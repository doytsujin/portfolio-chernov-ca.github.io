#!/usr/bin/env python3
"""Render the 1200x630 link-preview cards into docs/og/.

Separate from build.py because this needs Chrome and a network fetch for the
webfont, while build.py is standard library and must stay runnable anywhere.
The cards are committed, so a normal build never calls this -- rerun it only
when a project's title, lede or image changes.

Rendered in Chrome rather than drawn with PIL so the cards use the same
Roboto Slab as the site; no copy of the font has to be vendored to match.
"""

from __future__ import annotations

import functools
import http.server
import json
import pathlib
import shutil
import socket
import subprocess
import sys
import threading

ROOT = pathlib.Path(__file__).resolve().parent
DOCS = ROOT / "docs"
OG = DOCS / "og"
TMP = DOCS / "_og_tmp"

CHROME = next((c for c in ("google-chrome", "chromium-browser", "chromium")
               if shutil.which(c)), None)

CARD_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Roboto+Slab:wght@400;700&display=swap');
*{box-sizing:border-box;margin:0}
html,body{width:1200px;height:630px;overflow:hidden}
body{display:flex;background:#0b1220;color:#f8fafc;
font:400 16px/1.5 "Roboto Slab",Georgia,serif}
.pane{flex:1;min-width:0;padding:64px 56px;display:flex;flex-direction:column;
border-left:10px solid #ff2d2d}
.eyebrow{font-size:19px;letter-spacing:.2em;text-transform:uppercase;color:#94a3b8}
h1 .sur{color:#ff2d2d}
h1{margin-top:22px;font-size:60px;font-weight:700;line-height:1.08;letter-spacing:-.02em}
h1.long{font-size:47px}
h1.longer{font-size:39px}
.lede{margin-top:20px;font-size:25px;line-height:1.38;color:#cbd5e1;font-style:italic;
display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.foot{margin-top:auto;display:flex;align-items:baseline;gap:16px;font-size:21px;
color:#94a3b8}
.foot .dom{color:#f8fafc;font-weight:700}
.foot .accent{color:#ff2d2d}
.shot{width:420px;flex-shrink:0;background:#111c2f;position:relative}
.shot img{width:100%;height:100%;object-fit:cover;object-position:left center;opacity:.92}
.shot::after{content:"";position:absolute;inset:0;
background:linear-gradient(90deg,#0b1220 0%,rgba(11,18,32,.55) 30%,rgba(11,18,32,0) 72%)}
"""


def card_html(*, eyebrow: str, title: str, lede: str, image: str | None) -> str:
    cls = "" if len(title) <= 34 else ("long" if len(title) <= 58 else "longer")
    shot = (f'<div class="shot"><img src="../img/{image}" alt=""></div>'
            if image else "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<style>{CARD_CSS}</style></head><body>
<div class="pane">
  <p class="eyebrow">{eyebrow}</p>
  <h1 class="{cls}">{title}</h1>
  <p class="lede">{lede}</p>
  <p class="foot"><span class="dom">portfolio.chernov.ca</span>
    <span class="accent">&bull;</span><span>Alexander Chernov</span></p>
</div>{shot}</body></html>
"""


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def shoot(port: int, name: str, out: pathlib.Path) -> None:
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--virtual-time-budget=6000",
         "--window-size=1200,630", f"--screenshot={out}",
         f"http://127.0.0.1:{port}/_og_tmp/{name}.html"],
        check=True, capture_output=True,
    )


def main() -> None:
    if CHROME is None:
        sys.exit("refusing: no chrome/chromium on PATH -- cards are committed, "
                 "so this is only needed when content changes")

    projects = json.loads((ROOT / "content" / "projects.json").read_text())

    OG.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)

    cards = [("site", card_html(
        eyebrow="Portfolio",
        title='Alexander <span class="sur">CHERNOV</span>',
        lede="Something proposes under uncertainty &mdash; what decides whether it may act? "
             "Ten systems, one question.",
        image=None))]
    for i, p in enumerate(projects, start=1):
        cards.append((p["slug"], card_html(
            eyebrow=f"Project {i:02d}",
            title=p["title"],
            lede=p.get("lede", ""),
            image=p.get("image"))))

    for name, doc in cards:
        (TMP / f"{name}.html").write_text(doc, encoding="utf-8")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(DOCS))
    port = free_port()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        for name, _ in cards:
            out = OG / f"{name}.png"
            shoot(port, name, out)
            size = out.stat().st_size
            # Chrome exits 0 on a page that never painted, so the file existing
            # proves nothing; a real 1200x630 card is never this small.
            if size < 8000:
                sys.exit(f"refusing: og/{name}.png is {size} B -- it did not render")
            print(f"  og/{name}.png  {size/1024:.0f} kB")
    finally:
        server.shutdown()
        shutil.rmtree(TMP, ignore_errors=True)

    print(f"rendered {len(cards)} cards into docs/og/")


if __name__ == "__main__":
    main()
