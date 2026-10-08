"""Генератор печатных файлов и мокапов футболок Т-Софт.

Все размеры в миллиметрах. Текст переводится в кривые (HarfBuzz + fontTools),
поэтому печатные SVG не зависят от установленных шрифтов.

    pip install fonttools uharfbuzz
    python3 src/build.py
"""
import re
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PRINT = ROOT / "print"

# Палитра из brand tokens v2.0
NAVY = "#0A2646"
BLUE = "#015AFD"
BLUE_LIGHT = "#89B2FF"
WHITE = "#FFFFFF"


# ---------------------------------------------------------------- текст → кривые

class Font:
    _cache = {}

    def __new__(cls, name):
        if name not in cls._cache:
            obj = super().__new__(cls)
            path = SRC / "fonts" / f"{name}.ttf"
            obj.tt = TTFont(path)
            obj.upem = obj.tt["head"].unitsPerEm
            obj.glyphs = obj.tt.getGlyphSet()
            obj.order = obj.tt.getGlyphOrder()
            face = hb.Face(path.read_bytes())
            obj.hb = hb.Font(face)
            obj.hb.scale = (obj.upem, obj.upem)
            cls._cache[name] = obj
        return cls._cache[name]

    def shape(self, s, features):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, features)
        return buf.glyph_infos, buf.glyph_positions


def measure(s, font, size, tracking=0.0, features=None):
    f = Font(font)
    infos, pos = f.shape(s, features or {"kern": True})
    k = size / f.upem
    return sum(p.x_advance for p in pos) * k + tracking * size * (len(infos) - 1)


def text(s, font, size, x, y, fill, anchor="start", tracking=0.0, features=None):
    """Строка текста в кривых. y — базовая линия, size — кегль в мм."""
    f = Font(font)
    infos, pos = f.shape(s, features or {"kern": True})
    k = size / f.upem
    w = measure(s, font, size, tracking, features)
    cx = x - {"start": 0, "middle": w / 2, "end": w}[anchor]
    ds = []
    for info, p in zip(infos, pos):
        pen = SVGPathPen(f.glyphs, ntos=lambda v: f"{v:.2f}")
        tp = TransformPen(pen, (k, 0, 0, -k, cx + p.x_offset * k, y - p.y_offset * k))
        f.glyphs[f.order[info.codepoint]].draw(tp)
        d = pen.getCommands()
        if d:
            ds.append(d)
        cx += p.x_advance * k + tracking * size
    return f'<path fill="{fill}" d="{" ".join(ds)}"/>'


# ---------------------------------------------------------------- логотипы

def logo(name, x, y, width):
    """Вставка фирменного SVG без изменений геометрии и цвета."""
    svg = (SRC / "logo" / f"{name}.svg").read_text()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    body = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1)
    s = width / vb[2]
    return (f'<g transform="translate({x:.2f} {y:.2f}) scale({s:.6f}) '
            f'translate({-vb[0]} {-vb[1]})">{body}</g>'), vb[3] * s


def doc(w, h, body, title):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" '
            f'viewBox="0 0 {w} {h}">\n<title>{title}</title>\n{body}\n</svg>\n')


# ---------------------------------------------------------------- концепция A «Слоган»

def a_front():
    g, h = logo("tsoft-logo-ru-inverse", 0, 0, 100)
    return doc(100, round(h, 2), g, "A — грудь: логотип Т-Софт, 100 мм")


def a_back():
    W = 280
    icon, ih = logo("tsoft-icon-white", W / 2 - 18, 0, 36)
    size = 30
    l1, l2 = "Готовы до того,", "как случится."
    # кегль подбирается так, чтобы длинная строка заняла ширину макета
    size = size * W / measure(l1, "InterDisplay-Bold", size, -0.01)
    y1 = ih + 18 + size * 0.73
    y2 = y1 + size * 1.08
    parts = [
        icon,
        text(l1, "InterDisplay-Bold", size, W / 2, y1, WHITE, "middle", -0.01),
        text(l2, "InterDisplay-Bold", size, W / 2, y2, BLUE_LIGHT, "middle", -0.01),
    ]
    y3 = y2 + 36
    parts.append(f'<rect x="{W/2-20}" y="{y2+16}" width="40" height="1" fill="{BLUE_LIGHT}"/>')
    parts.append(text("КТК · OTS · VR-ТРЕНАЖЁРЫ · МАТЕМАТИЧЕСКИЕ МОДЕЛИ",
                      "Inter-SemiBold", 7.4, W / 2, y3, WHITE, "middle", 0.1))
    return doc(W, round(y3 + 2, 2), "\n".join(parts), "A — спина: слоган")


