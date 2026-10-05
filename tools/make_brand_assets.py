"""Generate AutopostVideo brand images (logo mark + app icon) — see DESIGN.md.

    python tools/make_brand_assets.py

Writes to assets/brand/:
    logo_mark.png   transparent gradient play mark (512px)
    app_icon.png    mark on a Deep Navy rounded square (512px)
    app_icon.ico    multi-size Windows icon (16–256px)
"""
import os

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "brand")

NAVY   = (11, 16, 32)      # #0B1020
VIOLET = (139, 92, 246)    # #8B5CF6 — gradient start (top-left)
PURPLE = (99, 102, 241)    # #6366F1 — Primary Purple
SKY    = (59, 130, 246)    # #3B82F6 — gradient end (bottom-right)

S = 2048  # supersampled canvas


def rounded_polygon_mask(points, radius):
    """Polygon with rounded corners: blur a sharp mask, then re-threshold."""
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).polygon(points, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(radius))
    return m.point(lambda v: 255 if v > 128 else 0)


def mostly_vertical_gradient(stops, x_weight=0.3):
    """Gradient running top → bottom (tilted slightly left → right) through RGB stops."""
    gy = Image.linear_gradient("L").resize((S, S))
    gx = gy.rotate(90).transpose(Image.FLIP_LEFT_RIGHT)
    t = Image.blend(gy, gx, x_weight)          # 0 = top-left … 255 = bottom-right

    seg = len(stops) - 1

    def channel(c):
        lut = []
        for v in range(256):
            p = v / 255 * seg
            i = min(int(p), seg - 1)
            f = p - i
            lut.append(round(stops[i][c] + (stops[i + 1][c] - stops[i][c]) * f))
        return t.point(lut)

    return Image.merge("RGB", [channel(c) for c in range(3)])


def logo_mark():
    # Outer play shape — soft, slightly wide triangle pointing right
    outer = rounded_polygon_mask([(330, 170), (1830, 1024), (330, 1878)], 150)
    # Inner white play glyph, nudged right so it reads as optically centered
    inner = rounded_polygon_mask([(800, 690), (1390, 1024), (800, 1358)], 60)

    mark = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    grad = mostly_vertical_gradient([VIOLET, PURPLE, SKY])
    mark.paste(grad, (0, 0), outer)

    # Soft highlight on the upper half for depth (clipped to the shape)
    hl = Image.new("L", (S, S), 0)
    ImageDraw.Draw(hl).ellipse((-600, -1300, 2200, 1000), fill=34)
    hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(220)), outer)
    mark.paste((255, 255, 255), (0, 0), hl)

    mark.paste((255, 255, 255, 255), (0, 0), inner)
    return mark


def app_icon(mark):
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bg = Image.new("L", (S, S), 0)
    ImageDraw.Draw(bg).rounded_rectangle((0, 0, S - 1, S - 1), radius=int(S * 0.23), fill=255)
    icon.paste(NAVY + (255,), (0, 0), bg)
    small = mark.resize((int(S * 0.66), int(S * 0.66)), Image.LANCZOS)
    o = (S - small.width) // 2
    icon.alpha_composite(small, (o + int(S * 0.02), o))
    return icon


def main():
    os.makedirs(OUT, exist_ok=True)
    mark = logo_mark()
    icon = app_icon(mark)
    mark.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, "logo_mark.png"))
    icon512 = icon.resize((512, 512), Image.LANCZOS)
    icon512.save(os.path.join(OUT, "app_icon.png"))
    icon512.save(os.path.join(OUT, "app_icon.ico"),
                 sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Brand assets written to", OUT)


if __name__ == "__main__":
    main()
