"""Generate app/web/static/img/hero.svg: a sunset valley in the Tajik mountains (pure SVG).

uv run python scripts/make_hero.py app/web/static/img/hero.svg
"""

# ruff: noqa: E501  (SVG markup reads better on one line)
import math
import random
import sys

W, H = 1600, 1000
rnd = random.Random(7)


def ridge(x0, x1, y_at, rough, step=8, seed=0):
    """Ridge line: base profile y_at(x) + fractal noise."""
    r = random.Random(seed)
    xs = list(range(x0, x1 + step, step))
    # 1D fractal noise via summed sines with random phases
    octaves = [(r.uniform(0, 6.28), f, a) for f, a in ((0.004, 1.0), (0.011, 0.5), (0.027, 0.25), (0.06, 0.12))]
    pts = []
    for x in xs:
        n = sum(a * math.sin(x * f + p) for p, f, a in octaves)
        pts.append((x, y_at(x) + n * rough))
    return pts


def path(pts, close_to=None):
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    if close_to is not None:
        d += f" L{pts[-1][0]:.1f},{close_to} L{pts[0][0]:.1f},{close_to} Z"
    return d


def peak(x, cx, h, w, sharp=1.0):
    t = abs(x - cx) / w
    return -h * max(0.0, 1 - t) ** sharp


def snow(pts, snow_y, seed):
    """Polygon between the ridge and a jagged snowline for points above snow_y."""
    r = random.Random(seed)
    polys, cur = [], []
    for x, y in pts:
        if y < snow_y:
            cur.append((x, y))
        elif cur:
            polys.append(cur)
            cur = []
    if cur:
        polys.append(cur)
    out = []
    for poly in polys:
        if len(poly) < 3:
            continue
        lower = []
        for x, y in reversed(poly):
            depth = min(snow_y - y, 26 + r.uniform(-12, 30))
            lower.append((x + r.uniform(-3, 3), y + max(4, depth) * r.uniform(0.6, 1.25)))
        out.append(path(poly + lower) + " Z")
    return out


def strokes(pts, n, y_max, seed, color, op, lo=30, hi=120):
    """Rock striation: thin lines falling from the ridge."""
    r = random.Random(seed)
    s = []
    for _ in range(n):
        x, y = pts[r.randrange(len(pts))]
        if y > y_max:
            continue
        ln = r.uniform(lo, hi)
        dx = r.uniform(-12, 12)
        s.append(f'<path d="M{x:.0f},{y + 4:.0f} q{dx / 2:.0f},{ln / 2:.0f} {dx:.0f},{ln:.0f}" '
                 f'stroke="{color}" stroke-opacity="{op * r.uniform(.4, 1):.2f}" '
                 f'stroke-width="{r.uniform(1, 3.5):.1f}" fill="none" stroke-linecap="round"/>')
    return s


def tree(x, y, s, seed):
    r = random.Random(seed)
    parts = [f'<rect x="{x - 2 * s:.0f}" y="{y - 10 * s:.0f}" width="{4 * s:.0f}" height="{12 * s:.0f}" fill="#3b2a22"/>']
    blobs = [(0, -26, 16), (-11, -18, 12), (11, -19, 12), (-5, -34, 11), (6, -31, 11)]
    for dx, dy, rr in blobs:
        parts.append(f'<circle cx="{x + dx * s:.0f}" cy="{y + dy * s:.0f}" r="{rr * s:.0f}" fill="url(#treeG)"/>')
    for _ in range(5):
        parts.append(f'<circle cx="{x + r.uniform(2, 14) * s:.0f}" cy="{y + r.uniform(-38, -16) * s:.0f}" '
                     f'r="{r.uniform(3, 6) * s:.0f}" fill="#e09a52" opacity=".55"/>')
    return "".join(parts)


