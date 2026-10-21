"""Free memory on this computer, and the gate a model job passes before it loads (it refuses, loudly, below)."""
from __future__ import annotations

import os

from rostrum_core import RostrumError, codes


def free_gb() -> float | None:
    """Free physical memory in GB (None where it can't be read)."""
    if os.name != "nt":
        return None
    import ctypes

    class M(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("avail", ctypes.c_ulonglong), *[(f"x{i}", ctypes.c_ulonglong) for i in range(5)]]
    m = M()
    m.len = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail / 2 ** 30


def gate(where: str, what: str, need_gb: float):
    free = free_gb()
    if free is not None and free < need_gb:
        raise RostrumError(codes.NO_MEMORY, where, what, f"needs about {need_gb} GB of free memory; {free:.1f} GB is free")
