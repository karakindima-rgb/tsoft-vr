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
# Тональная краска для концепции 1: на тон светлее полотна, подбирается по пробнику.
# В палитру бренда не входит, это технологический цвет печати.
TONAL = "#1A3A62"


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


# ---------------------------------------------------------------- 1 «Тон в тон»

def s1_front():
    g, h = logo("tsoft-icon-white", 0, 0, 40)
    return doc(40, round(h, 2), g, "1 — грудь: знак, вышивка белой нитью, 40 мм")


def s1_back():
    W = 270
    lines = ["Готовы", "до того, как", "случится."]
    ref = max(measure(l, "InterDisplay-Bold", 10, -0.02) for l in lines)
    size = 10 * W / ref
    parts, y = [], size * 0.73
    for l in lines:
        parts.append(text(l, "InterDisplay-Bold", size, 0, y, TONAL, "start", -0.02))
        y += size * 0.98
    y += 4
    g, h = logo("tsoft-icon-white", 0, y, 22)
    parts.append(g)
    parts.append(text("КТК · OTS · VR-ТРЕНАЖЁРЫ", "Inter-SemiBold", 6.4, 30, y + h / 2 + 2.3,
                      BLUE_LIGHT, "start", 0.12))
    return doc(W, round(y + h, 2), "\n".join(parts), "1 — спина: тональный слоган")

# ---------------------------------------------------------------- 2 «Схема»

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


def s2_front():
    g, h = logo("tsoft-icon-white", 0, 0, 55)
    return doc(55, round(h, 2), g, "2 — грудь: знак Т-Софт, 55 мм")


def s2_back():
    W = 280
    parts = [text("МОДЕЛЬ  →  ЭМУЛЯЦИЯ  →  ОТРАБОТКА", "Inter-SemiBold", 7.6, W / 2, 7,
                  BLUE_LIGHT, "middle", 0.12)]
    parts.append(scheme(0, 24))
    parts.append(text("Модель, а не картинка.", "InterDisplay-Bold", 21, W / 2, 292, WHITE, "middle", -0.01))
    g, h = logo("tsoft-logo-ru-inverse", W / 2 - 34, 306, 68)
    parts.append(g)
    return doc(W, round(306 + h, 2), "\n".join(parts), "2 — спина: технологическая схема")


# ---------------------------------------------------------------- 4 «Журнал тренажёра»

def s4_front():
    g, h = logo("tsoft-logo-ru-color", 0, 0, 100)
    return doc(100, round(h, 2), g, "4 — грудь: логотип Т-Софт, 100 мм")


def s4_back():
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
    return doc(W, round(y + 3, 2), "\n".join(p), "4 — спина: журнал тренажёра")



# ---------------------------------------------------------------- 3 «Каркас»