def grass_and_flowers(y_top, y_bot, count, size, seed, blur=None):
    r = random.Random(seed)
    palette = ["#8f6fd1", "#a98be0", "#7c5cc4", "#f4f1ea", "#ffffff", "#f07a2c", "#ff8f3a", "#e85d1f",
               "#f2c14e", "#b9a2f0"]
    weights = [3, 2, 3, 3, 2, 3, 2, 2, 1, 1]
    blades, flowers = [], []
    for _ in range(int(count * 1.6)):
        x = r.uniform(-20, W + 20)
        y = r.uniform(y_top, y_bot)
        k = (y - y_top) / (y_bot - y_top)
        ln = size * (8 + 26 * k) * r.uniform(.6, 1.3)
        lean = r.uniform(-.5, .5) * ln
        col = r.choice(["#3f6b2f", "#4f7d36", "#5f8f3c", "#2f5526", "#6f9a45"])
        blades.append(f'<path d="M{x:.0f},{y:.0f} q{lean / 3:.0f},{-ln / 2:.0f} {lean:.0f},{-ln:.0f}" '
                      f'stroke="{col}" stroke-width="{size * (1 + 2 * k):.1f}" fill="none" stroke-linecap="round"/>')
    for _ in range(count):
        x = r.uniform(-20, W + 20)
        y = r.uniform(y_top, y_bot)
        k = (y - y_top) / (y_bot - y_top)
        rr = size * (1.6 + 7 * k * k) * r.uniform(.7, 1.3)
        col = r.choices(palette, weights)[0]
        stem = rr * r.uniform(1.5, 4)
        flowers.append(f'<path d="M{x:.0f},{y:.0f} v{stem:.0f}" stroke="#355d2a" stroke-width="{max(1, rr / 4):.1f}"/>')
        if rr > 7 and r.random() < .7:  # petals
            petals = "".join(
                f'<ellipse cx="{x + math.cos(a) * rr * .6:.1f}" cy="{y + math.sin(a) * rr * .45:.1f}" '
                f'rx="{rr * .55:.1f}" ry="{rr * .38:.1f}" fill="{col}" '
                f'transform="rotate({math.degrees(a):.0f} {x + math.cos(a) * rr * .6:.1f} {y + math.sin(a) * rr * .45:.1f})"/>'
                for a in [i * 2 * math.pi / 5 + r.uniform(0, 1) for i in range(5)])
            flowers.append(petals + f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr * .22:.1f}" fill="#f6c453"/>')
        else:
            flowers.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rr:.1f}" ry="{rr * .75:.1f}" fill="{col}"/>')
    g = "".join(blades + flowers)
    return f'<g filter="url(#{blur})">{g}</g>' if blur else f"<g>{g}</g>"


