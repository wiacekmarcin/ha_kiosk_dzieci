#!/usr/bin/env python3
"""Kolorowanki: własne rysunki konturowe (czarne linie na białym tle) w klimacie motywów
Pokemon, Minecraft i Spidey - to nie są oficjalne postacie, tylko proste rysunki w tym
stylu (stworki, klockowy świat, pająki). Każdy rysunek to SVG składany w kodzie,
renderowany przez rsvg-convert do PNG 600 x 600 w dzieci/coloring/pages, plus
katalog.json (motyw, tytuł, plik).

Użycie: python3 tools/make_coloring.py   (wymaga rsvg-convert z librsvg2-bin)
"""
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dzieci" / "coloring" / "pages"
SIZE = 600
STROKE = 7


def svg(body: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIZE} {SIZE}" '
            f'width="{SIZE}" height="{SIZE}"><rect width="{SIZE}" height="{SIZE}" fill="white"/>'
            f'<g fill="white" stroke="black" stroke-width="{STROKE}" stroke-linejoin="round" '
            f'stroke-linecap="round">{body}</g></svg>')


def circle(x, y, r):
    return f'<circle cx="{x}" cy="{y}" r="{r}"/>'


def ellipse(x, y, rx, ry, rot=0):
    return f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="{ry}" transform="rotate({rot} {x} {y})"/>'


def rect(x, y, w, h, r=0):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}"/>'


def poly(points):
    return '<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in points) + '"/>'


def path(d, fill="white"):
    return f'<path d="{d}" fill="{fill}"/>'


def line(x1, y1, x2, y2):
    return f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" fill="none"/>'


def star(x, y, r, n=5):
    pts = []
    for i in range(n * 2):
        a = -math.pi / 2 + i * math.pi / n
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    return poly(pts)


def eye(x, y, r):
    return circle(x, y, r) + f'<circle cx="{x + r * 0.25}" cy="{y - r * 0.2}" r="{r * 0.45}" fill="black"/>'


# --- motyw Pokemon: kula i stworki ---------------------------------------------------------
def kula():
    b = star(80, 90, 40) + star(520, 100, 34) + star(510, 520, 40) + star(95, 510, 30)
    b += circle(300, 300, 210)
    b += line(90, 282, 510, 282) + line(90, 318, 510, 318)
    b += circle(300, 300, 62) + circle(300, 300, 32)
    b += path("M175 170 Q205 130 255 118", fill="none")
    return b


def chomik():
    b = poly([(395, 410), (470, 380), (440, 340), (520, 300), (490, 270), (555, 220),
              (470, 255), (500, 290), (420, 320), (450, 355), (380, 380)])     # ogon-błyskawica
    b += ellipse(215, 150, 32, 95, -25) + ellipse(385, 150, 32, 95, 25)       # uszy
    b += path("M190 85 L225 130 L250 100 Z") + path("M410 85 L375 130 L350 100 Z")
    b += ellipse(300, 430, 150, 120)                                           # tułów
    b += ellipse(300, 445, 85, 70)                                             # brzuszek
    b += circle(300, 265, 120)                                                 # głowa
    b += eye(255, 245, 22) + eye(345, 245, 22)
    b += circle(225, 300, 24) + circle(375, 300, 24)                           # policzki
    b += path("M285 300 Q300 315 315 300", fill="none")
    b += path("M270 320 Q300 350 330 320", fill="none")
    b += ellipse(230, 545, 45, 22) + ellipse(370, 545, 45, 22)                 # łapki
    b += ellipse(170, 420, 25, 45, 30) + ellipse(430, 420, 25, 45, -30)
    return b


def jaszczurka():
    b = path("M380 440 Q500 470 520 360 Q530 300 500 260", fill="none")       # ogon
    b += path("M500 260 Q470 200 505 140 Q520 190 545 170 Q560 230 520 262 Z")  # płomień
    b += path("M505 190 Q495 220 515 245 Q530 225 520 205 Z")
    b += ellipse(300, 420, 110, 130)                                           # tułów
    b += ellipse(300, 440, 65, 90)                                             # brzuch
    for y in (395, 430, 465, 500):
        b += line(245, y, 355, y)
    b += ellipse(300, 210, 115, 100)                                           # głowa
    b += eye(255, 195, 24) + eye(345, 195, 24)
    b += path("M250 255 Q300 290 350 255", fill="none")
    b += ellipse(200, 400, 30, 60, 35) + ellipse(400, 400, 30, 60, -35)         # łapki
    b += ellipse(240, 555, 50, 25) + ellipse(360, 555, 50, 25)
    return b


