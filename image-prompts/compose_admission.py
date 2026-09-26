"""Compose the Admission recording into a 'panes' clip: the recording in the
middle, note cards in columns either side, each tied to the region it is about
by a leader line and a crosshair, on the side that region is on. Every word on
a card is read from states.json, which the recorder took off the live page."""
import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REC = Path(sys.argv[1]); OUT = sys.argv[2]
FONTS = Path(__file__).resolve().parent / "fonts"
F = lambda name, size: ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
SLAB, SLAB_B, SLAB_L, MONO = "RobotoSlab-Regular", "RobotoSlab-Bold", "RobotoSlab-Light", "NerdMono"

BG, CARD, LINE, INK, MUTED, RED, NAVY = "#f1f5f9", "#ffffff", "#cbd5e1", "#0f172a", "#475569", "#dc2626", "#0f172a"
CW, CH, FPS = 1600, 900, 30
# Crop of the 1080x860 viewport that holds the section, and where it lands.
CROP = (150, 30, 930, 840)
SCALE = 820 / (CROP[3] - CROP[1])
IW, IH = round((CROP[2] - CROP[0]) * SCALE), 820
IX, IY = (CW - IW) // 2, 40
COLW = IX - 2 * 28
LX, RX = 28, IX + IW + 28

frames = json.loads((REC / "frames.json").read_text())
meta = json.loads((REC / "states.json").read_text())
states, HOLD, T0 = meta["states"], meta["hold"], meta["t0"]
TOTAL = HOLD * len(states)


def to_canvas(x, y):
    return IX + (x - CROP[0]) * SCALE, IY + (y - CROP[1]) * SCALE


def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def notes_for(i):
    """Cards for state i: (side, target(x,y) in viewport px, eyebrow, title, title_color, body lines, mono?)."""
    s = states[i]
    px, py, pw, ph = s["principalRect"]
    left_btn = px + pw / 2 < 540
    parts = s.get("chipParts") or [s["verdict"]]
    reason = parts[1] if len(parts) > 1 else ""
    clause = parts[2] if len(parts) > 2 else ""
    granted = s["verdict"] == "GRANTED"
    cx, cy, cw, chh = s["chipRect"]
    ax, ay, aw, ah = s["admittedRect"]
    ex, ey, ew, eh = s["evidenceRect"]
    rx, ry, rw, rh = s["requestRect"]
    cards = [
        ("L" if left_btn else "R", (px - 10 if left_btn else px + pw + 10, py + ph / 2),
         "WHO IS ASKING", s["principal"], INK, [s["principalNote"]], False),
        ("R", (rx + rw + 10, ry + rh / 2), "WHAT IS ASKED", s["request"], INK,
         [f"resolves to {s['capability']}"], False),
        ("L", (cx - 10, cy + chh / 2), "VERDICT", s["verdict"], NAVY if granted else RED,
         [reason] + ([f"deciding clause {clause}"] if clause else []), False),
        ("R", (ax + aw + 10, ay + ah / 2), "WHAT RAN",
         "executed, within scope" if granted else "nothing executed", INK if granted else RED,
         [f"admitted scope: {s['admitted']}"], True),
        ("L", (ex - 10, ey + eh / 2), "EVIDENCE", s["evidence"].replace("evidence — ", ""), INK,
         ["written either way, refusals included (AD-010)"], False),
    ]
    return cards


def layout(draw, cards):
    """Measure each card and stack it near its target's height, without overlaps."""
    placed = []
    for side in ("L", "R"):
        col = [c for c in cards if c[0] == side]
        col.sort(key=lambda c: c[1][1])
        y_min = 92
        for c in col:
            side, (tx, ty), eyebrow, title, tcol, body, mono = c
            tf, bf = F(SLAB_B, 24), (F(MONO, 15) if mono else F(SLAB, 17))
            tl = wrap(draw, title, tf, COLW - 36)
            bl = [ln for b in body for ln in wrap(draw, b, bf, COLW - 36)]
            h = 20 + 16 + 8 + len(tl) * 30 + 6 + len(bl) * 23 + 16
            _, cy = to_canvas(tx, ty)
            y = max(y_min, min(cy - h / 2, CH - 70 - h))
            placed.append((c, y, h, tl, bl, tf, bf))
            y_min = y + h + 14
        col_items = [q for q in placed if q[0][0] == side]
        if col_items:
            over = col_items[-1][1] + col_items[-1][2] - (CH - 64)
            if over > 0:
                for j, q in enumerate(placed):
                    if q[0][0] == side:
                        placed[j] = (q[0], max(92, q[1] - over),) + q[2:]
    return placed


