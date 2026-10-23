"""The native stamper (the 2D engine's `rostrum2d_stamp` library, `apps/2d/engine/stamp/`): lays a planned stroke's
dabs (`brush.plan`) with the same pixels as `brush.dabs`, bit for bit, many times faster. `lay` has `brush.dabs`'s
signature, so `brush.stamp_stroke(..., lay=native.lay)` uses it.

The library: `ROSTRUM_STAMP_LIB`, else the engine's working build in this checkout. `available()` says whether it
loads; `lay` fails loudly when it doesn't.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path

import numpy as np

from .marks import ALONG, MODES, TIPS, Coverage

LAYOUT, PARAMS, DAB = 2.0, 21, 21           # apps/2d/engine/stamp/src/lib.rs: the same numbers
_NAME = {"nt": "rostrum2d_stamp.dll", "posix": "librostrum2d_stamp.dylib"}[os.name]
_LIB = None


def lib_path() -> Path:
    env = os.environ.get("ROSTRUM_STAMP_LIB")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "apps" / "2d" / "engine" / "target" / "agent" / _NAME


def _lib():
    global _LIB
    if _LIB is None:
        path = lib_path()
        if not path.is_file():
            raise RuntimeError(f"the native stamper is not built: {path} (cargo build -p rostrum2d-stamp, or set "
                               f"ROSTRUM_STAMP_LIB)")
        lib = ctypes.CDLL(str(path))
        f = lib.rostrum2d_stamp_dabs
        f.restype = ctypes.c_int32
        f.argtypes = [ctypes.c_void_p] * 2 + [ctypes.c_size_t] + [ctypes.c_void_p] * 8 + [ctypes.c_size_t,
                                                                                         ctypes.c_char_p, ctypes.c_size_t]
        _LIB = lib
    return _LIB


def available() -> bool:
    try:
        _lib()
        return True
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


def lay(layer, P, mask=None, under=None):
    """`brush.dabs`, native: lays P's dabs into `layer` (in place); its Coverage."""
    H, W = layer.shape[:2]
    _f32(layer, (H, W, 4))
    if not layer.flags.writeable:
        raise ValueError("the layer must be writeable")
    bx0, by0, bx1, by1 = P.bbox
    grain = float(P.grain) if P.G is not None and P.grain > 0 else 0.0
    params = np.array([LAYOUT, TIPS.index(P.tip), MODES.index(P.mode), P.Kr, P.soft, ALONG[P.tip], P.cj, P.wet,
                       P.sample_all, grain, P.R[0], P.R[-1], P.L[-1], bx0, by0, bx1, by1, P.D, H, W,
                       0 if P.tex is None else P.tex.shape[0]], np.float64)
    col = lambda a: np.asarray(a, np.float64).reshape(P.n, -1)  # noqa: E731
    weak = [type(k[1]) is float for k in P.wetk]                    # numpy takes up a Python float in f32
    rows = np.ascontiguousarray(np.hstack([col(P.X), col(P.Y), col(P.R), col(P.A), col(P.cs), col(P.t), col(P.S),
                                           col(P.wetk), col(weak), col(P.wv if P.wv is not None else np.zeros(P.n)),
                                           col(P.box), col(P.at), col(P.cols)]))
    assert rows.shape == (P.n, DAB)
    prof = np.ascontiguousarray(np.stack([P.prof, P.start, P.end, P.streak]), np.float64)
    cov = np.zeros((by1 - by0, bx1 - bx0), np.float32)
    under_row = 0
    if P.sample_all:
        if under is None or under.dtype != np.float32 or under.strides[1:] != (16, 4) or under.shape != (H, W, 3):
            raise ValueError("sample_all needs the composite below as an HxWx3 float32 view of RGBA rows")
        under_row = under.strides[0] // 4
    err = ctypes.create_string_buffer(512)
    code = _lib().rostrum2d_stamp_dabs(_ptr(params), _ptr(rows), P.n, _ptr(prof), _ptr(layer), _ptr(cov),
                                       _ptr(_f32(mask, (H, W))), _ptr(_f32(P.G, (H, W)) if grain else None),
                                       _ptr(_f32(P.F, (H, W)) if P.tip == "chalk" else None),
                                       _ptr(None if P.tex is None else _f32(P.tex, (P.tex.shape[0],) * 2)),
                                       _ptr(under) if P.sample_all else None, under_row, err, len(err))
    if code:
        raise RuntimeError(f"the native stamper refused a stroke: {err.value.decode('utf-8', 'replace')}")
    return Coverage(cov, P.bbox)
