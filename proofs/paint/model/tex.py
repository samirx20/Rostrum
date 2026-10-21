"""Textures and images: load / save as float sRGB 0..1, bilinear sampling, texel density.
One place for image I/O and filtering in model/."""
import os
import numpy as np
from PIL import Image, ImageDraw
import scene

_cache = {}


def load(path, rgba=False):
    """Image file -> float32 (H,W,3) or (H,W,4) sRGB 0..1 (16-bit greyscale kept precise)."""
    key = (os.path.abspath(path), os.path.getmtime(path), rgba)
    if key not in _cache:
        im = Image.open(path)
        if im.mode in ("I;16", "I"):
            a = np.asarray(im, np.float32) / 65535.0
            a = np.repeat(a[..., None], 3, -1)
        else:
            a = np.asarray(im.convert("RGBA" if rgba else "RGB"), np.float32) / 255.0
        if rgba and a.shape[-1] == 3:
            a = np.concatenate([a, np.ones_like(a[..., :1])], -1)
        _cache[key] = a
    return _cache[key]


def material_texture(material, override=None):
    return load(override or scene.texture_path(material))


def save(path, img):
    a = np.clip(np.asarray(img, np.float32), 0, 1)
    mode = "RGBA" if a.ndim == 3 and a.shape[-1] == 4 else "RGB"
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8), mode).save(path)
    return path


def bilinear(img, x, y, wrap=False):
    """Sample img (H,W,C) at continuous pixel coords (x, y: pixel centres at i + 0.5).
    wrap=True repeats (textures); False clamps to the edge (screen layers)."""
    H, W = img.shape[:2]
    fx, fy = np.asarray(x, float) - 0.5, np.asarray(y, float) - 0.5
    x0, y0 = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
    ax, ay = (fx - x0)[..., None], (fy - y0)[..., None]
    if wrap:
        xi = [np.mod(x0, W), np.mod(x0 + 1, W)]; yi = [np.mod(y0, H), np.mod(y0 + 1, H)]
    else:
        xi = [np.clip(x0, 0, W - 1), np.clip(x0 + 1, 0, W - 1)]
        yi = [np.clip(y0, 0, H - 1), np.clip(y0 + 1, 0, H - 1)]
    top = img[yi[0], xi[0]] * (1 - ax) + img[yi[0], xi[1]] * ax
    bot = img[yi[1], xi[0]] * (1 - ax) + img[yi[1], xi[1]] * ax
    return top * (1 - ay) + bot * ay


def texel_density(sc, cam, size_of):
    """Per triangle: texels per frame pixel, linear (sqrt of texel area / screen area).
    size_of(material_index) -> (W, H) of that material's texture."""
    x, y, _ = cam.to_frame(sc["P"])
    sa = np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0]) - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])) / 2
    uv = sc["UV"]
    ua = np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1])
                - (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1])) / 2
    sizes = np.array([size_of(m) for m in range(len(sc["materials"]))], float)
    wh = sizes[sc["obj_material"][sc["tri_obj"]]]
    return np.sqrt(ua * wh[:, 0] * wh[:, 1] / np.maximum(sa, 1e-9))


def heat(v, lo, hi):
    """Scalar -> blue..green..yellow..red colour ramp (v clipped to lo..hi)."""
    t = np.clip((np.asarray(v, float) - lo) / (hi - lo), 0, 1)[..., None]
    stops = np.array([[0.15, 0.2, 0.8], [0.1, 0.75, 0.6], [0.95, 0.9, 0.2], [0.9, 0.2, 0.15]])
    k = np.minimum((t * 3).astype(int), 2); f = t * 3 - k
    return stops[k[..., 0]] * (1 - f) + stops[k[..., 0] + 1] * f


def legend(im, lo, hi, label, ticks):
    """Draw a heat legend bar on a PIL image (bottom-left)."""
    d = ImageDraw.Draw(im)
    x0, y0, w, h = 20, im.height - 60, 360, 18
    for i in range(w):
        c = heat(lo + (hi - lo) * i / (w - 1), lo, hi)
        d.line([(x0 + i, y0), (x0 + i, y0 + h)], fill=tuple(int(v * 255) for v in c))
    d.rectangle([x0 - 4, y0 - 26, x0 + w + 4, y0 + h + 26], outline=(255, 255, 255))
    d.text((x0, y0 - 22), label, fill=(255, 255, 255), font_size=16)
    for val, txt in ticks:
        tx = x0 + (val - lo) / (hi - lo) * (w - 1)
        d.line([(tx, y0 + h), (tx, y0 + h + 5)], fill=(255, 255, 255))
        d.text((tx - 10, y0 + h + 6), txt, fill=(255, 255, 255), font_size=14)
    return im
