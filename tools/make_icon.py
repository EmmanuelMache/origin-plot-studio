"""The app icon in the colours of the window: a navy tile, a white spectrum, a blue baseline and an orange dot (Origin).
Writes origin_plot_app/app.ico (16-256 px) and origin_plot_app/app.png (64 px). Run: python tools/make_icon.py"""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

APP = Path(__file__).resolve().parents[1] / "origin_plot_app"
NAVY, BLUE, ORANGE, WHITE = (23, 50, 77), (37, 99, 235), (180, 83, 42), (255, 255, 255)


def _stroke(d, pts, width, fill):
    """A smooth thick line: segments plus a round dot at every point (no corners)."""
    d.line(pts, fill=fill, width=width)
    r = width / 2
    for x, y in pts:
        d.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def draw(n=1024):
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, n - 1, n - 1], radius=int(n * 0.22), fill=NAVY)
    x0, x1, base, top = n * 0.17, n * 0.83, n * 0.70, n * 0.30
    _stroke(d, [(x0, n * 0.80), (x1, n * 0.80)], int(n * 0.055), BLUE)                    # the axis: the app's blue
    xs = np.linspace(0, 1, 900)
    pk = lambda c, w, h: h * np.exp(-0.5 * ((xs - c) / w) ** 2)
    ys = 0.05 + 0.10 * np.exp(-xs / 0.16) + pk(0.30, 0.035, 0.48) + pk(0.55, 0.035, 1.0) + pk(0.80, 0.035, 0.38)
    ys = ys / ys.max()
    pts = [(x0 + (x1 - x0) * x, base - (base - top) * y) for x, y in zip(xs, ys)]
    _stroke(d, pts, int(n * 0.05), WHITE)
    cx, rr = x0 + (x1 - x0) * 0.55, n * 0.06                                               # the orange dot above the main peak: Origin
    cy = top - n * 0.13
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=ORANGE)
    return im


def main():
    big = draw()
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    imgs = [big.resize((s, s), Image.LANCZOS) for s in sizes]
    imgs[-1].save(APP / "app.ico", sizes=[(s, s) for s in sizes], append_images=imgs[:-1])
    big.resize((64, 64), Image.LANCZOS).save(APP / "app.png")
    big.resize((256, 256), Image.LANCZOS).save(APP.parent / "docs" / "icon_256.png") if (APP.parent / "docs").is_dir() else None
    print("written app.ico, app.png")


if __name__ == "__main__":
    main()
