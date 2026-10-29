# -*- coding: utf-8 -*-
"""FFCore vektör işaret konseptleri: cekirdek, dugum, yorunge.
Aynı geometri SVG (kaynak) ve PNG (Pillow, 4x süperörnekleme) olarak yazılır.
Kullanım: python -I make_concepts.py [çıktı dizini]
"""
import math, os, sys
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
BG, BLUE, BLUE2, ORANGE, ORANGE2, CYAN, LINE = "#0A192F", "#3898EC", "#1565C0", "#FF8A00", "#E65100", "#00E5FF", "#8FA3C7"
SKEW = math.tan(math.radians(14))
R = 14          # köşe yuvarlatma (stroke ile)
S = 4           # PNG süperörnekleme
VB = 512

def hex2rgb(h): return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))

# ---------- harf geometrisi ----------
def F_polys(x, y, h=250, w=152, t=60):
    """F: gövde, üst çubuk, orta çubuk; dik koordinat. Orta çubuk üst çubuktan biraz kısa."""
    stem = [(x, y), (x + t, y), (x + t, y + h), (x, y + h)]
    top = [(x, y), (x + w, y), (x + w, y + t), (x, y + t)]
    my = y + int(h * 0.45)
    mid = [(x, my), (x + int(w * 0.74), my), (x + int(w * 0.74), my + t - 10), (x, my + t - 10)]
    return [stem, top, mid]

def skew(poly, cy=VB / 2):
    return [(px + SKEW * (cy - py), py) for px, py in poly]

BLUE_F = [skew(p) for p in F_polys(118, 122)]
ORANGE_F = [skew(p) for p in F_polys(238, 184, h=238)]
CORE = (300, 262)   # iki F'nin kesişimi

# ---------- SVG ----------
def d_of(polys):
    return " ".join("M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in p) + " Z" for p in polys)

def svg_letters():
    # stroke aynı renkte ve round join: köşeleri yuvarlatır
    return (f'<path d="{d_of(BLUE_F)}" fill="url(#b)" stroke="url(#b)" stroke-width="{R}" stroke-linejoin="round"/>\n'
            f'<path d="{d_of(ORANGE_F)}" fill="url(#o)" stroke="url(#o)" stroke-width="{R}" stroke-linejoin="round"/>')

DEFS = f'''<defs>
  <linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{BLUE2}"/></linearGradient>
  <linearGradient id="o" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ORANGE}"/><stop offset="1" stop-color="{ORANGE2}"/></linearGradient>
  <radialGradient id="g"><stop offset="0" stop-color="#ffffff"/><stop offset="0.3" stop-color="{CYAN}"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
</defs>'''

def svg_wrap(body, with_bg):
    bg = f'<rect width="{VB}" height="{VB}" rx="112" fill="{BG}"/>' if with_bg else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB} {VB}">\n{DEFS}\n{bg}\n{body}\n</svg>\n'

def svg_core():
    cx, cy = CORE
    return svg_letters() + f'\n<circle cx="{cx}" cy="{cy}" r="62" fill="url(#g)" opacity="0.95"/>\n<circle cx="{cx}" cy="{cy}" r="17" fill="#ffffff"/>'

NODES = [((118 + SKEW * (256 - 122) + 152, 122 + 30), (438, 70)),      # mavi üst çubuk ucu → sağ üst
         ((238 + SKEW * (256 - 422), 422), (150, 470)),                 # turuncu gövde altı → sol alt
         ((118 + SKEW * (256 - 372), 372), (60, 300))]                  # mavi gövde ortası → sol
def svg_node():
    parts = [svg_letters()]
    for (x1, y1), (x2, y2) in NODES:
        parts.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="6" stroke-linecap="round" opacity="0.8"/>')
        parts.append(f'<circle cx="{x2}" cy="{y2}" r="16" fill="{BG}" stroke="{CYAN}" stroke-width="6"/>')
    cx, cy = CORE
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="17" fill="{CYAN}"/>')
    return "\n".join(parts)

ORBIT = (256, 262, 232, 150, -28)  # cx, cy, rx, ry, açı
def svg_orbit():
    cx, cy, rx, ry, a = ORBIT
    # halka üstündeki nokta: parametre t=200°
    t = math.radians(200)
    px, py = rx * math.cos(t), ry * math.sin(t)
    ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
    dx, dy = cx + px * ca - py * sa, cy + px * sa + py * ca
    return (svg_letters() +
            f'\n<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="rotate({a} {cx} {cy})" fill="none" stroke="{LINE}" stroke-width="7" opacity="0.75"/>'
            f'\n<circle cx="{dx:.0f}" cy="{dy:.0f}" r="18" fill="{CYAN}"/>')

