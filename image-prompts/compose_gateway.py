#!/usr/bin/env python3
"""Encode the gateway recording and prove what it shows.

    python3 compose_gateway.py <recdir> <out.mp4> <poster.jpg> <card.webp>

The recording is a CDP screencast: frames arrive when the page repaints, each
with its own timestamp, and the video is resampled from those real intervals
at a fixed rate -- it runs in real time, nothing compressed.

Before anything is written, every frame the video will hold is read with OCR
for the internal product name and the record identifiers the demo corpus
keeps. record_gateway.mjs already removes them from the page and polls the DOM;
this checks the pixels, which is what a reader sees. A check that has never
failed proves nothing, so it is also run on a frame known to carry each
pattern, and the run refuses if it does not fire there.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

FPS = 30

# Shared with record_gateway.mjs, and kept out of the repository because it
# names what it hides.
LIST = Path(os.environ.get("REDACT_FILE") or Path(__file__).resolve().parent / "redact.local.json")
if not LIST.is_file():
    sys.exit(f"refusing: no redaction list at {LIST} -- it is kept out of the "
             "repository, so it has to be present locally")
REDACT = json.loads(LIST.read_text())
LEAK = re.compile("|".join(REDACT["patterns"]), re.I)


def ocr(path: Path) -> str:
    return subprocess.run(["tesseract", str(path), "-"], capture_output=True,
                          text=True, check=True).stdout


def leaks(path: Path) -> list[str]:
    return [ln.strip() for ln in ocr(path).splitlines() if LEAK.search(ln)]


def prove_ocr_bites(tmp: Path) -> None:
    """Render each pattern in the page's own sizes and insist OCR finds it."""
    from PIL import ImageDraw, ImageFont
    font = Path(__file__).resolve().parent / "fonts" / "NerdMono.ttf"
    for text in REDACT["samples"]:
        im = Image.new("RGB", (1600, 1000), "white")
        ImageDraw.Draw(im).text((40, 400), text, fill="#334155",
                                font=ImageFont.truetype(str(font), 13))
        p = tmp / "bite.png"
        im.save(p)
        if not leaks(p):
            sys.exit(f"refusing: OCR did not find {text!r} in a frame made to "
                     "carry it, so a clean result would mean nothing")


def main() -> None:
    rec, out, poster, card = (Path(a) for a in sys.argv[1:5])
    frames = json.loads((rec / "frames.json").read_text())
    states = json.loads((rec / "states.json").read_text())
    t_of = {s["name"]: s["t"] for s in states["states"]}

    # Frames before the first state are the page settling; the clip starts at
    # the intro. Durations are the real gaps between repaints.
    frames = [f for f in frames if t_of["intro"] - 0.05 <= f["t"] <= t_of["end"] + 0.05]
    if len(frames) < 100:
        sys.exit(f"refusing: only {len(frames)} frames between intro and end")

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        prove_ocr_bites(tmp)

        # Every 4th frame, plus the last frame before each repaint gap of
        # more than half a second (a held state is on screen longest).
        pick = {i for i in range(0, len(frames), 4)}
        pick |= {i for i in range(len(frames) - 1) if frames[i + 1]["t"] - frames[i]["t"] > 0.5}
        pick.add(len(frames) - 1)
        with ThreadPoolExecutor(max_workers=4) as ex:
            found = list(ex.map(lambda i: (i, leaks(Path(frames[i]["file"]))), sorted(pick)))
        bad = [(i, l) for i, l in found if l]
        if bad:
            for i, l in bad[:12]:
                print(f"  frame {i} ({frames[i]['file']}): {l}", file=sys.stderr)
            sys.exit(f"refusing: {len(bad)} of {len(pick)} frames read as carrying a redacted pattern")
        print(f"ocr: {len(pick)} of {len(frames)} frames read, none carry a redacted pattern")

    # Resampled here at a fixed rate: each output tick shows the latest repaint
    # at or before it. (ffmpeg's concat list gives every still at least 1/25 s,
    # which stretched 44 s of screencast to 49.) A held state repaints nothing,
    # so the last frame stays up until the recording's own end mark.
    W, H = states["W"], states["H"]
    t0, t1 = frames[0]["t"], max(t_of["end"], frames[-1]["t"] + 1.5)
    ticks = int((t1 - t0) * FPS)
    out.parent.mkdir(parents=True, exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-vf", "format=yuv420p",
                           "-c:v", "libx264", "-preset", "slow", "-crf", "28",
                           "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    i, shown, raw = 0, -1, b""
    for k in range(ticks):
        t = t0 + k / FPS
        while i + 1 < len(frames) and frames[i + 1]["t"] <= t:
            i += 1
        if i != shown:
            raw, shown = Image.open(frames[i]["file"]).convert("RGB").tobytes(), i
        ff.stdin.write(raw)
    ff.stdin.close()
    if ff.wait():
        sys.exit("refusing: ffmpeg failed")

    # Poster and card: the held chat answer, the state that shows the most.
    held = [f for f in frames if t_of["chat"] < f["t"] < t_of["graph"] - 1.2]
    # Read on its own: it is published as a still, and the sampling above
    # need not have picked it.
    if leaks(Path(held[-1]["file"])):
        sys.exit("refusing: the poster frame reads as carrying a redacted pattern")
    still = Image.open(held[-1]["file"]).convert("RGB")
    still.save(poster, quality=80)
    # The card's image pane is 420 x 630 (2:3): the chat panel, below the hint.
    still.crop((1160, 340, 1600, 1000)).save(card, quality=86)

    print(f"clip -> {out}  ({ticks / FPS:.1f} s at {FPS} fps from {len(frames)} repaints)  "
          f"poster -> {poster}  card -> {card}")


if __name__ == "__main__":
    main()
