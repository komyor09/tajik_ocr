"""Generate a test image with Tajik text: uv run python scripts/make_sample.py"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TEXT = [
    "Ҷумҳурии Тоҷикистон",
    "Забони тоҷикӣ забони давлатӣ мебошад.",
    "Ғайрат, ҳунар ва қувват — роҳи бахт.",
    "Хуҷанд, кӯчаи Ленин 226",
]
FONTS = [
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/times.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]

font_path = next((f for f in FONTS if Path(f).exists()), None)
font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default(40)
img = Image.new("RGB", (1000, 80 + 70 * len(TEXT)), "white")
draw = ImageDraw.Draw(img)
for i, line in enumerate(TEXT):
    draw.text((40, 40 + i * 70), line, fill="black", font=font)
out = Path("samples/tajik_sample.png")
out.parent.mkdir(exist_ok=True)
img.save(out)
print(f"Saved {out}")