def zolw():
    b = ellipse(110, 330, 70, 55)                                              # głowa
    b += eye(85, 315, 16) + path("M60 355 Q85 372 110 352", fill="none")
    b += ellipse(200, 470, 40, 55, 20) + ellipse(400, 470, 40, 55, -20)       # nogi
    b += ellipse(470, 380, 45, 20, -20)                                        # ogonek
    b += path("M150 400 Q150 180 300 180 Q450 180 450 400 Z")                  # skorupa
    b += rect(140, 390, 320, 40, 18)
    cx, cy = 300, 300
    hexa = [(cx + 55 * math.cos(math.radians(a)), cy + 55 * math.sin(math.radians(a)))
            for a in range(0, 360, 60)]
    b += poly(hexa)
    for (x, y) in hexa:
        dx, dy = x - cx, y - cy
        b += line(x, y, cx + dx * 2.2, cy + dy * 2.0)
    return b


# --- motyw Minecraft: klockowy świat -----------------------------------------------------------
def grid(x, y, cols, rows, k):
    return "".join(rect(x + c * k, y + r * k, k, k) for r in range(rows) for c in range(cols))


def dom():
    b = rect(460, 40, 90, 90)                                                  # słońce
    b += grid(0, 520, 15, 2, 40)                                               # ziemia
    b += "".join(rect(140 + c * 40, 300 + r * 44, 40, 44)                     # ściana z bloków
                 for r in range(5) for c in range(8))
    steps = [(120, 300), (120, 270), (160, 270), (160, 240), (200, 240), (200, 210),
             (240, 210), (240, 180), (360, 180), (360, 210), (400, 210), (400, 240),
             (440, 240), (440, 270), (480, 270), (480, 300)]
    b += poly(steps)                                                           # dach
    b += rect(272, 388, 64, 132) + circle(322, 455, 6)                         # drzwi
    b += rect(170, 340, 70, 60) + line(205, 340, 205, 400) + line(170, 370, 240, 370)
    b += rect(370, 340, 70, 60) + line(405, 340, 405, 400) + line(370, 370, 440, 370)
    return b


def swinka():
    b = rect(120, 250, 360, 200)                                               # tułów
    for x in (140, 210, 340, 410):
        b += rect(x, 450, 55, 80)                                              # nogi
    b += rect(40, 170, 180, 180)                                               # głowa
    b += rect(70, 270, 100, 55) + rect(90, 285, 18, 25) + rect(132, 285, 18, 25)  # ryjek
    b += rect(60, 200, 40, 40) + rect(150, 200, 40, 40)                        # oczy
    b += rect(78, 218, 22, 22) + rect(168, 218, 22, 22)
    b += rect(480, 280, 30, 30)                                                # ogonek
    b += grid(300, 290, 3, 2, 40)                                              # łaty
    return b


def kilof():
    k = 30
    pix = ["....HHHHHH......", "..HHHHHHHHHH....", ".HHH......HHH...", "HH....SS....HH..",
           "H.....SS.....H..", "......SS........", "......SS........", "......SS........",
           "......SS........", "......SS........", "......SS........", "......SS........",
           "......SS........", "......SS........", ".....SSSS.......", "................"]
    b = ""
    for r, row in enumerate(pix):
        for c, ch in enumerate(row):
            if ch != ".":
                b += rect(60 + c * k, 60 + r * k, k, k)
    return b


def drzewo():
    b = grid(0, 520, 15, 2, 40)
    b += grid(260, 340, 2, 5, 40)                                              # pień
    b += grid(160, 140, 7, 2, 40) + grid(200, 60, 5, 2, 40) + grid(160, 220, 7, 3, 40)
    b += grid(440, 400, 2, 3, 40)                                              # krzak
    b += rect(60, 60, 70, 40) + rect(90, 40, 70, 40)                           # chmurka
    return b


# --- motyw Spidey: pająki i pajęczyny --------------------------------------------------------
def web(cx, cy, rmax, spokes=12, rings=5):
    b = ""
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        b += line(cx, cy, cx + rmax * math.cos(a), cy + rmax * math.sin(a))
    for k in range(1, rings + 1):
        r = rmax * k / rings
        d = ""
        for i in range(spokes + 1):
            a1, a2 = 2 * math.pi * i / spokes, 2 * math.pi * (i + 1) / spokes
            x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
            x2, y2 = cx + r * math.cos(a2), cy + r * math.sin(a2)
            mx, my = cx + r * 0.88 * math.cos((a1 + a2) / 2), cy + r * 0.88 * math.sin((a1 + a2) / 2)
            d += (f"M{x1:.1f} {y1:.1f} " if i == 0 else "") + f"Q{mx:.1f} {my:.1f} {x2:.1f} {y2:.1f} "
        b += path(d, fill="none")
    return b


