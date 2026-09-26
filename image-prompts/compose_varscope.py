"""Compose the mapping tool's keyframes into a panes clip: the app in the middle,
zooming from the whole graph to the selected variable and its detail panel,
note cards on either side tied to what they describe by a leader line and a
crosshair, and three steps underneath. Every value on a card is read from
keys.json, which the recorder took off the live page; the clip is time
compressed and the cards carry the measured timings.

    python3 compose_varscope.py <keyframe dir> <out.mp4> [fonts dir]
"""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REC = Path(sys.argv[1]); OUT = sys.argv[2]
FONTS = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).resolve().parent / "fonts"
F = lambda name, size: ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
SLAB, SLAB_B, MONO = "RobotoSlab-Regular", "RobotoSlab-Bold", "NerdMono"
BG, LINE, INK, MUTED, FAINT, RED = "#f1f5f9", "#cbd5e1", "#0f172a", "#475569", "#94a3b8", "#dc2626"
CW, CH, FPS = 1600, 900, 30

meta = json.loads((REC / "keys.json").read_text())
K = meta["keys"]
NODE = meta["node"]
by = lambda name: [k for k in K if k["name"] == name]
over, sel = by("overview")[0], by("selected")[0]
pre = [k for k in K if k["name"] == "other"]
loads, reas, prop = by("loading"), by("reasoning")[-1], by("proposal")[-1]

# Facts, all read off the page.
m = re.search(r"browser/(\S+) (\w+) \(webgpu ([^)]+)\)", prop["model"])
MODEL, QUANT, GPU = m.group(1), m.group(2), m.group(3)
TOTAL_MB = re.search(r"/ (\d+) MB", loads[-1]["panel"]).group(1)
LOAD_S = reas["t"] - meta["tClick"]
INFER_S = prop["t"] - reas["t"]
WHO, DOMAIN = sel["selected"], sel["domain"]
TARGET, PCT, MAPPED = prop["target"], prop["pct"], prop["mapped"]

# Stage: where the app sits, and the two views of it.
SX, SY, SW, SH = 300, 96, 1000, 625
FULL = (0, 0, 1600, 1000)
ZOOM = (820, 459, 1590, 940)           # same 1.6 aspect as the stage; stops above the view switcher

# Timeline: (keyframe, seconds, zoom from, zoom to).
scenes = [(over, 2.0, FULL, FULL), (sel, 0.4, FULL, FULL), (sel, 1.1, FULL, ZOOM), (sel, 1.8, ZOOM, ZOOM)]
scenes += [(k, 0.5, ZOOM, ZOOM) for k in pre]
scenes += [(k, 0.42, ZOOM, ZOOM) for k in loads]
scenes += [(reas, 2.0, ZOOM, ZOOM), (prop, 6.5, ZOOM, ZOOM)]


def ease(u): return u * u * (3 - 2 * u)


def lerp_box(a, b, u): return tuple(a[i] + (b[i] - a[i]) * u for i in range(4))


def to_stage(x, y, box):
    return SX + (x - box[0]) * SW / (box[2] - box[0]), SY + (y - box[1]) * SH / (box[3] - box[1])


def wrap(d, text, font, width):
    out, cur = [], ""
    for w in text.split():
        t2 = (cur + " " + w).strip()
        if d.textlength(t2, font=font) <= width or not cur: cur = t2
        else: out.append(cur); cur = w
    return out + ([cur] if cur else [])


_img = {}
def key_img(k):
    if k["file"] not in _img: _img[k["file"]] = Image.open(k["file"]).convert("RGB")
    return _img[k["file"]]


def stage(k, box):
    im = key_img(k).crop(tuple(round(v) for v in box)).resize((SW, SH), Image.LANCZOS)
    return im


def cards_for(k):
    """(side, eyebrow, title, body, target viewport point or None, live?)"""
    n = k["name"]
    out = []
    if n != "overview":
        out.append(("L", "SELECTED", WHO, f"SDTM variable · domain {DOMAIN}", (NODE[0] - 16, NODE[1]), n == "selected"))
    if n in ("other", "loading", "reasoning", "proposal"):
        hd = k["rects"]["head"] or prop["rects"]["head"]
        pt = (hd[0] - 8, hd[1] + 30)
        if n == "loading":
            mb = re.search(r"(\d+) MB / (\d+) MB", k["panel"])
            out.append(("L", "THE MODEL, IN THIS TAB", f"loading {mb.group(1)} / {mb.group(2)} MB", "weights fetched once, then cached by the browser", pt, True))
        elif n in ("other", "reasoning"):
            out.append(("L", "THE MODEL, IN THIS TAB", "reasoning on the GPU", f"{MODEL} {QUANT} · WebGPU ({GPU})", pt, True))
        else:
            out.append(("L", "THE MODEL, IN THIS TAB", f"answered in {INFER_S:.1f} s", f"after a {LOAD_S:.0f} s first-use load of {TOTAL_MB} MB · {MODEL} {QUANT}", pt, False))
    if n == "proposal":
        tg = k["rects"]["target"]
        out.append(("R", "PROPOSED", f"{TARGET} · {PCT}", "the model's suggestion and its own confidence", (tg[0] + tg[2] + 8, tg[1] + tg[3] / 2), True))
        md = k["rects"]["model"]
        out.append(("R", "NOT APPLIED", "proposal only", f"review before use · mapped {MAPPED}", (md[0] + md[2] + 8, md[1] + md[3] * 0.75), True))
    elif n not in ("overview",):
        out.append(("R", "PROPOSED", "nothing yet", "a proposal waits for a reviewer; nothing is ever applied here", None, False))
    return out


