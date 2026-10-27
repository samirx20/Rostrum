"""The native stamper (the 2D engine's `rostrum2d_stamp` library, `apps/2d/engine/stamp/`): lays a planned stroke's
dabs (`brush.plan`) with the same pixels as `brush.dabs`, bit for bit, many times faster. `lay` has `brush.dabs`'s
signature, so `brush.stamp_stroke(..., lay=native.lay)` uses it. `straight8`: premultiplied float -> straight RGBA8 for
a box, `compose.straight8`'s bytes in one call (numpy's steps when the library isn't built).

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
    return builds.newest([target / p / _NAME for p in ("release", "agent")], "the native stamper") or target / "agent" / _NAME


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