# ---------------------------------------------------------------- концепция B «Схема»

def scheme(ox, oy):
    """Технологическая схема ректификации: Т-1 → К-1 → Х-1 → Е-1 → Н-1/Н-2."""
    L, Ls = 1.2, 0.8
    st = f'fill="none" stroke="{BLUE_LIGHT}" stroke-linejoin="round" stroke-linecap="round"'
    el = []

    def line(pts, w=L, dash=None):
        d = " ".join(f"{'M' if i == 0 else 'L'}{x} {y}" for i, (x, y) in enumerate(pts))
        da = f' stroke-dasharray="{dash}"' if dash else ""
        el.append(f'<path {st} stroke-width="{w}"{da} d="{d}"/>')

    def arrow(x, y, direction):
        a = 4.5
        pts = {"r": [(x, y), (x - a, y - a / 2), (x - a, y + a / 2)],
               "d": [(x, y), (x - a / 2, y - a), (x + a / 2, y - a)],
               "l": [(x, y), (x + a, y - a / 2), (x + a, y + a / 2)],
               "u": [(x, y), (x - a / 2, y + a), (x + a / 2, y + a)]}[direction]
        el.append(f'<path fill="{BLUE_LIGHT}" d="M{pts[0][0]} {pts[0][1]} '
                  f'L{pts[1][0]} {pts[1][1]} L{pts[2][0]} {pts[2][1]}Z"/>')

    def valve(x, y, vertical=False):
        s = 5
        if vertical:
            d = f"M{x-s/2} {y-s} L{x+s/2} {y-s} L{x-s/2} {y+s} L{x+s/2} {y+s}Z"
        else:
            d = f"M{x-s} {y-s/2} L{x-s} {y+s/2} L{x+s} {y-s/2} L{x+s} {y+s/2}Z"
        el.append(f'<path fill="{NAVY}" stroke="{BLUE_LIGHT}" stroke-width="{Ls}" '
                  f'stroke-linejoin="round" d="{d}"/>')

    def pump(cx, cy):
        r = 11
        el.append(f'<circle {st} stroke-width="{L}" cx="{cx}" cy="{cy}" r="{r}"/>')
        el.append(f'<path {st} stroke-width="{Ls}" d="M{cx-6} {cy-7} L{cx+8} {cy} L{cx-6} {cy+7}Z"/>')

    def instrument(cx, cy, tag, num):
        el.append(f'<circle fill="{NAVY}" stroke="{BLUE_LIGHT}" stroke-width="{Ls}" '
                  f'cx="{cx}" cy="{cy}" r="8.5"/>')
        el.append(f'<path stroke="{BLUE_LIGHT}" stroke-width="0.6" d="M{cx-8.5} {cy} H{cx+8.5}"/>')
        el.append(text(tag, "Inter-SemiBold", 3.8, cx, cy - 1.6, WHITE, "middle"))
        el.append(text(num, "Inter-Medium", 3.6, cx, cy + 5.2, BLUE_LIGHT, "middle",
                       features={"kern": True, "tnum": True}))

    def tag(s, x, y, anchor="middle"):
        el.append(text(s, "Inter-SemiBold", 6, x, y, WHITE, anchor))

    def stream(s, x, y, anchor="start"):
        el.append(text(s, "Inter-Medium", 4.6, x, y, BLUE_LIGHT, anchor))

    # линии потоков (рисуются первыми, аппараты сверху)
    line([(0, 140), (40, 140)])                                   # сырьё → Т-1
    line([(80, 140), (120, 140)])                                 # Т-1 → К-1
    line([(142, 20), (142, 6), (215, 6), (215, 15)])              # шлемовая линия → Х-1
    line([(215, 41), (215, 60)])                                  # Х-1 → Е-1
    line([(240, 84), (240, 119)])                                 # Е-1 → Н-1
    line([(240, 141), (240, 160), (276, 160)])                    # Н-1 → дистиллят
    line([(240, 160), (172, 160), (172, 45), (164, 45)])          # орошение в К-1
    line([(142, 200), (142, 214), (189, 214)])                    # куб К-1 → Н-2
    line([(211, 214), (276, 214)])                                # Н-2 → остаток
    arrow(280, 160, "r"); arrow(280, 214, "r"); arrow(120, 140, "r"); arrow(164, 45, "l")

    # Т-1 — печь/подогреватель
    el.append(f'<rect {st} stroke-width="{L}" x="40" y="115" width="40" height="50" rx="2"/>')
    line([(40, 152), (48, 128), (56, 152), (64, 128), (72, 152), (80, 128)], Ls)

    # К-1 — колонна с тарелками
    el.append(f'<rect {st} stroke-width="{L}" x="120" y="20" width="44" height="180" rx="22"/>')
    for i, y in enumerate([44, 58, 72, 86, 140, 154, 168, 182]):
        x0, x1 = (120, 150) if i % 2 == 0 else (134, 164)
        line([(x0, y), (x1, y)], Ls)

    # Х-1 — конденсатор
    el.append(f'<circle {st} stroke-width="{L}" cx="215" cy="28" r="13"/>')
    line([(202, 28), (207, 21), (213, 35), (219, 21), (225, 35), (228, 28)], Ls)

    # Е-1 — рефлюксная ёмкость
    el.append(f'<rect {st} stroke-width="{L}" x="180" y="60" width="70" height="24" rx="12"/>')

    pump(240, 130)
    pump(200, 214)
    valve(100, 140)
    valve(172, 120, vertical=True)
    valve(258, 160)

    # КИП
    line([(120, 34), (106, 34)], 0.6, "2 1.6")
    instrument(97, 34, "PT", "101")
    line([(120, 186), (106, 186)], 0.6, "2 1.6")
    instrument(97, 186, "TT", "102")
    line([(250, 72), (262, 72)], 0.6, "2 1.6")
    instrument(270.5, 72, "LT", "103")

    # позиции и потоки
    tag("К-1", 142, 117)
    tag("Т-1", 60, 176)
    tag("Х-1", 236, 32, "start")
    tag("Е-1", 215, 74.2)
    tag("Н-1", 255, 128, "start")
    tag("Н-2", 200, 236)
    stream("Сырьё", 0, 134)
    stream("Дистиллят", 280, 154, "end")
    stream("Остаток", 280, 208, "end")

    return f'<g transform="translate({ox} {oy})">' + "\n".join(el) + "</g>"


