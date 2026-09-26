"""Compose the VarScope recording: the whole app on the left for context, its
detail panel magnified on the right so the proposal is readable, and a strip of
three steps underneath. Every value on the strip is read from phases.json,
which the recorder took off the live page (panel text sampled every 300 ms)."""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REC = Path(sys.argv[1]); OUT = sys.argv[2]
FONTS = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).resolve().parent / "fonts"
F = lambda name, size: ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)
SLAB, SLAB_B, MONO = "RobotoSlab-Regular", "RobotoSlab-Bold", "NerdMono"
BG, LINE, INK, MUTED, FAINT, RED, MULB = "#f1f5f9", "#cbd5e1", "#0f172a", "#475569", "#94a3b8", "#dc2626", "#830051"
CW, CH, FPS, APP = 1600, 900, 30, (1600, 1000)

frames = json.loads((REC / "frames.json").read_text())
meta = json.loads((REC / "phases.json").read_text())
ph = {p["name"]: p for p in meta["phases"]}
timeline = meta["timeline"]
T0 = frames[0]["t"]
END = frames[-1]["t"] - T0

# Layout: app on the left, magnified panel on the right, steps along the bottom.
AS = 0.6
AX, AY = 28, 104
AW, AH = int(APP[0] * AS), int(APP[1] * AS)
CROP = (1284, 600, 1582, 984)
cw, chh = CROP[2] - CROP[0], CROP[3] - CROP[1]
ZS = min(556 / cw, 590 / chh)
ZW, ZH = int(cw * ZS), int(chh * ZS)
ZX, ZY = 1016 + (556 - ZW) // 2, AY

# Facts read off the page.
final = ph["proposal"]
model = re.search(r"browser/(\S+) (\w+) \(webgpu ([^)]+)\)", final["model"])
MODEL, QUANT, GPU = model.group(1), model.group(2), model.group(3)
TARGET, PCT, MAPPED = final["target"], final["pct"], final["mapped"]
DOMAIN = ph["selected"]["domain"]
loads = [x for x in timeline if x["text"].startswith("Loading model")]
TOTAL_MB = re.search(r"/ (\d+) MB", loads[-1]["text"]).group(1) if loads else None
t_load_end = next((x["t"] for x in timeline if loads and x["t"] > loads[-1]["t"]), None)
t_prop = timeline[-1]["t"]
INFER = t_prop - t_load_end if t_load_end else None
SEL_T, SUG_T = ph["selected"]["t"] - T0 - 0.9, ph["reasoning"]["t"] - T0 - 0.7
PROP_T = t_prop - T0


def panel_status(t):
    cur = None
    for x in timeline:
        if x["t"] - T0 <= t: cur = x["text"]
    return cur


def shown_t(t):
    """Page time of the frame on screen at clip time t, so a caption never runs ahead of the picture."""
    best = frames[0]
    for f in frames:
        if f["t"] - T0 <= t: best = f
        else: break
    return best["t"] - T0 + 0.01


def step_texts(t):
    s1 = f"{ph['selected']['selected']} · SDTM · domain {DOMAIN}" if t >= SEL_T else "an SDTM variable, picked from the graph"
    st = panel_status(t) if t >= SUG_T else None
    if st is None:
        s2 = f"{MODEL} {QUANT} runs in this tab"
    elif st.startswith("Loading model"):
        mb = re.search(r"(\d+) MB / (\d+) MB", st)
        s2 = f"loading the model: {mb.group(1)} / {mb.group(2)} MB · first use only"
    elif st.startswith("Reasoning"):
        s2 = f"reasoning on the GPU via WebGPU ({GPU})"
    else:
        s2 = f"answered in {INFER:.1f} s once loaded, on WebGPU ({GPU})"
    s3 = f"{TARGET} · {PCT} · not applied · mapped {MAPPED}" if t >= PROP_T else "a proposal waits for a reviewer"
    active = 0 if t < SEL_T + 1.2 else 1 if t < PROP_T else 2
    return [s1, s2, s3], active


def wrap(d, text, font, width):
    out, cur = [], ""
    for w in text.split():
        t2 = (cur + " " + w).strip()
        if d.textlength(t2, font=font) <= width or not cur: cur = t2
        else: out.append(cur); cur = w
    return out + ([cur] if cur else [])


