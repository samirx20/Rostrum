"""P9 measurements: each cleanup step run cold (an empty cache of its own) in its own process, timed, with the
process's peak memory; and UMX-HQ quantized to 8-bit weights against the full model (stem SDR, time).

    <venv>\\Scripts\\python.exe measure.py <results folder>        (under heavy.ps1 gpu)
"""
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
R = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\sound-cleanup")
JOBS = {"denoise (25 s voice)": (R / "voice-noisy-roomy.wav", {"denoise": 1.0}),
        "dereverb (25 s voice)": (R / "voice-noisy-roomy.wav", {"dereverb": 0.7}),
        "isolate (60 s voice-over on music)": (R / "voice-over-on-music.wav", {"isolate": True}),
        "stems (60 s cue)": (R / "cue-mix.wav", {"stem": "vocals"})}


def peak_gb():
    class P(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong), ("peak", ctypes.c_size_t),
                    *[(f"x{i}", ctypes.c_size_t) for i in range(7)]]
    k = ctypes.WinDLL("kernel32")
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong]
    p = P()
    p.cb = ctypes.sizeof(P)
    if not k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(p), p.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return round(p.peak / 2 ** 30, 2)


def child(name):
    from rostrum_sound import cleanup
    media, recipe = JOBS[name]
    t = time.perf_counter()
    r = cleanup.make(str(media), recipe)
    print(json.dumps({"seconds": round(time.perf_counter() - t, 1), "peak_process_gb": peak_gb(), "made": r.generated}))


def quantized():
    import numpy as np
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from rostrum_sound.cleanup import audio, models, stems
    q = Path(tempfile.mkdtemp()) / "umxhq-int8.onnx"
    quantize_dynamic(str(models.path(models.UMXHQ)), str(q), weight_type=QuantType.QInt8)
    x, _ = audio.read(R / "cue-mix.wav", stems.RATE)
    t = time.perf_counter()
    full = stems.separate(x)
    t_full = time.perf_counter() - t
    import onnxruntime as ort
    real = models.session
    models.session = lambda m, device="cpu": ort.InferenceSession(str(q), providers=["CPUExecutionProvider"])
    t = time.perf_counter()
    small = stems.separate(x)
    t_q = time.perf_counter() - t
    models.session = real
    sdr = {k: round(float(10 * np.log10(np.sum(full[k] ** 2) / max(np.sum((full[k] - small[k]) ** 2), 1e-20))), 1)
           for k in full}
    out = {"int8_mb": round(q.stat().st_size / 2 ** 20, 1), "fp32_mb": round(models.UMXHQ.size / 2 ** 20, 1),
           "seconds_fp32": round(t_full, 1), "seconds_int8": round(t_q, 1), "int8_vs_fp32_sdr_db": sdr}
    audio.write(OUT / "cue-stem-vocals-int8.wav", small["vocals"], stems.RATE)
    audio.write(OUT / "cue-stem-drums-int8.wav", small["drums"], stems.RATE)
    q.unlink()
    return out


if __name__ == "__main__":
    if sys.argv[1] == "--child":
        child(sys.argv[2])
        raise SystemExit(0)
    facts = {}
    for name in JOBS:
        cache = tempfile.mkdtemp(prefix="rostrum-p9-measure-")
        p = subprocess.run([sys.executable, __file__, "--child", name], capture_output=True, text=True,
                           env={**os.environ, "ROSTRUM_CACHE_DIR": cache})
        if p.returncode:
            raise SystemExit(f"{name} failed:\n{p.stderr[-2000:]}")
        facts[name] = json.loads(p.stdout.strip().splitlines()[-1])
        subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", cache])
        print(name, facts[name], flush=True)
    facts["UMX-HQ 8-bit weights vs full"] = quantized()
    print(facts["UMX-HQ 8-bit weights vs full"])
    (OUT / "measurements-models.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")