def spider(x, y, s):
    b = ""
    for side in (-1, 1):
        for i, a in enumerate((-40, -10, 20, 50)):
            r = math.radians(a)
            kx, ky = x + side * s * 1.3 * math.cos(r), y + s * 1.1 * math.sin(r) - s * 0.5
            b += path(f"M{x:.1f} {y:.1f} Q{kx:.1f} {ky - s * 0.6:.1f} "
                      f"{x + side * s * 2.0 * math.cos(r):.1f} {y + s * 1.6 * math.sin(r) + s * 0.4:.1f}",
                      fill="none")
    b += ellipse(x, y + s * 0.5, s * 0.8, s * 0.95) + circle(x, y - s * 0.55, s * 0.55)
    b += eye(x - s * 0.22, y - s * 0.62, s * 0.18) + eye(x + s * 0.22, y - s * 0.62, s * 0.18)
    return b


def pajeczyna():
    b = web(300, 270, 250)
    b += line(300, 270, 300, 400) + spider(300, 450, 60)
    return b


def maska():
    b = ellipse(300, 300, 200, 250)
    cx, cy = 300, 330
    for a in range(0, 360, 30):
        r = math.radians(a)
        b += line(cx, cy, cx + 240 * math.cos(r), cy + 290 * math.sin(r))
    for k in (70, 135, 200):
        b += path(f"M{cx - k} {cy} Q{cx} {cy - k * 1.35} {cx + k} {cy} Q{cx} {cy + k * 1.35} {cx - k} {cy}",
                  fill="none")
    b = f'<clipPath id="m"><ellipse cx="300" cy="300" rx="200" ry="250"/></clipPath>' \
        f'{ellipse(300, 300, 200, 250)}<g clip-path="url(#m)">{b}</g>' \
        f'<ellipse cx="300" cy="300" rx="200" ry="250" fill="none"/>'
    b += path("M150 250 Q170 170 270 230 Q260 320 160 300 Z")                 # oczy
    b += path("M450 250 Q430 170 330 230 Q340 320 440 300 Z")
    return b


def miasto():
    b = circle(480, 100, 55)                                                  # księżyc
    blds = [(20, 260, 110, 340), (140, 180, 120, 420), (270, 300, 90, 300),
            (370, 220, 110, 380), (490, 330, 100, 270)]
    for x, y, w, h in blds:
        b += rect(x, y, w, h)
        for wy in range(y + 25, 560, 60):
            for wx in range(x + 18, x + w - 30, 40):
                b += rect(wx, wy, 22, 30)
    b += line(0, 0, 200, 140) + line(200, 140, 200, 175)
    b += spider(200, 170, 22)
    return b


def pajak():
    b = web(110, 110, 100, spokes=8, rings=3)
    b += spider(320, 330, 120)
    b += path("M270 300 Q320 340 370 300", fill="none")
    return b


PAGES = [
    ("pokemon", "Kula stworków", "kula", kula),
    ("pokemon", "Elektryczny chomik", "chomik", chomik),
    ("pokemon", "Ognista jaszczurka", "jaszczurka", jaszczurka),
    ("pokemon", "Wodny żółwik", "zolw", zolw),
    ("minecraft", "Dom z klocków", "dom", dom),
    ("minecraft", "Klockowa świnka", "swinka", swinka),
    ("minecraft", "Kilof", "kilof", kilof),
    ("minecraft", "Klockowe drzewo", "drzewo", drzewo),
    ("spidey", "Pajęczyna", "pajeczyna", pajeczyna),
    ("spidey", "Maska bohatera", "maska", maska),
    ("spidey", "Miasto nocą", "miasto", miasto),
    ("spidey", "Wesoły pająk", "pajak", pajak),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = []
    for theme, title, name, draw in PAGES:
        src = Path(f"/tmp/kol_{name}.svg")
        src.write_text(svg(draw()), encoding="utf-8")
        subprocess.run(["rsvg-convert", "-w", str(SIZE), "-h", str(SIZE), "-b", "white",
                        str(src), "-o", str(OUT / f"{name}.png")], check=True)
        src.unlink()
        catalog.append({"theme": theme, "title": title, "file": f"{name}.png"})
    (OUT / "katalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    print(f"COLORING_OK {len(catalog)} kolorowanek w {OUT}")


if __name__ == "__main__":
    main()
