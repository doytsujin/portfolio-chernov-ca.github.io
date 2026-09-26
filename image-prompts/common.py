"""Shared call and style for the portfolio's project illustrations.

Same form as the LinkedIn article images -- a rendered hero object, thin leader-line
annotation, one statement band, an explicit list of what not to draw -- recoloured
to the portfolio: slate background, white panels, slate-navy ink, Roboto-Slab-like
slab-serif headings, and ONE accent red (#dc2626) used sparingly, with a quiet
royal blue (#1d4ed8) for neutral chips.
"""
import base64, pathlib, sys
from openai import OpenAI

STYLE = """
PALETTE AND TYPE (match an existing web page exactly): background a very pale cool slate (#f1f5f9) fading to white at the centre; panels and cards pure white with a hairline slate border (#e2e8f0) and soft shadow; all text in deep slate-navy (#0f172a) or muted slate (#475569); headings and numbers in a sturdy slab-serif typeface similar to Roboto Slab, labels in the same slab serif at small size. ONE accent colour only: a clean signal red (#dc2626), used sparingly for the single most important element and thin accent rules. A quiet royal blue (#1d4ed8) may appear only as thin outlines on neutral chips. No teal, no cyan, no glow, no gradients beyond the pale background.

RENDERING: the hero objects in soft-3D product-visualisation style - realistic matte materials, soft contact shadows, gentle rim light, sitting on a pale surface. Schematic content floats over them as thin slate leader lines and small labels, never as a flowchart of boxes and arrows. Generous margins; nothing important near the edges; balanced 3:2 composition.

TEXT: minimal, short labels only, spelled exactly as given, every number rendered exactly as given. No paragraphs.

DO NOT DRAW: vendor logos or brand marks of any kind (no AWS smile, no cloud-provider icons), no Kubernetes wheel, no human figures or hands, no robots with faces, no neon, no dark background, no watermark, no website, no signature, no bar-chart clip-art, no extra numbers beyond those given.
"""

def generate(prompt: str, out_name: str) -> None:
    key = pathlib.Path.home().joinpath(".openai_key").read_text().strip()
    client = OpenAI(api_key=key)
    model = sys.argv[1] if len(sys.argv) > 1 else "gpt-image-2"
    out = pathlib.Path(__file__).resolve().parent.parent / "image-src" / out_name
    print(f"calling {model} for {out_name} ...", flush=True)
    resp = client.images.generate(model=model, prompt=prompt + STYLE, size="1536x1024", quality="high")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(resp.data[0].b64_json))
    print("saved:", out, out.stat().st_size, "bytes")