def draw_cards(img, d, k, box):
    LX, RX, CWID = 24, SX + SW + 20, SX - 44
    cols = {"L": [], "R": []}
    for c in cards_for(k): cols[c[0]].append(c)
    for side, cs in cols.items():
        y = SY + 20
        for (s, eyebrow, title, body, pt, live) in cs:
            x = LX if side == "L" else RX
            tf, bf = F(SLAB_B, 21), F(SLAB, 16)
            tl, bl = wrap(d, title, tf, CWID - 32), wrap(d, body, bf, CWID - 32)
            h = 20 + 18 + len(tl) * 27 + 6 + len(bl) * 21 + 16
            if pt:
                gx, gy = to_stage(pt[0], pt[1], box)
                y = max(y, min(gy - 34, SY + SH - h))
            d.rounded_rectangle([x, y, x + CWID, y + h], 10, fill="#ffffff", outline=LINE)
            if live: d.rectangle([x if side == "L" else x, y + 1, x + 4, y + h - 1], fill=RED)
            d.text((x + 16, y + 16), eyebrow, font=F(MONO, 12), fill=MUTED)
            yy = y + 38
            for ln in tl: d.text((x + 16, yy), ln, font=tf, fill=INK if pt or side == "L" else FAINT); yy += 27
            yy += 6
            for ln in bl: d.text((x + 16, yy), ln, font=bf, fill=MUTED); yy += 21
            if pt:
                gx, gy = to_stage(pt[0], pt[1], box)
                sx = x + CWID if side == "L" else x
                d.line([(sx, y + 30), (gx, gy)], fill="#64748b", width=1)
                r = 7
                d.ellipse([gx - r, gy - r, gx + r, gy + r], outline=RED, width=2)
                d.line([(gx - r - 5, gy), (gx - r + 2, gy)], fill=RED, width=2)
                d.line([(gx + r - 2, gy), (gx + r + 5, gy)], fill=RED, width=2)
            y += h + 14


TITLES = ["1  SELECT", "2  SUGGEST, IN THE BROWSER", "3  A PROPOSAL, NOT A MAPPING"]
def strip(d, k):
    n = k["name"]
    active = 0 if n in ("overview", "selected") else 2 if n == "proposal" else 1
    texts = [f"{WHO} · SDTM · domain {DOMAIN}" if n != "overview" else "an SDTM variable, picked from the graph",
             f"{MODEL} {QUANT} runs on this machine's GPU, inside the tab",
             f"{TARGET} · {PCT} · not applied · mapped {MAPPED}" if n == "proposal" else "a proposal waits for a reviewer"]
    sw, sy = (CW - 48 - 32) / 3, 748
    for i in range(3):
        x0 = 24 + i * (sw + 16)
        on, done = i == active, i < active
        d.rounded_rectangle([x0, sy, x0 + sw, sy + 104], 10, fill="#ffffff", outline=LINE)
        if on: d.rectangle([x0 + 1, sy + 1, x0 + sw - 1, sy + 4], fill=RED)
        d.text((x0 + 16, sy + 16), TITLES[i], font=F(MONO, 12), fill=RED if on else (INK if done else FAINT))
        for j, ln in enumerate(wrap(d, texts[i], F(SLAB, 18), sw - 32)[:2]):
            d.text((x0 + 16, sy + 42 + j * 24), ln, font=F(SLAB, 18), fill=INK if (on or done) else FAINT)


def frame(k, box, prev=None, fade=1.0):
    img = Image.new("RGB", (CW, CH), BG); d = ImageDraw.Draw(img)
    d.text((24, 26), "VARSCOPE  ·  SDTM → ADAM", font=F(MONO, 13), fill=MUTED)
    d.text((24, 46), "A mapping proposal from a model running in the browser tab", font=F(SLAB_B, 22), fill=INK)
    st = stage(k, box)
    if prev is not None and fade < 1.0: st = Image.blend(stage(prev, box), st, fade)
    img.paste(st, (SX, SY))
    d.rectangle([SX - 1, SY - 1, SX + SW, SY + SH], outline=LINE)
    draw_cards(img, d, k, box)
    strip(d, k)
    d.text((24, CH - 26), "recorded live on the public CDISC pilot · time compressed; the timings on the cards were measured in this run",
           font=F(MONO, 12), fill=MUTED)
    return img


ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{CW}x{CH}",
                       "-r", str(FPS), "-i", "-", "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                       "-crf", "18", "-movflags", "+faststart", "-an", OUT], stdin=subprocess.PIPE)
FADE = 0.18
prev_k, total = None, 0
for (k, dur, b0, b1) in scenes:
    n = max(1, round(dur * FPS))
    cache = None
    for i in range(n):
        u = ease(i / max(1, n - 1)) if b0 != b1 else 0.0
        box = lerp_box(b0, b1, u)
        tfade = i / FPS / FADE
        if b0 == b1 and tfade >= 1 and cache is not None:
            img = cache
        else:
            img = frame(k, box, prev_k if prev_k is not k else None, min(1.0, tfade))
            if b0 == b1 and tfade >= 1: cache = img
        ff.stdin.write(img.tobytes()); total += 1
    prev_k = k
ff.stdin.close(); ff.wait()
print(f"wrote {OUT} {total} frames {total / FPS:.1f}s | {WHO} -> {TARGET} {PCT} | load {LOAD_S:.1f}s infer {INFER_S:.1f}s | {MODEL} {QUANT} {GPU}")
