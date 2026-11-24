"""Synthetic photos of sketches on paper (grey shading, noise, wobbly pen lines, scribbled words) for the photo reader."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def _paper(w, h, seed):
    r = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w]
    a = 225 - 35 * (xx / w) - 20 * (yy / h) + r.normal(0, 4, (h, w))           # light from one side, paper grain
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8")).convert("RGB"), r


def _wob(r, pts, amp=2.0):
    return [(x + r.normal(0, amp), y + r.normal(0, amp)) for x, y in pts]


def _line(d, pts, w=5, ink=(35, 40, 70)):
    d.line(pts, fill=ink, width=w, joint="curve")


def _box(d, r, x, y, w, h, pen=5):
    n = 30
    pts = [(x + w * t, y) for t in np.linspace(0, 1, n)] + [(x + w, y + h * t) for t in np.linspace(0, 1, n)] + \
          [(x + w * (1 - t), y + h) for t in np.linspace(0, 1, n)] + [(x, y + h * (1 - t)) for t in np.linspace(0, 1, n)]
    _line(d, _wob(r, pts), w=pen)


def _scribble(d, r, x, y, n=7):
    for k in range(n):
        xs = x + k * 14
        _line(d, _wob(r, [(xs, y), (xs + 6, y - 12), (xs + 11, y)], 1.0), w=3)


def framed(path, seed=1):
    im, r = _paper(1600, 1100, seed); d = ImageDraw.Draw(im)
    _box(d, r, 200, 180, 1200, 760)
    for k in range(3):                                                          # three curves, one above the other
        xs = np.linspace(240, 1360, 80); ys = 330 + 190 * k - 70 * np.exp(-((xs - 700) / 40) ** 2) - 40 * np.exp(-((xs - 1000) / 30) ** 2)
        _line(d, _wob(r, list(zip(xs, ys)), 1.5))
    _box(d, r, 960, 210, 380, 230, pen=4)                                         # the zoom, top right
    _box(d, r, 230, 210, 110, 60, pen=3)                                          # the legend, top left
    _scribble(d, r, 650, 130); _scribble(d, r, 700, 1010)                       # title and x axis title (not read)
    im.filter(ImageFilter.GaussianBlur(1.2)).save(path)
    return path


def axes_only(path, seed=2):
    im, r = _paper(1400, 1000, seed); d = ImageDraw.Draw(im)
    _line(d, _wob(r, [(200, 150 + t * 650) for t in np.linspace(0, 1, 40)] + [(200 + t * 1000, 800) for t in np.linspace(0, 1, 50)]))   # an L
    for k in range(2):                                                          # two crossing curves
        xs = np.linspace(240, 1150, 70); ys = 500 + 200 * np.sin(xs / 150 + 2 * k)
        _line(d, _wob(r, list(zip(xs, ys)), 1.5))
    im.filter(ImageFilter.GaussianBlur(1.0)).save(path)
    return path


def two_frames(path, seed=3):
    im, r = _paper(1600, 900, seed); d = ImageDraw.Draw(im)
    for x in (120, 860):
        _box(d, r, x, 150, 620, 600)
        xs = np.linspace(x + 30, x + 590, 50); _line(d, _wob(r, list(zip(xs, 600 - 300 * np.exp(-((xs - x - 300) / 60) ** 2))), 1.5))
    im.filter(ImageFilter.GaussianBlur(1.0)).save(path)
    return path