CONCEPTS = {"cekirdek": svg_core, "dugum": svg_node, "yorunge": svg_orbit}

# ---------- PNG ----------
def draw_letters(d, scale):
    def poly(p, col):
        pts = [(x * scale, y * scale) for x, y in p]
        d.polygon(pts, fill=col)
        d.line(pts + [pts[0]], fill=col, width=int(R * scale), joint="curve")
        for x, y in pts:
            r = R * scale / 2
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    for p in BLUE_F: poly(p, BLUE)
    for p in ORANGE_F: poly(p, ORANGE)

def glow(im, cx, cy, r, col, alpha=210):
    g = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse([cx - r, cy - r, cx + r, cy + r], fill=hex2rgb(col) + (alpha,))
    g = g.filter(ImageFilter.GaussianBlur(r * 0.55))
    return Image.alpha_composite(im, g)

def render(name, size, with_bg=True):
    W = VB * S
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if with_bg:
        d.rounded_rectangle([0, 0, W - 1, W - 1], radius=112 * S, fill=BG)
    draw_letters(d, S)
    cx, cy = CORE[0] * S, CORE[1] * S
    if name == "cekirdek":
        im = glow(im, cx, cy, 62 * S, CYAN)
        d = ImageDraw.Draw(im)
        d.ellipse([cx - 17 * S, cy - 17 * S, cx + 17 * S, cy + 17 * S], fill="#ffffff")
    elif name == "dugum":
        for (x1, y1), (x2, y2) in NODES:
            d.line([(x1 * S, y1 * S), (x2 * S, y2 * S)], fill=LINE, width=6 * S)
            d.ellipse([(x2 - 16) * S, (y2 - 16) * S, (x2 + 16) * S, (y2 + 16) * S], fill=BG, outline=CYAN, width=6 * S)
        d.ellipse([cx - 17 * S, cy - 17 * S, cx + 17 * S, cy + 17 * S], fill=CYAN)
    elif name == "yorunge":
        ocx, ocy, rx, ry, a = ORBIT
        layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        ImageDraw.Draw(layer).ellipse([(ocx - rx) * S, (ocy - ry) * S, (ocx + rx) * S, (ocy + ry) * S], outline=hex2rgb(LINE) + (190,), width=7 * S)
        layer = layer.rotate(-a, resample=Image.BICUBIC, center=(ocx * S, ocy * S))
        im = Image.alpha_composite(im, layer)
        d = ImageDraw.Draw(im)
        t = math.radians(200); px, py = rx * math.cos(t), ry * math.sin(t)
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        dx, dy = (ocx + px * ca - py * sa) * S, (ocy + px * sa + py * ca) * S
        d.ellipse([dx - 18 * S, dy - 18 * S, dx + 18 * S, dy + 18 * S], fill=CYAN)
    return im.resize((size, size), Image.LANCZOS)

SIZES = [1024, 512, 256, 128, 64, 48, 32, 16]
for name, fn in CONCEPTS.items():
    d = os.path.join(OUT, name); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"ffcore-{name}.svg"), "w", encoding="utf-8").write(svg_wrap(fn(), True))
    open(os.path.join(d, f"ffcore-{name}-transparent.svg"), "w", encoding="utf-8").write(svg_wrap(fn(), False))
    for s in SIZES:
        render(name, s).save(os.path.join(d, f"ffcore-{name}-{s}.png"))
    render(name, 512, False).save(os.path.join(d, f"ffcore-{name}-transparent-512.png"))
    render(name, 256).save(os.path.join(d, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

# levha: 3 satır (konsept) × (256, 64, 32, 16) açık zemin + aynı koyu zemin
COLS = [256, 64, 32, 16]
cw = sum(COLS) + 24 * (len(COLS) + 1)
sheet = Image.new("RGBA", (cw * 2, (256 + 40) * 3 + 24), (238, 242, 247, 255))
ImageDraw.Draw(sheet).rectangle([cw, 0, cw * 2, sheet.height], fill=BG)
for row, name in enumerate(CONCEPTS):
    y0 = 24 + row * (256 + 40)
    for half in (0, 1):
        x = half * cw + 24
        for s in COLS:
            sheet.alpha_composite(render(name, s), (x, y0 + (256 - s) // 2)); x += s + 24
sheet.save(os.path.join(OUT, "preview-concepts.png"))
print("ok", OUT)