def draw_card(img, draw, item, alpha, changed):
    (side, (tx, ty), eyebrow, title, tcol, body, mono), y, h, tl, bl, tf, bf = item
    x = LX if side == "L" else RX
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    d.rounded_rectangle([x, y, x + COLW, y + h], 10, fill=(255, 255, 255, a), outline=(203, 213, 225, a), width=1)
    if changed:
        d.rounded_rectangle([x, y, x + 4, y + h], 2, fill=(220, 38, 38, a))
    yy = y + 18
    d.text((x + 18, yy), eyebrow, font=F(MONO, 12), fill=(71, 85, 105, a)); yy += 24
    for ln in tl:
        d.text((x + 18, yy), ln, font=tf, fill=tcol if a == 255 else _rgba(tcol, a)); yy += 30
    yy += 6
    for ln in bl:
        d.text((x + 18, yy), ln, font=bf, fill=(71, 85, 105, a)); yy += 23
    # leader: card edge -> region, with a crosshair at the region
    gx, gy = to_canvas(tx, ty)
    sx = x + COLW if side == "L" else x
    sy = y + 30
    d.line([(sx, sy), (gx, gy)], fill=(100, 116, 139, a), width=1)
    r = 7
    d.ellipse([gx - r, gy - r, gx + r, gy + r], outline=(220, 38, 38, a), width=2)
    d.line([(gx - r - 5, gy), (gx - r + 2, gy)], fill=(220, 38, 38, a), width=2)
    d.line([(gx + r - 2, gy), (gx + r + 5, gy)], fill=(220, 38, 38, a), width=2)
    img.alpha_composite(layer)


def _rgba(hexcol, a):
    h = hexcol.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def frame_at(t):
    best = frames[0]
    for f in frames:
        if f["t"] - T0 <= t: best = f
        else: break
    return best["file"]


def state_at(t):
    i = 0
    for k, s in enumerate(states):
        if s["t"] - T0 + 0.15 <= t: i = k
    return i


cache = {}
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                       "-s", f"{CW}x{CH}", "-r", str(FPS), "-i", "-", "-vf", "format=yuv420p",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-movflags", "+faststart", "-an", OUT],
                      stdin=subprocess.PIPE)
scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))
prev_cards = None
n = int(TOTAL * FPS)
for k in range(n):
    t = k / FPS
    i = state_at(t)
    img = Image.new("RGBA", (CW, CH), BG)
    d = ImageDraw.Draw(img)
    rec = Image.open(frame_at(t)).convert("RGB").crop(CROP).resize((IW, IH), Image.LANCZOS)
    d.rounded_rectangle([IX - 1, IY - 1, IX + IW, IY + IH], 8, outline=LINE, width=1)
    img.paste(rec, (IX, IY))
    # header and footer in the side margins
    d.text((LX, 34), "AGENTIC DATASETS", font=F(MONO, 13), fill=MUTED)
    d.text((LX, 52), "Admission, recorded live", font=F(SLAB_B, 20), fill=INK)
    d.text((RX, 34), f"STATE {i + 1} / {len(states)}", font=F(MONO, 13), fill=MUTED)
    d.text((RX, 52), "change who asks, or what", font=F(SLAB, 17), fill=MUTED)
    d.text((LX, CH - 44), "agenticdatasets.org/showcase", font=F(MONO, 13), fill=MUTED)
    d.text((RX, CH - 44), "computed in the page · no server · no model", font=F(MONO, 13), fill=MUTED)
    if i not in cache:
        cards = notes_for(i)
        prev = notes_for(i - 1) if i > 0 else None
        changed = [prev is None or (c[2], c[3], tuple(c[5])) != (p[2], p[3], tuple(p[5]))
                   for c, p in zip(cards, prev or cards)]
        if i == 0: changed = [False] * len(cards)
        cache[i] = (layout(scratch, cards), changed)
    placed, changed = cache[i]
    since = t - (states[i]["t"] - T0 + 0.15)
    alpha = 1.0 if i == 0 and since < 0 else min(1.0, max(0.0, since / 0.3)) if i > 0 else 1.0
    for item in placed:
        idx = [c[2] for c in notes_for(i)].index(item[0][2])
        a = alpha if changed[idx] else 1.0
        draw_card(img, d, item, a, changed[idx])
    ff.stdin.write(img.convert("RGB").tobytes())
ff.stdin.close(); ff.wait()
print("wrote", OUT, n, "frames")
