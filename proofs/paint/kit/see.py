"""Seeing: the painter's eyes. Every function returns a PIL image; paint.py saves it and prints the path.

Canvas pixels are the only coordinates anywhere: grid labels, zoom boxes and outlines are all canvas pixels.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

GRIDS = (1, 2, 5, 10, 16, 25, 32, 50, 64, 100, 128, 200, 256, 500, 512, 1000, 1024, 4096)


def _font(px):
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def to_u8(a):
    return (np.clip(np.asarray(a, np.float32), 0, 1) * 255 + 0.5).astype(np.uint8)


def canvas_size(doc):
    """(w, h) of the canvas, read off the composite so it works whatever the doc calls its fields."""
    h, w = doc.composite().shape[:2]
    return w, h


def check_zoom(zoom, w, h):
    """Return (x, y, w, h) ints inside the canvas, or raise ValueError saying what is wrong."""
    if zoom is None:
        return 0, 0, w, h
    x, y, zw, zh = (int(round(v)) for v in zoom)
    if zw <= 0 or zh <= 0:
        raise ValueError(f"zoom {zoom}: width and height must be positive")
    if x < 0 or y < 0 or x + zw > w or y + zh > h:
        raise ValueError(f"zoom {zoom} is outside the {w}x{h} canvas (x+w must be <= {w}, y+h <= {h})")
    return x, y, zw, zh


def crop(a, zoom):
    x, y, zw, zh = zoom
    return a[y:y + zh, x:x + zw]


def _auto_grid(w):
    return next(g for g in GRIDS if w / g <= 10)


def _scale_img(rgb_u8, size, zw, zh):
    s = size / zw
    resample = Image.NEAREST if s >= 3 else Image.LANCZOS
    return Image.fromarray(rgb_u8).resize((size, max(1, round(zh * s))), resample), s


def draw_grid(img, zoom, s, grid=None):
    """Label a grid in canvas pixels onto `img`, which shows `zoom` at scale `s`. Lines sit on pixel edges."""
    x, y, zw, zh = zoom
    grid = grid or _auto_grid(zw)
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d, f = ImageDraw.Draw(lay), _font(13)
    for k in range(-(-x // grid) * grid, x + zw + 1, grid):
        px = round((k - x) * s)
        if 0 <= px < img.width:
            d.line([(px, 0), (px, img.height)], fill=(255, 0, 255, 120))
            d.rectangle([px + 1, 0, px + 8 * len(str(k)) + 4, 15], fill=(0, 0, 0, 175))
            d.text((px + 3, 1), str(k), fill=(255, 255, 255, 255), font=f)
    for k in range(-(-y // grid) * grid, y + zh + 1, grid):
        py = round((k - y) * s)
        if 0 <= py < img.height:
            d.line([(0, py), (img.width, py)], fill=(0, 255, 255, 120))
            d.rectangle([0, py + 1, 8 * len(str(k)) + 4, py + 16], fill=(0, 0, 0, 175))
            d.text((2, py + 2), str(k), fill=(255, 255, 255, 255), font=f)
    return Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB")


def view(rgb, zoom=None, grid=None, size=1200, label=None):
    """Crop `zoom`, scale to `size` px wide, label a grid in canvas pixels. `rgb` is HxWx3 float 0..1."""
    h, w = rgb.shape[:2]
    zoom = check_zoom(zoom, w, h)
    if size < 16:
        raise ValueError("size must be at least 16 px")
    img, s = _scale_img(to_u8(crop(rgb, zoom)), size, zoom[2], zoom[3])
    img = draw_grid(img, zoom, s, grid) if grid != 0 else img
    return titled(img, label) if label else img


def titled(img, text, h=22):
    can = Image.new("RGB", (img.width, img.height + h), (28, 28, 28))
    can.paste(img, (0, h))
    ImageDraw.Draw(can).text((6, 3), text, fill=(235, 235, 235), font=_font(15))
    return can


def hstack(imgs, gap=10):
    H = max(i.height for i in imgs)
    can = Image.new("RGB", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), H), (28, 28, 28))
    x = 0
    for i in imgs:
        can.paste(i, (x, 0))
        x += i.width + gap
    return can


def layer_view(doc, name, zoom=None, grid=None, size=1200):
    """One layer alone, over a checkerboard so transparent areas show."""
    px = np.asarray(doc.layer_pixels(name), np.float32)
    h, w = px.shape[:2]
    zoom = check_zoom(zoom, w, h)
    yy, xx = np.mgrid[0:h, 0:w]
    chk = np.where(((xx // 8 + yy // 8) % 2)[..., None] == 0, 0.35, 0.55).astype(np.float32) * np.ones(3, np.float32)
    a = px[..., 3:4]
    rgb = px[..., :3]
    if getattr(doc, "layer_premultiplied", False):
        out = rgb + chk * (1 - a)
    else:
        out = rgb * a + chk * (1 - a)
    return view(out, zoom, grid, size, label=f"layer '{name}'")


def changed_bbox(a, b, thresh=1 / 255):
    """(x0, y0, x1, y1) of pixels where a and b differ by more than thresh, or None."""
    m = np.abs(a - b).max(axis=2) > thresh
    if not m.any():
        return None
    ys, xs = np.where(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def diff_image(a, b):
    """Dark picture of `b` with every changed pixel burned in red/yellow by how much it changed."""
    d = np.abs(a - b).max(axis=2)
    base = np.repeat((b.mean(axis=2, keepdims=True) * 0.35), 3, axis=2)
    k = np.clip(d * 4, 0, 1)[..., None]
    hot = np.stack([np.ones_like(d), np.clip(d * 2, 0, 1), np.zeros_like(d)], axis=2)
    return base * (1 - k) + hot * k


def before_after(doc, k=1, zoom=None, grid=None, size=600):
    """The last `k` batches: before | after | difference, the changed box outlined in all three."""
    hist = doc.history()
    if k < 1 or k > len(hist):
        raise ValueError(f"--batches {k}: the document has {len(hist)} batches")
    after = np.asarray(doc.composite(), np.float32)
    before = _composite_before(doc, hist, k)
    h, w = after.shape[:2]
    zoom_t = check_zoom(zoom, w, h)
    box = changed_bbox(before, after)
    diff = diff_image(before, after)
    panels = []
    for name, arr in (("BEFORE", before), ("AFTER", after), ("DIFFERENCE", diff)):
        img, s = _scale_img(to_u8(crop(arr, zoom_t)), size, zoom_t[2], zoom_t[3])
        img = draw_grid(img, zoom_t, s, grid)
        if box:
            d = ImageDraw.Draw(img)
            x0, y0, x1, y1 = box
            d.rectangle([(x0 - zoom_t[0]) * s - 2, (y0 - zoom_t[1]) * s - 2,
                         (x1 - zoom_t[0]) * s + 2, (y1 - zoom_t[1]) * s + 2], outline=(0, 255, 0), width=2)
        panels.append(titled(img, name))
    labels = ", ".join(f"#{e['batch']} {e['label']}" for e in hist[-k:])
    note = f"last {k} batch(es): {labels}; " + (f"changed box x{box[0]}..{box[2]} y{box[1]}..{box[3]}" if box else "nothing changed")
    return titled(hstack(panels), note[:200], 22), box


def _composite_before(doc, hist, k):
    """Composite as it was before the last k batches."""
    if len(hist) > k:
        try:
            return np.asarray(doc.snapshot(hist[-k - 1]["batch"]), np.float32)
        except Exception:
            pass
    for _ in range(k):  # fall back: step back in history, look, step forward again
        doc.undo()
    try:
        return np.asarray(doc.composite(), np.float32).copy()
    finally:
        for _ in range(k):
            doc.redo()


def load_ref(path, w, h):
    """Reference image scaled to the canvas size (same pixels as the work, so zoom boxes match)."""
    im = Image.open(path).convert("RGB")
    if abs(im.width / im.height - w / h) > 0.02:
        print(f"note: reference is {im.width}x{im.height} but canvas is {w}x{h}; it is stretched to fit")
    return np.asarray(im.resize((w, h), Image.LANCZOS), np.float32) / 255


def side_by_side(doc, ref_path, zoom=None, grid=None, size=600, diff=False):
    work = np.asarray(doc.composite(), np.float32)
    h, w = work.shape[:2]
    zoom_t = check_zoom(zoom, w, h)
    ref = load_ref(ref_path, w, h)
    items = [("REFERENCE", ref), ("WORK", work)]
    if diff:
        items.append(("DIFFERENCE (brighter = further off)", np.repeat(np.clip(np.abs(ref - work).mean(axis=2, keepdims=True) * 3, 0, 1), 3, 2)))
    panels = []
    for name, arr in items:
        img, s = _scale_img(to_u8(crop(arr, zoom_t)), size, zoom_t[2], zoom_t[3])
        panels.append(titled(draw_grid(img, zoom_t, s, grid), name))
    return hstack(panels)


def luminance(rgb):
    return rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)


def values(doc, zoom=None, grid=None, size=600, steps=5):
    """Colour | greyscale | greyscale posterised into `steps` value steps (shows the big shapes)."""
    rgb = np.asarray(doc.composite(), np.float32)
    h, w = rgb.shape[:2]
    zoom_t = check_zoom(zoom, w, h)
    g = luminance(rgb)
    post = np.minimum(np.floor(g * steps), steps - 1) / (steps - 1)
    panels = []
    for name, arr in (("COLOUR", rgb), ("GREY", np.repeat(g[..., None], 3, 2)),
                      (f"{steps} VALUE STEPS", np.repeat(post[..., None], 3, 2))):
        img, s = _scale_img(to_u8(crop(arr, zoom_t)), size, zoom_t[2], zoom_t[3])
        panels.append(titled(draw_grid(img, zoom_t, s, grid), name))
    sub = crop(g, zoom_t)
    hist = np.bincount(np.minimum((sub * steps).astype(int), steps - 1).ravel(), minlength=steps) / sub.size
    note = "share per step (dark->light): " + "  ".join(f"{v * 100:.0f}%" for v in hist)
    return titled(hstack(panels), note, 22)


def small(doc, width=480):
    """The canvas as seen small (thumbnail / far away). No grid: it is the point."""
    rgb = np.asarray(doc.composite(), np.float32)
    h, w = rgb.shape[:2]
    if width < 16 or width > w * 4:
        raise ValueError(f"--width {width}: use 16 .. {w * 4}")
    img = Image.fromarray(to_u8(rgb)).resize((width, max(1, round(h * width / w))), Image.LANCZOS)
    return titled(img, f"small: {width}px wide")