def wireframe(width):
    """Каркасная 3D-модель колонны с ёмкостью, ортогональная проекция."""
    import math
    rot, tilt = math.radians(-32), math.radians(24)

    def P(x, y, z):  # y — вверх
        x1 = x * math.cos(rot) - z * math.sin(rot)
        z1 = x * math.sin(rot) + z * math.cos(rot)
        return x1, -(y * math.cos(tilt) - z1 * math.sin(tilt))

    segs = []  # (точки, толщина)

    def poly(pts, w=0.7, closed=False):
        pts = [P(*q) for q in pts]
        if closed:
            pts.append(pts[0])
        segs.append((pts, w))

    N = 12
    ang = [2 * math.pi * i / N for i in range(N)]
    R, H = 1.25, 7.6
    # колонна: кольца, образующие, купол
    for y in [0.0, 0.95, 1.9, 2.85, 3.8, 4.75, 5.7, 6.65, H]:
        poly([(R * math.cos(a), y, R * math.sin(a)) for a in ang], closed=True)
    for a in ang:
        poly([(R * math.cos(a), 0, R * math.sin(a)), (R * math.cos(a), H, R * math.sin(a))])
    for k in (1, 2, 3):
        t = k * math.pi / 8
        poly([(R * math.cos(t) * math.cos(a), H + R * math.sin(t), R * math.cos(t) * math.sin(a))
              for a in ang], closed=True)
    for a in ang:
        poly([(R * math.cos(t) * math.cos(a), H + R * math.sin(t), R * math.cos(t) * math.sin(a))
              for t in [k * math.pi / 8 for k in range(5)]])
    # юбка
    poly([(1.5 * math.cos(a), -0.6, 1.5 * math.sin(a)) for a in ang], closed=True)
    for a in ang[::2]:
        poly([(R * math.cos(a), 0, R * math.sin(a)), (1.5 * math.cos(a), -0.6, 1.5 * math.sin(a))])
    # площадки обслуживания с ограждением
    for y in (2.6, 6.0):
        for r in (1.95,):
            poly([(r * math.cos(a), y, r * math.sin(a)) for a in ang], closed=True)
            poly([(r * math.cos(a), y + 0.45, r * math.sin(a)) for a in ang], 0.5, closed=True)
            for a in ang:
                poly([(r * math.cos(a), y, r * math.sin(a)), (r * math.cos(a), y + 0.45, r * math.sin(a))], 0.5)
    # лестница
    lx, lz = 1.45 * math.cos(-0.9), 1.45 * math.sin(-0.9)
    dx, dz = 0.22 * math.sin(-0.9), -0.22 * math.cos(-0.9)
    poly([(lx + dx, -0.6, lz + dz), (lx + dx, 6.0, lz + dz)], 0.5)
    poly([(lx - dx, -0.6, lz - dz), (lx - dx, 6.0, lz - dz)], 0.5)
    for i in range(0, 22):
        y = -0.3 + i * 0.3
        poly([(lx + dx, y, lz + dz), (lx - dx, y, lz - dz)], 0.5)
    # горизонтальная ёмкость на опорах
    cx, cy, cz, r, L = 3.2, 1.2, 1.2, 0.65, 2.4
    for x in [cx - L / 2 + i * L / 4 for i in range(5)]:
        poly([(x, cy + r * math.cos(a), cz + r * math.sin(a)) for a in ang], closed=True)
    for a in ang:
        poly([(cx - L / 2, cy + r * math.cos(a), cz + r * math.sin(a)),
              (cx + L / 2, cy + r * math.cos(a), cz + r * math.sin(a))])
    for x in (cx - 0.8, cx + 0.8):
        poly([(x, cy - r, cz - 0.4), (x, 0, cz - 0.4), (x, 0, cz + 0.4), (x, cy - r, cz + 0.4)], 0.6)
    # шлемовая линия: верх колонны → ёмкость
    poly([(0, H + R, 0), (0, H + R + 0.5, 0), (cx, H + R + 0.5, 0), (cx, H + R + 0.5, cz),
          (cx, cy + r, cz)], 0.9)
    # сетка пола
    for i in range(-3, 6):
        poly([(i, -0.6, -2.5), (i, -0.6, 3.5)], 0.45)
    for k in [v * 1.0 - 2.5 for v in range(7)]:
        poly([(-3, -0.6, k), (5, -0.6, k)], 0.45)

    xs = [x for pts, _ in segs for x, _ in pts]
    ys = [y for pts, _ in segs for _, y in pts]
    sc = width / (max(xs) - min(xs))
    x0, y0 = min(xs), min(ys)
    out = []
    for pts, w in segs:
        d = " ".join(f"{'M' if i == 0 else 'L'}{(x - x0) * sc:.2f} {(y - y0) * sc:.2f}"
                     for i, (x, y) in enumerate(pts))
        out.append(f'<path d="{d}" stroke-width="{w}"/>')
    g = (f'<g fill="none" stroke="{BLUE_LIGHT}" stroke-linecap="round" stroke-linejoin="round">'
         + "".join(out) + "</g>")
    return g, (max(ys) - y0) * sc, lambda x, y, z: ((P(x, y, z)[0] - x0) * sc, (P(x, y, z)[1] - y0) * sc)


def s3_front():
    g, h = logo("tsoft-logo-ru-inverse", 0, 0, 90)
    return doc(90, round(h, 2), g, "3 — грудь: логотип Т-Софт, 90 мм")


