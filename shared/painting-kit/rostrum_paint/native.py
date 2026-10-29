"""The native stamper (the 2D engine's `rostrum2d_stamp` library, `apps/2d/engine/stamp/`): lays a planned stroke's
dabs (`brush.plan`) with the same pixels as `brush.dabs`, bit for bit, many times faster. `lay` has `brush.dabs`'s
signature, so `brush.stamp_stroke(..., lay=native.lay)` uses it. `straight8`: premultiplied float -> straight RGBA8 for
a box, `compose.straight8`'s bytes in one call (numpy's steps when the library isn't built). `spacing`: where a
stroke's dabs go (`brush._spacing`, a walk of a Python step per dab: thousands a stroke); `fill`: a fill's paint laid
(`marks.apply_paint` for a fill); `noise`, `blur`, `upsample`, `mix`: a wash's drying (`marks._noise`, `wash._blur`,
`wash._upsample`, `wash.dry`'s per-pixel steps); the same numbers as the Python, which stays the reference (tests/test_native.py).

The library: `ROSTRUM_STAMP_LIB`, else the engine's working build in this checkout. `available()` says whether it
is built; `lay` fails loudly when it isn't. A build of another layout (its `rostrum2d_stamp_layout`, missing in builds
before layout 3) is refused on load with what to rebuild: calling it would read the arguments wrongly and crash.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import numpy as np

from .marks import ALONG, MODES, TIPS, Coverage

LAYOUT, PARAMS, DAB = 5.0, 23, 22           # apps/2d/engine/stamp/src/lib.rs: the same numbers
_NAME = {"nt": "rostrum2d_stamp.dll", "posix": "librostrum2d_stamp.dylib"}[os.name]
_LIB = None


def lib_path() -> Path:
    env = os.environ.get("ROSTRUM_STAMP_LIB")
    if env:
        return Path(env)
    target = Path(__file__).resolve().parents[3] / "apps" / "2d" / "engine" / "target"
    from rostrum_core import builds
    from rostrum_core.engine_copy import run_exe
    found = builds.newest([target / p / _NAME for p in ("release", "agent")], "the native stamper")
    # loaded from a run copy: a library held open by a running 2D server would make cargo fail with "file in use"
    return run_exe(found, "2d-stamp", target) if found else target / "agent" / _NAME


def _lib():
    global _LIB
    if _LIB is None:
        path = lib_path()
        if not path.is_file():
            raise RuntimeError(f"the native stamper is not built: {path} (cargo build --profile agent -p rostrum2d-stamp in apps/2d/engine, or set "
                               f"ROSTRUM_STAMP_LIB)")
        lib = ctypes.CDLL(str(path))
        check_layout(lib, path)
        f = lib.rostrum2d_stamp_dabs
        f.restype = ctypes.c_int32
        f.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_size_t] + [ctypes.c_void_p] * 9 + [ctypes.c_size_t,
                                                                                         ctypes.c_char_p, ctypes.c_size_t]
        f = lib.rostrum2d_stamp_straight8
        f.restype = ctypes.c_int32
        f.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t]
        if hasattr(lib, "rostrum2d_stamp_spacing"):     # added in layout 5's later builds (an older one: the kit's Python)
            f = lib.rostrum2d_stamp_spacing
            f.restype = ctypes.c_int64
            f.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_size_t] + [ctypes.c_void_p] * 2 + [ctypes.c_size_t]
            f = lib.rostrum2d_stamp_fill
            f.restype = ctypes.c_int32
            f.argtypes = [ctypes.c_void_p] + [ctypes.c_size_t] * 3 + [ctypes.c_void_p] * 2
        if hasattr(lib, "rostrum2d_stamp_noise"):       # added later still (an older one: the kit's Python dries)
            f = lib.rostrum2d_stamp_noise
            f.restype = ctypes.c_int32
            f.argtypes = [ctypes.c_void_p] + [ctypes.c_size_t] * 2 + [ctypes.c_void_p]
            f = lib.rostrum2d_stamp_blur
            f.restype = ctypes.c_int32
            f.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_size_t] * 3
            f = lib.rostrum2d_stamp_upsample
            f.restype = ctypes.c_int32
            f.argtypes = [ctypes.c_void_p] + [ctypes.c_size_t] * 3 + [ctypes.c_double, ctypes.c_void_p] + [ctypes.c_size_t] * 2
            f = lib.rostrum2d_stamp_wash_mix
            f.restype = ctypes.c_int32
            f.argtypes = [ctypes.c_uint32, ctypes.c_size_t, ctypes.c_float, ctypes.c_void_p, ctypes.c_void_p]
        _LIB = lib
    return _LIB


class OutOfDate(RuntimeError):
    pass


def check_layout(lib, path) -> None:
    """Refuses a library built for another layout (an old build has no `rostrum2d_stamp_layout`: layout 2 or less)."""
    try:
        f = lib.rostrum2d_stamp_layout
    except AttributeError:
        built = "2 or older"
    else:
        f.restype, f.argtypes = ctypes.c_double, []
        built = f()
        if built == LAYOUT:
            return
    raise OutOfDate(f"the native stamper is out of date (built for layout {built}, this code needs {LAYOUT}): "
                    f"cargo build --profile agent -p rostrum2d-stamp in apps/2d/engine ({path})")


def available() -> bool:
    """Whether the native stamper is built; an out-of-date build raises (OutOfDate), never falls back quietly."""
    try:
        _lib()
        return True
    except OutOfDate:
        raise
    except (RuntimeError, OSError):
        return False


def walks() -> bool:
    """Whether the built library has `spacing` and `fill` (a build from before them hasn't: the kit's Python does
    them then, the same numbers, slower)."""
    return available() and hasattr(_lib(), "rostrum2d_stamp_spacing")


_DRIES = None


def dries() -> bool:
    """Whether the built library has the wash's drying (`noise`, `blur`, `upsample`); else the kit's Python does it,
    the same numbers, slower."""
    global _DRIES
    if _DRIES is None:
        _DRIES = available() and hasattr(_lib(), "rostrum2d_stamp_noise")
    return _DRIES


def _ptr(a):
    return None if a is None else a.ctypes.data


def _f32(a, shape):
    if a is None:
        return None
    if a.dtype != np.float32 or a.shape != shape or not a.flags.c_contiguous:
        raise ValueError(f"the native stamper takes C-ordered float32 {shape}, got {a.dtype} {a.shape}")
    return a


def lay(layer, P, mask=None, under=None, cov=None, res=None, res_in=False):
    """`brush.dabs`, native: lays P's dabs into `layer` (in place); its Coverage (`cov`, `res`, `res_in`: as
    `brush.dabs`'s)."""
    H, W = layer.shape[:2]
    _f32(layer, (H, W, 4))
    if not layer.flags.writeable:
        raise ValueError("the layer must be writeable")
    bx0, by0, bx1, by1 = P.bbox
    grain = float(P.grain) if P.G is not None and P.grain > 0 else 0.0
    params = np.array([LAYOUT, TIPS.index(P.tip), MODES.index(P.mode), P.Kr, P.soft, ALONG[P.tip], P.cj, P.wet,
                       P.sample_all, grain, P.r0, P.rl, P.length, bx0, by0, bx1, by1, P.D, H, W,
                       0 if P.tex is None else P.tex.shape[0], P.wrap, bool(res_in)], np.float64)
    col = lambda a: np.asarray(a, np.float64).reshape(P.n, -1)  # noqa: E731
    weak = [type(k[1]) is float for k in P.wetk]                    # numpy takes up a Python float in f32
    rows = np.ascontiguousarray(np.hstack([col(P.X), col(P.Y), col(P.R), col(P.A), col(P.cs), col(P.t), col(P.S),
                                           col(P.wetk), col(weak), col(P.wv if P.wv is not None else np.zeros(P.n)),
                                           col(P.box), col(P.at), col(P.cols),
                                           col(np.zeros(P.n) if P.again is None else P.again)]))
    assert rows.shape == (P.n, DAB)
    prof = np.ascontiguousarray(np.stack([P.prof, P.start, P.end, P.streak]), np.float64)
    cov = np.zeros((by1 - by0, bx1 - bx0), np.float32) if cov is None else _f32(cov, (by1 - by0, bx1 - bx0))
    if res_in and res is None:
        raise ValueError("res_in needs the reservoir (res)")
    res = _f32(res, (P.D, P.D, 4))
    under_row = 0
    if P.sample_all:
        if under is None or under.dtype != np.float32 or under.strides[1:] != (16, 4) or under.shape != (H, W, 3):
            raise ValueError("sample_all needs the composite below as an HxWx3 float32 view of RGBA rows")
        under_row = under.strides[0] // 4
    err = ctypes.create_string_buffer(512)
    code = _lib().rostrum2d_stamp_dabs(_ptr(params), _ptr(rows), P.n, _ptr(prof), _ptr(layer), _ptr(cov), _ptr(res),
                                       _ptr(_f32(mask, (H, W))), _ptr(_f32(P.G, (H, W)) if grain else None),
                                       _ptr(_f32(P.F, (H, W)) if P.tip == "chalk" else None),
                                       _ptr(None if P.tex is None else _f32(P.tex, (P.tex.shape[0],) * 2)),
                                       _ptr(under) if P.sample_all else None, under_row, err, len(err))
    if code:
        raise RuntimeError(f"the native stamper refused a stroke: {err.value.decode('utf-8', 'replace')}")
    return Coverage(cov, P.bbox)