def b_front():
    g, h = logo("tsoft-icon-white", 0, 0, 55)
    return doc(55, round(h, 2), g, "B — грудь: знак Т-Софт, 55 мм")


def b_back():
    W = 280
    parts = [text("МОДЕЛЬ  →  ЭМУЛЯЦИЯ  →  ОТРАБОТКА", "Inter-SemiBold", 7.6, W / 2, 7,
                  BLUE_LIGHT, "middle", 0.12)]
    parts.append(scheme(0, 24))
    parts.append(text("Модель, а не картинка.", "InterDisplay-Bold", 21, W / 2, 292, WHITE, "middle", -0.01))
    g, h = logo("tsoft-logo-ru-inverse", W / 2 - 34, 306, 68)
    parts.append(g)
    return doc(W, round(306 + h, 2), "\n".join(parts), "B — спина: технологическая схема")


# ---------------------------------------------------------------- концепция C «Журнал тренажёра»

def c_front():
    g, h = logo("tsoft-logo-ru-color", 0, 0, 100)
    return doc(100, round(h, 2), g, "C — грудь: логотип Т-Софт, 100 мм")


def c_back():
    W = 280
    tnum = {"kern": True, "tnum": True}
    p = [text("ЖУРНАЛ ТРЕНАЖЁРА · СЦЕНАРИЙ 07", "Inter-SemiBold", 7.4, 0, 7, BLUE, "start", 0.12)]
    p.append(f'<rect x="0" y="15" width="{W}" height="0.8" fill="{NAVY}"/>')
    rows = [
        ("08:00:00", "Пуск сценария", "старт"),
        ("08:12:47", "Рост давления в колонне К-1", "обнаружено"),
        ("08:13:05", "Срабатывание блокировки", "отработано"),
        ("08:14:22", "Переход на резервный насос", "выполнено"),
        ("08:19:40", "Режим стабилизирован", "норма"),
    ]
    y = 37
    for t, ev, status in rows:
        p.append(text(t, "Inter-Medium", 9, 0, y, BLUE, "start", 0, tnum))
        p.append(text(ev, "Inter-Regular", 9, 56, y, NAVY))
        p.append(text(status, "Inter-SemiBold", 9, W, y, NAVY, "end"))
        y += 18
    p.append(f'<rect x="0" y="{y-5}" width="{W}" height="0.8" fill="{NAVY}"/>')
    # итог сценария
    y += 28
    p.append(f'<path fill="none" stroke="{BLUE}" stroke-width="5" stroke-linecap="round" '
             f'stroke-linejoin="round" d="M3 {y-11} L13 {y-1} L31 {y-22}"/>')
    size = 28 * (W - 44) / measure("Сценарий пройден", "InterDisplay-Bold", 28)
    p.append(text("Сценарий пройден", "InterDisplay-Bold", size, 44, y, NAVY))
    y += 32
    p.append(text("Готовы до того, как случится.", "InterDisplay-SemiBold", 14, 0, y, BLUE))
    return doc(W, round(y + 3, 2), "\n".join(p), "C — спина: журнал тренажёра")


