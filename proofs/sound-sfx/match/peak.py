"""Peak memory of this process (RAM, and GPU if CUDA was used), in MB."""
import ctypes
import sys


def _peak_ram_mb() -> float:
    if sys.platform == "win32":
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")]

        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return -1.0
        return c.PeakWorkingSetSize / 2**20
    import resource
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 1024


def peak() -> dict:
    out = {"peak_ram_mb": round(_peak_ram_mb(), 1)}
    try:
        import torch
        if torch.cuda.is_available() and torch.cuda.is_initialized():
            out["peak_gpu_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    except ImportError:
        pass
    return out