def straight8(px, out=None):
    """Premultiplied float32 pixels (h x w x 4, any view of rows of RGBA: a box of a bigger canvas) as straight-alpha
    RGBA8, `compose.straight8`'s bytes, written into `out` (h x w x 4 uint8, a view of rows too: a box of a bigger
    picture) or a new array; returned. One native call when the library is built (it lets go of Python's lock for
    the whole box: numpy's six steps each waited for it); numpy's steps otherwise."""
    h, w = px.shape[:2]
    if px.dtype != np.float32 or px.shape[2:] != (4,) or px.strides[1:] != (16, 4) or px.strides[0] % 4:
        raise ValueError(f"straight8 takes float32 rows of RGBA pixels, got {px.dtype} {px.shape} {px.strides}")
    if out is None:
        out = np.empty((h, w, 4), np.uint8)
    elif out.dtype != np.uint8 or out.shape != (h, w, 4) or out.strides[1:] != (4, 1) or not out.flags.writeable:
        raise ValueError(f"straight8 writes uint8 rows of RGBA pixels {(h, w, 4)}, got {out.dtype} {out.shape} {out.strides}")
    if not h or not w:
        return out
    try:
        lib = _lib()
    except OutOfDate:
        raise
    except (RuntimeError, OSError):
        from .compose import straight8 as numpy_straight8
        out[...] = numpy_straight8(px)
        return out
    if lib.rostrum2d_stamp_straight8(_ptr(px), px.strides[0] // 4, _ptr(out), out.strides[0], h, w):
        raise RuntimeError("the native stamper refused straight8")
    return out


def spacing(L, pressure, step, sp, size, length, start, end) -> np.ndarray:
    """`brush._spacing`, native: the dabs' places along the path (px from its start), f64. `L`: the path's lengths so
    far, `pressure` its pressure there; `length`: what the taper is sized by; `start`, `end`: the taper's."""
    L, pr = np.ascontiguousarray(L, np.float64), np.ascontiguousarray(pressure, np.float64)
    if len(L) < 1 or len(pr) != len(L):
        raise ValueError(f"spacing takes the path's lengths and pressures, one each a point, got {len(L)} and {len(pr)}")
    k = np.array([step, sp, size, length, start, end], np.float64)
    out = np.empty(int(float(L[-1]) / 0.3) + 3, np.float64)     # a dab at least every 0.3 px
    n = _lib().rostrum2d_stamp_spacing(_ptr(L), _ptr(pr), len(L), _ptr(k), _ptr(out), len(out))
    if n < 0:
        raise RuntimeError("the native stamper's spacing ran past its room")
    return out[:n]


def fill(region, c, col) -> None:
    """`marks.apply_paint(region, 0, c, col, "normal")` (a fill's paint), native: `region` h x w x 4 float32 (a box of a
    layer, rows of RGBA) changed in place, `c` its coverage (h x w float32), `col` the colour (3 float32)."""
    h, w = region.shape[:2]
    if region.dtype != np.float32 or region.shape[2:] != (4,) or region.strides[1:] != (16, 4) or region.strides[0] % 4:
        raise ValueError(f"fill takes float32 rows of RGBA pixels, got {region.dtype} {region.shape} {region.strides}")
    if not region.flags.writeable:
        raise ValueError("the region must be writeable")
    c = np.ascontiguousarray(_f32(np.ascontiguousarray(c), (h, w)))
    col = np.ascontiguousarray(col, np.float32)
    if col.shape != (3,):
        raise ValueError(f"fill takes one colour (3 float32), got {col.shape}")
    if h and w and _lib().rostrum2d_stamp_fill(_ptr(region), region.strides[0] // 4, h, w, _ptr(c), _ptr(col)):
        raise RuntimeError("the native stamper refused a fill")


def noise(h, w, cell, seed, salt, origin, wrap) -> np.ndarray:
    """`marks._noise(h, w, cell, seed, salt, origin, wrap)`, native: h x w float32."""
    if wrap:
        nk = (max(1, round(w / cell)), max(1, round(h / cell)))
        div = (w / nk[0], h / nk[1])
    else:
        nk, div = (0, 0), (float(cell), float(cell))
    k = np.array([float(origin[0]), float(origin[1]), div[0], div[1],
                  (int(seed) * 0x9E3779B1 + int(salt) * 0x85EBCA6B) & 0xFFFFFFFF, nk[0], nk[1]], np.float64)
    out = np.empty((h, w), np.float32)
    if _lib().rostrum2d_stamp_noise(_ptr(out), h, w, _ptr(k)):
        raise RuntimeError(f"the native stamper refused noise {h}x{w} cell {cell}")
    return out


def blur(a, r) -> np.ndarray:
    """`wash._blur(a, r)`, native: `a` h x w float32, a new array."""
    a = np.ascontiguousarray(a, np.float32)
    out = np.empty_like(a)
    if a.ndim != 2 or r < 0:
        raise ValueError(f"blur takes h x w float32 and r >= 0, got {a.shape} {r}")
    _lib().rostrum2d_stamp_blur(_ptr(a), _ptr(out), a.shape[0], a.shape[1], int(r))
    return out


def upsample(small, f, H, W, at) -> np.ndarray:
    """`wash._upsample(small, f, H, W, at)`, native: H x W float32."""
    small = np.ascontiguousarray(_f32(small, small.shape))
    out = np.empty((H, W), np.float32)
    if small.ndim != 2 or _lib().rostrum2d_stamp_upsample(_ptr(small), small.shape[0], small.shape[1], int(f), float(at), _ptr(out), H, W):
        raise RuntimeError(f"the native stamper refused upsample {small.shape} x{f} -> {H}x{W}")
    return out


MIX = ("edge", "granulation", "pooling", "wet", "bloom")     # stamp/src/wash.rs `mix`: its kinds, in order


def mix(kind, k, fields, out) -> None:
    """One effect's per-pixel steps of `wash.dry` (stamp/src/wash.rs `mix`: which fields, which outputs, += or =):
    `fields` and `out` float32 arrays of one shape (made C-ordered), `k` the effect's NumPy f32 strength."""
    shape = out[0].shape
    fields = [_f32(np.ascontiguousarray(f), shape) for f in fields]
    for o in out:
        if o.dtype != np.float32 or o.shape != shape or not o.flags.c_contiguous or not o.flags.writeable:
            raise ValueError(f"mix writes C-ordered float32 {shape}, got {o.dtype} {o.shape}")
    fp = (ctypes.c_void_p * 4)(*[_ptr(f) for f in fields], *[None] * (4 - len(fields)))
    op = (ctypes.c_void_p * 2)(*[_ptr(o) for o in out], *[None] * (2 - len(out)))
    if _lib().rostrum2d_stamp_wash_mix(MIX.index(kind), out[0].size, float(k), fp, op):
        raise RuntimeError(f"the native stamper refused the wash's {kind}")