# ---------------------------------------------------------------- мокап

# Силуэт футболки размера L (мм, вид спереди/сзади); полуобхват груди 520 мм.
SHIRT = ("M290 40 Q380 {neck} 470 40 L630 78 L748 252 L664 304 L640 266 "
         "L646 742 Q380 754 114 742 L120 266 L96 304 L12 252 L130 78Z")

CONCEPTS = [
    ("A", "Слоган", NAVY, "Тёмно-синяя футболка. Логотип на груди, слоган «Готовы до того, как случится» на спине.",
     "Конференции, выставки, подарки заказчикам", "2 цвета: белый, #89B2FF (+ #015AFD в знаке логотипа)"),
    ("B", "Схема", NAVY, "Знак на груди, на спине технологическая схема ректификации и ключевое сообщение «Модель, а не картинка».",
     "Команда разработки, инженеры, отраслевые мероприятия", "3 цвета: #89B2FF, белый, #015AFD"),
    ("C", "Журнал тренажёра", "#F4F6F9", "Белая футболка. На спине журнал событий учебного сценария, который закрывается строкой «Сценарий пройден».",
     "Внутренний мерч, тимбилдинги, хакатоны, стажёры", "2 цвета: #0A2646, #015AFD (+ #2B2A29 в логотипе)"),
]


def shirt(fabric, side, art, art_w, art_x, art_y):
    light = fabric != NAVY
    stroke = "#C9D1DC" if light else "#16365E"
    shade = "#E3E8EF" if light else "#071D37"
    neck = 112 if side == "front" else 64
    inner = f"M290 40 Q380 {neck} 470 40"
    return f"""<svg viewBox="0 0 760 780" xmlns="http://www.w3.org/2000/svg">
<path d="{SHIRT.format(neck=neck)}" fill="{fabric}" stroke="{stroke}" stroke-width="3" stroke-linejoin="round"/>
<path d="M130 78 L120 266 M630 78 L640 266" stroke="{shade}" stroke-width="3" fill="none"/>
<path d="{inner}" fill="none" stroke="{shade}" stroke-width="14"/>
<path d="{inner}" fill="none" stroke="{stroke}" stroke-width="2"/>
<image href="{art}" x="{art_x}" y="{art_y}" width="{art_w}"/>
</svg>"""


