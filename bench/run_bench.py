"""Benchmark OCR engines on bench/set (90 synthetic Tajik images).

uv run python bench/run_bench.py paddle
uv run python bench/run_bench.py tesseract      # needs Tesseract + tgk.traineddata
uv run python bench/run_bench.py easyocr        # needs: uv add easyocr
Add --flatten to even out lighting before OCR.
"""

import collections
import difflib
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
TJ = set("ҒғӢӣҚқӮӯҲҳҶҷ")


def norm(s):
    return re.sub(r"\s+", " ", s.replace("--", "—")).strip()


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def tajik_hits(ref, hyp):
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    ok = sum(sum(c in TJ for c in ref[i1:i2]) for t, i1, i2, _, _ in sm.get_opcodes() if t == "equal")
    return ok, sum(c in TJ for c in ref)


def flatten(img: Image.Image) -> Image.Image:
    import cv2

    g = np.asarray(img.convert("L"))
    k = max(31, (min(g.shape) // 8) | 1)
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    return Image.fromarray(cv2.divide(g, bg, scale=255)).convert("RGB")


def make_engine(name):
    if name == "paddle":
        import os

        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            lang="tg",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        return lambda im: "\n".join(
            t for r in ocr.predict(np.asarray(im)[:, :, ::-1].copy()) for t in r["rec_texts"]
        )
    if name == "tesseract":
        import pytesseract

        return lambda im: pytesseract.image_to_string(im, lang="tgk", config="--psm 6")
    if name == "easyocr":
        import easyocr

        r = easyocr.Reader(["tjk"], gpu=False, verbose=False)
        return lambda im: "\n".join(r.readtext(np.asarray(im), detail=0))
    raise SystemExit(f"unknown engine {name}")


def main():
    engine = sys.argv[1]
    use_flatten = "--flatten" in sys.argv
    run = make_engine(engine)
    gt = json.loads((HERE / "gt.json").read_text(encoding="utf-8"))
    groups = collections.defaultdict(lambda: [0.0, 0, 0, 0])  # cer_sum, n, tj_ok, tj_total
    t0 = time.time()
    for name, ref in gt.items():
        im = Image.open(HERE / "set" / name).convert("RGB")
        hyp = run(flatten(im) if use_flatten else im)
        R, H = norm(ref), norm(hyp)
        ok, tot = tajik_hits(R, H)
        cond = name.split("_", 2)[2][:-4]
        for key in ("ALL", cond):
            g = groups[key]
            g[0] += lev(R, H) / len(R)
            g[1] += 1
            g[2] += ok
            g[3] += tot
    print(f"{engine}{' +flatten' if use_flatten else ''}: {time.time() - t0:.0f}s")
    for key, (c, n, ok, tot) in sorted(groups.items()):
        print(f"  {key:12s} CER {c / n * 100:5.1f}%   таджикские буквы {ok / tot * 100:5.1f}%")


if __name__ == "__main__":
    main()
