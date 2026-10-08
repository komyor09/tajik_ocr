"""Generate the synthetic benchmark (90 images): uv run python bench/make_set.py"""

import json, random
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

random.seed(0)
np.random.seed(0)
LINES = [
    "Ҷумҳурии Тоҷикистон дар Осиёи Марказӣ ҷойгир аст.",
    "Пойтахти кишвар шаҳри Душанбе мебошад.",
    "Забони тоҷикӣ забони давлатии ҷумҳурӣ аст.",
    "Хуҷанд яке аз шаҳрҳои қадимтарини Осиёи Миёна аст.",
    "Кӯҳҳои Помир қисми зиёди қаламравро ишғол мекунанд.",
    "Дарёи Сир аз водии Фарғона мегузарад.",
    "Донишҷӯён ҳар рӯз ба донишгоҳ меоянд.",
    "Ғолиби озмун ҷоизаи асосиро гирифт.",
    "Мо бо ҳамдигар бо забони модарӣ гап мезанем.",
    "Ин китоб барои хонандагони ҷавон навишта шудааст.",
    "Шумораи аҳолӣ зиёда аз даҳ миллион нафар аст.",
    "Ҳукумат барномаи нави рақамикуниро қабул кард.",
]
from pathlib import Path as _P

_W = "C:/Windows/Fonts/"
_L = "/usr/share/fonts/truetype/"
_CANDIDATES = {  # Windows font first, Linux fallback; all cover Tajik letters
    "sans": [_W + "arial.ttf", _L + "liberation/LiberationSans-Regular.ttf"],
    "serif": [_W + "times.ttf", _L + "liberation/LiberationSerif-Regular.ttf"],
    "calibri": [_W + "calibri.ttf", _L + "crosextra/Carlito-Regular.ttf"],
    "bold": [_W + "arialbd.ttf", _L + "dejavu/DejaVuSans-Bold.ttf"],
    "mono": [_W + "cour.ttf", _L + "freefont/FreeMono.ttf"],
}
FONTS = {k: next((f for f in v if _P(f).exists()), None) for k, v in _CANDIDATES.items()}
FONTS = {k: v for k, v in FONTS.items() if v}


def render(lines, font, size=36):
    f = ImageFont.truetype(font, size)
    h = int(size * 1.7)
    w = max(int(f.getlength(l)) for l in lines) + 80
    img = Image.new("L", (w, h * len(lines) + 60), 255)
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        d.text((40, 30 + i * h), l, fill=0, font=f)
    return img


def cond(img, c):
    if c == "clean":
        return img
    if c == "small":
        return img.resize((img.width * 2 // 5, img.height * 2 // 5), Image.LANCZOS)
    if c == "blur":
        return img.filter(ImageFilter.GaussianBlur(1.6))
    if c == "noise_jpeg":
        a = np.asarray(img).astype(float) + np.random.normal(0, 28, (img.height, img.width))
        im = Image.fromarray(a.clip(0, 255).astype("uint8"))
        import io

        b = io.BytesIO()
        im.save(b, "JPEG", quality=30)
        return Image.open(b).convert("L")
    if c == "rotate":
        return img.rotate(4, expand=True, fillcolor=255, resample=Image.BICUBIC)
    if c == "photo":  # uneven lighting + low contrast + slight blur
        a = np.asarray(img).astype(float) / 255
        yy, xx = np.mgrid[0 : img.height, 0 : img.width]
        light = 0.55 + 0.4 * (xx / img.width) * (1 - 0.5 * yy / img.height)
        a = (a * 0.6 + 0.25) * light * 255
        return Image.fromarray(a.clip(0, 255).astype("uint8")).filter(ImageFilter.GaussianBlur(0.8))


out = Path(__file__).parent / "set"
out.mkdir(exist_ok=True)
gt = {}
for p in range(3):
    lines = LINES[p * 4 : p * 4 + 4]
    for fn, fp in FONTS.items():
        base = render(lines, fp)
        for c in ["clean", "small", "blur", "noise_jpeg", "rotate", "photo"]:
            name = f"p{p}_{fn}_{c}.png"
            cond(base, c).convert("RGB").save(out / name)
            gt[name] = "\n".join(lines)
json.dump(gt, open(Path(__file__).parent / "gt.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(gt))