def s3_back():
    W = 270
    parts = [text("3D-МОДЕЛЬ · VR-ТРЕНАЖЁР", "Inter-SemiBold", 7.4, 0, 7, BLUE_LIGHT, "start", 0.12)]
    g, h, P = wireframe(W)
    parts.append(f'<g transform="translate(0 18)">{g}</g>')
    # выноска с позицией аппарата
    tx, ty = P(-1.25, 4.3, 0)
    ty += 18
    parts.append(f'<path fill="none" stroke="{WHITE}" stroke-width="0.6" d="M{tx:.1f} {ty:.1f} L{tx-18:.1f} {ty-12:.1f} H{tx-34:.1f}"/>')
    parts.append(f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="1.4" fill="{WHITE}"/>')
    parts.append(text("К-1", "Inter-SemiBold", 7, tx - 36, ty - 10.5, WHITE, "end"))
    # гизмо осей
    gx, gy = W - 32, 36
    for (dx, dy, lab) in ((18, 0, "X"), (0, -18, "Y"), (-11, 9, "Z")):
        parts.append(f'<path stroke="{WHITE}" stroke-width="1" d="M{gx} {gy} l{dx} {dy}"/>')
        parts.append(text(lab, "Inter-SemiBold", 5.4, gx + dx * 1.3, gy + dy * 1.3 + 1.6, WHITE, "middle"))
    y = 18 + h + 26
    cap = "Навык переносится в работу."
    size = min(21, 21 * W / measure(cap, "InterDisplay-Bold", 21, -0.01))
    parts.append(text(cap, "InterDisplay-Bold", size, 0, y, WHITE, "start", -0.01))
    return doc(W, round(y + 5, 2), "\n".join(parts), "3 — спина: каркасная модель")


# ---------------------------------------------------------------- 5 «Шильдик»

def s5_front():
    W, H, hb_ = 96, 62, 15
    p = [f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="3" fill="{WHITE}" stroke="{NAVY}" stroke-width="1"/>',
         f'<path fill="{NAVY}" d="M0.5 {hb_} V3.5 a3 3 0 0 1 3 -3 H{W-3.5} a3 3 0 0 1 3 3 V{hb_}Z"/>']
    g, lh = logo("tsoft-logo-ru-inverse", 8, (hb_ - 7.5) / 2 + 0.5, 7.5 * 3.816)
    p.append(g)
    p.append(text("ТРЕНАЖЁРНЫЙ КОМПЛЕКС", "Inter-SemiBold", 2.9, W - 8, hb_ / 2 + 1.6, BLUE_LIGHT, "end", 0.1))
    rows = [("ИЗДЕЛИЕ", "Инженер-разработчик"), ("ЗАВ. №", "0042"),
            ("ГОД ВЫПУСКА", "2026"), ("РЕЖИМ", "штатный")]
    y = hb_ + 4
    for i, (k, v) in enumerate(rows):
        yb = y + 7
        p.append(text(k, "Inter-SemiBold", 3.0, 8, yb, BLUE, "start", 0.1))
        p.append(text(v, "Inter-Medium", 4.4, 36, yb + 0.2, NAVY, "start", 0,
                      {"kern": True, "tnum": True}))
        if i < len(rows) - 1:
            p.append(f'<rect x="8" y="{yb+3.1:.2f}" width="{W-16}" height="0.4" fill="{NAVY}"/>')
        y += 10.3
    for cx, cy in ((4, hb_ + 4), (W - 4, hb_ + 4), (4, H - 4), (W - 4, H - 4)):
        p.append(f'<circle cx="{cx}" cy="{cy}" r="1.5" fill="none" stroke="{NAVY}" stroke-width="0.5"/>'
                 f'<path stroke="{NAVY}" stroke-width="0.5" d="M{cx-1} {cy} H{cx+1}"/>')
    return doc(W, H, "\n".join(p), "5 — грудь: шильдик, поля «Изделие» и «Зав. №» персонализируются")


def s5_back():
    g, h = logo("tsoft-icon-color", 0, 0, 30)
    return doc(30, round(h, 2), g, "5 — спина: знак под воротом, 30 мм")


# ---------------------------------------------------------------- мокап

# Силуэт футболки размера L (мм, вид спереди/сзади); полуобхват груди 520 мм.
SHIRT = ("M290 40 Q380 {neck} 470 40 L630 78 L748 252 L664 304 L640 266 "
         "L646 742 Q380 754 114 742 L120 266 L96 304 L12 252 L130 78Z")
GREY = "#C9CED6"

# ключ, название, ткань, ширина груди, ширина спины, верх спины, описание, для кого, печать
CONCEPTS = [
    ("1", "Тон в тон", NAVY, 40, 270, 125,
     "Минимум бренда: знак вышит на груди, слоган напечатан на спине краской на тон светлее ткани. Читается вблизи, издалека выглядит однотонной вещью.",
     "Подарки заказчикам и партнёрам, руководители, деловые мероприятия",
     "Вышивка белой нитью (грудь); тональная краска + #89B2FF, белый (спина)"),
    ("2", "Схема", NAVY, 55, 280, 125,
     "На спине технологическая схема ректификации: колонна, насосы, КИП. Ключевое сообщение «Модель, а не картинка».",
     "Инженеры, разработчики моделей, отраслевые конференции",
     "#89B2FF, белый, #015AFD (знак)"),
    ("3", "Каркас", NAVY, 90, 270, 125,
     "Каркасная 3D-модель колонны с площадками, лестницей и ёмкостью, оси как во вьюпорте редактора. Сообщение «Навык переносится в работу».",
     "Направление 3D/VR, выставки с VR-демо, HR-бренд для 3D-художников и Unity-разработчиков",
     "#89B2FF, белый, #015AFD (знак)"),
    ("4", "Журнал тренажёра", "#F4F6F9", 100, 280, 125,
     "Журнал событий учебного сценария на спине: от отклонения до штатного режима, итог «Сценарий пройден».",
     "Внутренний мерч, стажёры, хакатоны, дни открытых дверей",
     "#0A2646, #015AFD (+ #2B2A29 в логотипе)"),
    ("5", "Шильдик", GREY, 96, 30, 95,
     "Шильдик оборудования на груди. Поля «Изделие» и «Зав. №» заполняются под сотрудника: роль и личный номер.",
     "Сотрудники (персональный мерч), онбординг, юбилеи стажа",
     "Белый, #0A2646, #015AFD; персональные поля — DTF"),
]


def shirt(fabric, side, art, art_w, art_x, art_y):
    light = fabric != NAVY
    stroke = "#B4BCC8" if light else "#16365E"
    shade = "#D5DBE3" if fabric == "#F4F6F9" else ("#B9BFC9" if light else "#071D37")
    neck = 112 if side == "front" else 64
    inner = f"M290 40 Q380 {neck} 470 40"
    return f"""<svg viewBox="0 0 760 780" xmlns="http://www.w3.org/2000/svg">
<path d="{SHIRT.format(neck=neck)}" fill="{fabric}" stroke="{stroke}" stroke-width="3" stroke-linejoin="round"/>
<path d="M130 78 L120 266 M630 78 L640 266" stroke="{shade}" stroke-width="3" fill="none"/>
<path d="{inner}" fill="none" stroke="{shade}" stroke-width="14"/>
<path d="{inner}" fill="none" stroke="{stroke}" stroke-width="2"/>
<image href="{art}" x="{art_x}" y="{art_y}" width="{art_w}"/>
</svg>"""


def art_path(key, side):
    return f"print/2026-10-08_tsoft-tshirt_{key}_{side}.svg"


def mockup():
    cards = []
    for key, name, fabric, fw, bw, by, desc, use, colors in CONCEPTS:
        cards.append(f"""<section class="card" data-key="{key}">
  <div class="kicker">КОНЦЕПЦИЯ {key}</div><h2>{name}</h2>
  <div class="pair">
    <figure>{shirt(fabric, "front", art_path(key, "front"), fw, 475 - fw / 2, 165)}<figcaption>Перед</figcaption></figure>
    <figure>{shirt(fabric, "back", art_path(key, "back"), bw, 380 - bw / 2, by)}<figcaption>Спина</figcaption></figure>
  </div>
  <p>{desc}</p>
  <dl><dt>Для кого</dt><dd>{use}</dd><dt>Печать</dt><dd>{colors}</dd></dl>
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
<p>Пять концепций в фирменном стиле: палитра brand tokens v2.0, Inter, оригинальные файлы логотипа. Печатные файлы в папке print/ в масштабе 1:1, текст в кривых.</p></header>
<main>
{chr(10).join(cards)}
</main>
</body></html>
"""


# ---------------------------------------------------------------- сборка

ARTS = {f"{k}_{side}": globals()[f"s{k}_{side}"] for k in "12345" for side in ("front", "back")}

if __name__ == "__main__":
    PRINT.mkdir(exist_ok=True)
    for old in PRINT.glob("*.svg"):
        old.unlink()
    for name, fn in ARTS.items():
        out = PRINT / f"2026-10-08_tsoft-tshirt_{name}.svg"
        out.write_text(fn())
        print(out.relative_to(ROOT), out.stat().st_size // 1024, "KB")
    (ROOT / "mockup.html").write_text(mockup())
    print("mockup.html")
