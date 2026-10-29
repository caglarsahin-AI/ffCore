# -*- coding: utf-8 -*-
"""FFCore işareti: FFEngine'in çift F'si + merkezde 'core' noktası. Aynı geometri SVG ve PNG'ye yazılır."""
import math, os, sys
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)

BG, CARD = "#0A192F", "#112240"
BLUE, BLUE2 = "#3898EC", "#1565C0"
ORANGE, ORANGE2 = "#FF8A00", "#E65100"
CYAN = "#00E5FF"
SK = math.tan(math.radians(12))  # italik eğim
CY = 256

# F harfi: gövde + üst çubuk + orta çubuk (dik koordinatlarda, sonra eğilir)
def F(x, y, h=250, w=150, t=58):
    stem = [(x, y), (x + t, y), (x + t, y + h), (x, y + h)]
    top = [(x, y), (x + w, y), (x + w, y + t), (x, y + t)]
    mid_y = y + int(h * 0.44)
    mid = [(x, mid_y), (x + int(w * 0.78), mid_y), (x + int(w * 0.78), mid_y + t - 8), (x, mid_y + t - 8)]
    return [stem, top, mid]

def skew(poly):
    return [(px + SK * (CY - py), py) for px, py in poly]

blueF = [skew(p) for p in F(118, 118)]
orangeF = [skew(p) for p in F(236, 180, h=240, w=150)]
core = (300, 262, 30)  # cx, cy, r: iki F'nin kesiştiği yer

# ---------- SVG ----------
def path(polys):
    return " ".join("M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in p) + " Z" for p in polys)

def svg(with_bg: bool):
    bg = f'<rect width="512" height="512" rx="112" fill="{BG}"/>' if with_bg else ""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{BLUE}"/><stop offset="1" stop-color="{BLUE2}"/></linearGradient>
    <linearGradient id="o" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{ORANGE}"/><stop offset="1" stop-color="{ORANGE2}"/></linearGradient>
    <radialGradient id="g"><stop offset="0" stop-color="#ffffff"/><stop offset="0.35" stop-color="{CYAN}"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
  </defs>
  {bg}
  <path d="{path(blueF)}" fill="url(#b)"/>
  <path d="{path(orangeF)}" fill="url(#o)"/>
  <circle cx="{core[0]}" cy="{core[1]}" r="{core[2]*2.2:.0f}" fill="url(#g)" opacity="0.9"/>
  <circle cx="{core[0]}" cy="{core[1]}" r="{core[2]*0.55:.0f}" fill="#ffffff"/>
</svg>
'''

open(os.path.join(OUT, "ffcore-mark.svg"), "w", encoding="utf-8").write(svg(True))
open(os.path.join(OUT, "ffcore-mark-transparent.svg"), "w", encoding="utf-8").write(svg(False))

# ---------- PNG (4x süperörnekleme) ----------
S = 4
def render(size, with_bg=True):
    W = 512 * S
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if with_bg:
        d.rounded_rectangle([0, 0, W - 1, W - 1], radius=112 * S, fill=BG)
    def poly(p, fill):
        d.polygon([(x * S, y * S) for x, y in p], fill=fill)
    for p in blueF: poly(p, BLUE)
    for p in orangeF: poly(p, ORANGE)
    cx, cy, r = [v * S for v in core]
    glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - r * 1.8, cy - r * 1.8, cx + r * 1.8, cy + r * 1.8], fill=(0, 229, 255, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(r * 0.9))
    im = Image.alpha_composite(im, glow)
    d = ImageDraw.Draw(im)
    d.ellipse([cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55], fill="#ffffff")
    return im.resize((size, size), Image.LANCZOS)

sizes = [1024, 512, 256, 128, 64, 48, 32, 16]
for s in sizes:
    render(s).save(os.path.join(OUT, f"ffcore-mark-{s}.png"))
render(512, with_bg=False).save(os.path.join(OUT, "ffcore-mark-transparent-512.png"))
render(256).save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

# karşılaştırma levhası: 256 / 64 / 32 / 16 yan yana, açık ve koyu zemin
sheet = Image.new("RGBA", (256 + 64 + 32 + 16 + 5 * 24, 256 * 2 + 72), (238, 242, 247, 255))
sd = ImageDraw.Draw(sheet)
sd.rectangle([0, 256 + 48, sheet.width, sheet.height], fill=BG)
for row, y0 in enumerate([24, 256 + 72]):
    x = 24
    for s in [256, 64, 32, 16]:
        sheet.alpha_composite(render(s), (x, y0 + (256 - s) // 2))
        x += s + 24
sheet.save(os.path.join(OUT, "preview-sheet.png"))
print("ok", OUT)
