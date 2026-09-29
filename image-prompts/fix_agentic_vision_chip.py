"""Replace the one misspelled label in the generated agentic-vision-stack.png.

gpt-image-2 drew the "VSS overlay, read-only over VISS" chip as a microchip and
spelled it "oved-only". This paints a white annotation chip, in the other
chips' style, over exactly that footprint, with the text set in Roboto Slab
rather than generated, so it cannot be misspelled. Idempotent: it reads the
generated original and writes the fixed copy beside it.
"""
import pathlib
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "image-src" / "agentic-vision-stack.png"
OUT = HERE.parent / "image-src" / "agentic-vision-stack-fixed.png"
BOX = (1366, 394, 1512, 512)          # covers the microchip and its pins
LINES = ["VSS overlay,", "read-only", "over VISS"]

im = Image.open(SRC).convert("RGBA")
shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle((BOX[0] + 2, BOX[1] + 5, BOX[2] + 2, BOX[3] + 5), 8, fill=(15, 23, 42, 60))
im = Image.alpha_composite(im, shadow.filter(ImageFilter.GaussianBlur(6)))
d = ImageDraw.Draw(im)
d.rounded_rectangle(BOX, 8, fill=(255, 255, 255, 255), outline=(203, 213, 225, 255), width=2)
font = ImageFont.truetype(str(HERE / "fonts" / "RobotoSlab-Bold.ttf"), 20)
heights = [font.getbbox(t)[3] - font.getbbox(t)[1] for t in LINES]
gap = 10
y = BOX[1] + ((BOX[3] - BOX[1]) - (sum(heights) + gap * (len(LINES) - 1))) // 2
for t, h in zip(LINES, heights):
    w = font.getlength(t)
    d.text(((BOX[0] + BOX[2] - w) / 2, y - font.getbbox(t)[1]), t, font=font, fill=(15, 23, 42, 255))
    y += h + gap
im.convert("RGB").save(OUT)
print("wrote", OUT)