def frame_at(t):
    best = frames[0]
    for f in frames:
        if f["t"] - T0 <= t: best = f
        else: break
    return best["file"]


_cache = {}
def app_img(path):
    if path not in _cache:
        im = Image.open(path).convert("RGB")
        if im.size != APP: im = im.resize(APP, Image.LANCZOS)
        _cache.clear(); _cache[path] = im
    return _cache[path]


TITLES = ["1  SELECT", "2  SUGGEST, IN THE BROWSER", "3  A PROPOSAL, NOT A MAPPING"]
ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{CW}x{CH}",
                       "-r", str(FPS), "-i", "-", "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                       "-crf", "20", "-movflags", "+faststart", "-an", OUT], stdin=subprocess.PIPE)
n = int((END + 0.5) * FPS)
for k in range(n):
    t = k / FPS
    img = Image.new("RGB", (CW, CH), BG); d = ImageDraw.Draw(img)
    app = app_img(frame_at(t))
    d.text((AX, 30), "VARSCOPE  ·  SDTM → ADAM", font=F(MONO, 13), fill=MUTED)
    d.text((AX, 50), "Mapping proposals from a model running in the browser tab, recorded live", font=F(SLAB_B, 22), fill=INK)
    img.paste(app.resize((AW, AH), Image.LANCZOS), (AX, AY))
    d.rectangle([AX - 1, AY - 1, AX + AW, AY + AH], outline=LINE)
    has_panel = t >= SEL_T + 0.4
    if has_panel:
        bx0, by0 = AX + CROP[0] * AS, AY + CROP[1] * AS
        bx1, by1 = AX + CROP[2] * AS, AY + CROP[3] * AS
        d.rectangle([bx0, by0, bx1, by1], outline=RED, width=2)
        d.line([(bx1, by0), (ZX, ZY)], fill=FAINT, width=1)
        d.line([(bx1, by1), (ZX, ZY + ZH)], fill=FAINT, width=1)
        img.paste(app.crop(CROP).resize((ZW, ZH), Image.LANCZOS), (ZX, ZY))
        d.rectangle([ZX - 1, ZY - 1, ZX + ZW, ZY + ZH], outline=RED, width=2)
    else:
        d.rounded_rectangle([ZX, ZY + 180, ZX + ZW, ZY + 360], 10, fill="#ffffff", outline=LINE)
        d.text((ZX + 24, ZY + 208), "the detail panel opens here", font=F(MONO, 13), fill=MUTED)
        for i, ln in enumerate(wrap(d, "Pick an SDTM variable and ask for its ADaM mapping.", F(SLAB, 20), ZW - 48)):
            d.text((ZX + 24, ZY + 238 + i * 28), ln, font=F(SLAB, 20), fill=INK)
    texts, active = step_texts(shown_t(t))
    sw, sx0, sy = (CW - 2 * AX - 2 * 16) / 3, AX, 738
    for i in range(3):
        x0 = sx0 + i * (sw + 16)
        on, done = i == active, i < active
        d.rounded_rectangle([x0, sy, x0 + sw, sy + 128], 10, fill="#ffffff", outline=LINE)
        if on: d.rectangle([x0 + 1, sy + 1, x0 + sw - 1, sy + 4], fill=RED)
        d.text((x0 + 18, sy + 18), TITLES[i], font=F(MONO, 13), fill=RED if on else (INK if done else FAINT))
        for j, ln in enumerate(wrap(d, texts[i], F(SLAB, 19), sw - 36)[:3]):
            d.text((x0 + 18, sy + 44 + j * 26), ln, font=F(SLAB, 19), fill=INK if (on or done) else FAINT)
    d.text((AX, CH - 22), "public CDISC pilot · computed in the page · proposals are labelled as such and never applied", font=F(MONO, 12), fill=MUTED)
    ff.stdin.write(img.tobytes())
ff.stdin.close(); ff.wait()
print("wrote", OUT, n, "frames", f"{END:.1f}s", "| model", MODEL, QUANT, GPU, "| target", TARGET, PCT, "| infer", f"{INFER:.2f}s")