def mockup():
    cards = []
    for key, name, fabric, desc, use, colors in CONCEPTS:
        front = f"print/2026-10-08_tsoft-tshirt_{key}_front.svg"
        back = f"print/2026-10-08_tsoft-tshirt_{key}_back.svg"
        fw = 55 if key == "B" else 100
        cards.append(f"""<section class="card">
  <div class="kicker">КОНЦЕПЦИЯ {key}</div><h2>{name}</h2>
  <div class="pair">
    <figure>{shirt(fabric, "front", front, fw, 475 - fw / 2, 170)}<figcaption>Перед</figcaption></figure>
    <figure>{shirt(fabric, "back", back, 280, 240, 125)}<figcaption>Спина</figcaption></figure>
  </div>
  <p>{desc}</p>
  <dl><dt>Для чего</dt><dd>{use}</dd><dt>Цвета печати</dt><dd>{colors}</dd></dl>
</section>""")
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Футболки Т-Софт</title>
<style>
@font-face {{ font-family: Inter; font-weight: 400; src: url(src/fonts/Inter-Regular.ttf); }}
@font-face {{ font-family: Inter; font-weight: 600; src: url(src/fonts/Inter-SemiBold.ttf); }}
@font-face {{ font-family: "Inter Display"; font-weight: 700; src: url(src/fonts/InterDisplay-Bold.ttf); }}
:root {{ --navy: {NAVY}; --blue: {BLUE}; --grey: #E4E8EF; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #F5F7FA; color: var(--navy); font: 400 15px/1.5 Inter, "Segoe UI", sans-serif; }}
header {{ background: var(--navy); color: #fff; padding: 40px 48px; }}
header .kicker {{ color: #89B2FF; }}
h1 {{ font: 700 40px/1.1 "Inter Display", Inter, sans-serif; margin: 6px 0 8px; }}
header p {{ color: #B9C6D6; margin: 0; max-width: 760px; }}
main {{ padding: 32px 48px 48px; display: grid; gap: 28px; }}
.kicker {{ font-weight: 600; font-size: 12px; letter-spacing: .14em; color: var(--blue); }}
.card {{ background: #fff; border-radius: 16px; padding: 28px 32px; }}
h2 {{ font: 700 28px/1.2 "Inter Display", Inter, sans-serif; margin: 4px 0 16px; }}
.pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; background: var(--grey); border-radius: 12px; padding: 24px; }}
figure {{ margin: 0; text-align: center; }}
figure svg {{ width: 100%; height: auto; display: block; }}
figcaption {{ font-weight: 600; font-size: 13px; color: #5A6B82; margin-top: 6px; }}
dl {{ display: grid; grid-template-columns: 140px 1fr; gap: 4px 16px; margin: 12px 0 0; }}
dt {{ font-weight: 600; }} dd {{ margin: 0; }}
@media (max-width: 720px) {{ header, main {{ padding-left: 16px; padding-right: 16px; }} .pair {{ grid-template-columns: 1fr; }} dl {{ grid-template-columns: 1fr; }} }}
</style></head>
<body>
<header><div class="kicker">МЕРЧ · ФУТБОЛКИ · 2026</div><h1>Футболки Т-Софт</h1>
<p>Три концепции в фирменном стиле: палитра brand tokens v2.0, Inter, оригинальные файлы логотипа. Печатные файлы в папке print/ в масштабе 1:1, текст в кривых.</p></header>
<main>
{chr(10).join(cards)}
</main>
</body></html>
"""


# ---------------------------------------------------------------- сборка

ARTS = {
    "A_front": a_front, "A_back": a_back,
    "B_front": b_front, "B_back": b_back,
    "C_front": c_front, "C_back": c_back,
}

if __name__ == "__main__":
    PRINT.mkdir(exist_ok=True)
    for name, fn in ARTS.items():
        out = PRINT / f"2026-10-08_tsoft-tshirt_{name}.svg"
        out.write_text(fn())
        print(out.relative_to(ROOT), out.stat().st_size // 1024, "KB")
    (ROOT / "mockup.html").write_text(mockup())
    print("mockup.html")