def main(out):
    hz = 640  # horizon
    s = []
    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice">')
    s.append("""<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#bfcad6"/><stop offset=".35" stop-color="#dcdcde"/>
 <stop offset=".58" stop-color="#efdcd2"/><stop offset=".68" stop-color="#f6cdb7"/><stop offset="1" stop-color="#f9d9c2"/>
</linearGradient>
<radialGradient id="sun" cx="800" cy="610" r="520" gradientUnits="userSpaceOnUse">
 <stop offset="0" stop-color="#fff3e2" stop-opacity=".95"/><stop offset=".35" stop-color="#ffd9bd" stop-opacity=".45"/>
 <stop offset="1" stop-color="#ffd9bd" stop-opacity="0"/>
</radialGradient>
<linearGradient id="far" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#c7b3bd"/><stop offset="1" stop-color="#e6c9bf"/>
</linearGradient>
<linearGradient id="rockL" x1="0" y1="0" x2="1" y2="0">
 <stop offset="0" stop-color="#9b8d8f"/><stop offset=".45" stop-color="#d9c4bb"/><stop offset=".7" stop-color="#c2aaa6"/><stop offset="1" stop-color="#a7969a"/>
</linearGradient>
<linearGradient id="rockShade" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".6" stop-color="#d7b59a" stop-opacity=".25"/><stop offset="1" stop-color="#6d7a4a" stop-opacity=".7"/>
</linearGradient>
<linearGradient id="rockR" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#c9aeb0"/><stop offset=".5" stop-color="#b59ca0"/><stop offset="1" stop-color="#8e8a72"/>
</linearGradient>
<linearGradient id="slopeR" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#7f8d4f"/><stop offset="1" stop-color="#4f6e35"/>
</linearGradient>
<linearGradient id="hillGold" x1="0" y1="0" x2="1" y2="1">
 <stop offset="0" stop-color="#c9b14f"/><stop offset=".45" stop-color="#a6a845"/><stop offset="1" stop-color="#6f8c3a"/>
</linearGradient>
<linearGradient id="hillMid" x1="0" y1="0" x2="1" y2="0">
 <stop offset="0" stop-color="#7e9a3e"/><stop offset=".5" stop-color="#b6ac4c"/><stop offset="1" stop-color="#5f853a"/>
</linearGradient>
<linearGradient id="meadow" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#6f8f3f"/><stop offset=".4" stop-color="#4c7432"/><stop offset="1" stop-color="#2c4d24"/>
</linearGradient>
<linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
 <stop offset="0" stop-color="#f7d8c4" stop-opacity="0"/><stop offset="1" stop-color="#f7d8c4" stop-opacity=".55"/>
</linearGradient>
<radialGradient id="treeG" cx=".35" cy=".3" r=".8">
 <stop offset="0" stop-color="#b8693a"/><stop offset=".55" stop-color="#7a3f2a"/><stop offset="1" stop-color="#4d2b22"/>
</radialGradient>
<linearGradient id="glow" x1="0" y1="0" x2="1" y2="0">
 <stop offset="0" stop-color="#ffcf8a" stop-opacity="0"/><stop offset=".5" stop-color="#ffcf8a" stop-opacity=".35"/><stop offset="1" stop-color="#ffcf8a" stop-opacity="0"/>
</linearGradient>
<filter id="b1"><feGaussianBlur stdDeviation="1.2"/></filter>
<filter id="b3"><feGaussianBlur stdDeviation="3.5"/></filter>
<filter id="b6"><feGaussianBlur stdDeviation="7"/></filter>
<filter id="soft"><feGaussianBlur stdDeviation="18"/></filter>
</defs>""")
    s.append(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
    s.append(f'<rect width="{W}" height="{H}" fill="url(#sun)"/>')

    # far range, hazy
    far = ridge(-20, W + 20, lambda x: hz - 70 + peak(x, 1120, 120, 260, 1.3) + peak(x, 1380, 90, 220)
                + peak(x, 560, 60, 260), 22, seed=1)
    s.append(f'<path d="{path(far, H)}" fill="url(#far)" opacity=".75"/>')
    s.extend(f'<path d="{d}" fill="#fbf1ec" opacity=".7"/>' for d in snow(far, hz - 150, 11))
    s.append(f'<rect y="{hz - 200}" width="{W}" height="300" fill="url(#haze)"/>')

    # right mountains (mid)
    rm = ridge(560, W + 20, lambda x: hz + 60 - min(80, max(0, x - 600) * .4) + peak(x, 1250, 170, 330, 1.2) + peak(x, 1520, 230, 260, 1.1)
               + peak(x, 1050, 50, 200), 16, seed=2)
    s.append(f'<path d="{path(rm, H)}" fill="url(#rockR)"/>')
    s.extend(f'<path d="{d}" fill="#f6ece8" opacity=".9"/>' for d in snow(rm, hz - 165, 12))
    s.append(f'<path d="{path(rm, H)}" fill="url(#rockShade)"/>')
    # right green slope
    rs = ridge(560, W + 20, lambda x: hz + 40 - max(0, (x - 1000)) * .42 + peak(x, 1480, 40, 120), 12, seed=3)
    s.append(f'<path d="{path(rs, H)}" fill="url(#slopeR)"/>')
    s.extend(strokes(rs, 50, H, 33, "#2f4a22", .25, 10, 35))
    # scattered rocks on right slope
    r = random.Random(5)
    for _ in range(26):
        x = r.uniform(1150, 1600)
        base = [y for xx, y in rs if abs(xx - x) < 6]
        if not base:
            continue
        y = base[0] + r.uniform(20, 200)
        w_ = r.uniform(6, 18)
        s.append(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{w_:.0f}" ry="{w_ * .6:.0f}" fill="#d9d2c7"/>'
                 f'<ellipse cx="{x + 2:.0f}" cy="{y + 3:.0f}" rx="{w_:.0f}" ry="{w_ * .35:.0f}" fill="#7f8164" opacity=".5"/>')

    # left massif: tall rocky peaks
    lm = ridge(-20, 640, lambda x: hz + 40 + peak(x, 190, 430, 230, .95) + peak(x, 40, 330, 180, 1.0)
               + peak(x, 340, 300, 200, 1.1) + peak(x, 470, 160, 170), 18, seed=4)
    lm = [(x, min(y, hz + 120)) for x, y in lm]
    s.append(f'<path d="{path(lm, H)}" fill="url(#rockL)"/>')
    s.extend(strokes(lm, 160, hz - 40, 44, "#7a6c70", .4, 20, 110))
    s.extend(strokes(lm, 90, hz - 120, 45, "#fff4ec", .3, 20, 80))
    s.extend(f'<path d="{d}" fill="#fbf4f0" opacity=".85"/>' for d in snow(lm, hz - 330, 13))
    s.append(f'<path d="{path(lm, H)}" fill="url(#rockShade)"/>')

    # warm light band across the valley
    s.append(f'<rect y="{hz - 60}" width="{W}" height="140" fill="url(#glow)" filter="url(#soft)"/>')

    # golden left hill
    gh = ridge(-20, 900, lambda x: hz + 20 + x * .05 + peak(x, 120, 150, 380) - 30, 10, seed=6)
    s.append(f'<path d="{path(gh, H)}" fill="url(#hillGold)"/>')
    s.extend(strokes(gh, 70, H, 66, "#5d7a31", .25, 8, 30))
    # mid valley hills
    mh = ridge(-20, W + 20, lambda x: hz + 85 + 18 * math.sin(x / 140) - peak(x, 1000, -40, 300), 8, seed=7)
    s.append(f'<path d="{path(mh, H)}" fill="url(#hillMid)"/>')
    # shadow band on mid hills
    mh2 = ridge(-20, W + 20, lambda x: hz + 120 + 14 * math.sin(x / 110 + 1), 6, seed=8)
    s.append(f'<path d="{path(mh2, H)}" fill="#5c7e35" opacity=".55"/>')

    # house on the golden hill (flat roof, Pamiri style simplified)
    hx, hy = 210, hz + 64
    s.append(f'<g><rect x="{hx}" y="{hy}" width="110" height="46" fill="#eae3d9"/>'
             f'<rect x="{hx + 110}" y="{hy}" width="34" height="46" fill="#bdb3a7"/>'
             f'<polygon points="{hx - 8},{hy + 2} {hx + 30},{hy - 30} {hx + 152},{hy - 30} {hx + 150},{hy + 2}" fill="#3c3a40"/>'
             f'<rect x="{hx + 20}" y="{hy + 14}" width="14" height="16" fill="#6a5d55"/>'
             f'<rect x="{hx + 62}" y="{hy + 14}" width="14" height="16" fill="#6a5d55"/>'
             f'<rect x="{hx}" y="{hy + 46}" width="146" height="5" fill="#556b2f" opacity=".6"/></g>')

    # trees
    for tx, ty, ts, sd in [(470, hz + 110, 1.9, 1), (520, hz + 115, 1.4, 2), (1030, hz + 70, 1.0, 3),
                           (1165, hz + 105, 2.6, 4), (900, hz + 95, .8, 5), (360, hz + 120, 1.1, 6)]:
        s.append(tree(tx, ty, ts, sd))

    # meadow
    mead = ridge(-20, W + 20, lambda x: hz + 150 + 10 * math.sin(x / 200), 6, seed=9)
    s.append(f'<path d="{path(mead, H)}" fill="url(#meadow)"/>')
    s.append(grass_and_flowers(hz + 150, hz + 230, 260, .6, 21, "b1"))
    s.append(grass_and_flowers(hz + 200, hz + 300, 200, 1.3, 22))
    s.append(grass_and_flowers(hz + 280, H + 40, 110, 2.6, 23, "b3"))

    s.append("</svg>")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(s))


if __name__ == "__main__":
    main(sys.argv[1])
