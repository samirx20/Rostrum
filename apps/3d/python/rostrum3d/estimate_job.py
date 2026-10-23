"""The render time estimate, measured, never guessed (SPEC §11.2): a probe through the same engine path as the real job.

`measure()` starts its own engine (as the Render button does), loads the shot's scene and renders the shot's middle frame
at a quarter of the pixels, twice (the first also pays the kernel compile and first sync), then once at a sixteenth, then once at a quarter of the samples (to split the per-pixel time into a part
that grows with samples and a part that does not).
From those it keeps: the start-up cost (engine + scene + warm-up), and a frame's cost as a fixed part plus a part per
pixel. `mcp/estimate.scale()` turns that into the job's time for any size, samples and frame count without a new probe.

The measurement is cached (rostrum_core.cache) by the scene, the engine build and what changes the picture's cost other
than size, samples and frames (renderer, noise clean-up, the shot's shape), so changing the scene re-measures and
changing only those three re-scales at once. The probe has a wall-time budget: past it the engine is ended (our own
child, by its handle) and the error says the job is at least that slow.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path

from rostrum_core.cache import CACHE, cache_key, file_hash
from rostrum_core.errors import RostrumError, codes

from .engine import Engine
from .runtime import VERSION as LIBS

KIND, VERSION = "3d-estimate", "probe@2"
BUDGET_S = 90.0


def probe_key(scene: dict, s: dict, exe) -> str:
    return cache_key(KIND, f"rostrum3d-core@{file_hash(exe)[:16]}+{LIBS}", [json.dumps(scene, sort_keys=True)],
                     {"v": VERSION, "renderer": s["renderer"], "denoise": s.get("denoise", True),
                      "shape": round(s["width"] / s["height"], 4)})


def cached(scene: dict, s: dict, exe=None) -> dict | None:
    """The stored measurement for this scene and settings, or None (then the screen shows "Measuring…")."""
    folder = CACHE.get(KIND, probe_key(scene, s, exe or Engine().exe))
    return _read(folder, cached=True) if folder else None


def _read(folder: Path, cached: bool) -> dict:
    """The measurement, with the probe's picture (kept so the sheet shows what is about to be rendered)."""
    return {**json.loads((folder / "probe.json").read_text(encoding="utf-8")), "picture": str(folder / "probe.png"), "cached": cached}


def measure(scene: dict, info: dict, s: dict, where: str = "render_estimate", budget_s: float = BUDGET_S, make_engine=Engine) -> dict:
    """The measurement (cached). `s`: render_fields.settings(). Blocking: call it from a job."""
    engine = make_engine()
    try:
        key = probe_key(scene, s, engine.exe)
        if (folder := CACHE.get(KIND, key)) is not None:
            return _read(folder, cached=True)

        def make(tmp: Path):
            m = _probe(engine, scene, info, s, where, budget_s, tmp)
            (tmp / "probe.json").write_text(json.dumps(m), encoding="utf-8")
        return _read(CACHE.put(KIND, key, make, {"shot": info["id"]}), cached=False)
    finally:
        engine.close()


def _probe(engine, scene: dict, info: dict, s: dict, where: str, budget_s: float, out: Path) -> dict:
    over = threading.Event()

    def stop():                                          # the budget is up: end our own engine process by its handle
        over.set()
        if engine.proc is not None and engine.proc.poll() is None:
            engine.proc.kill()
    timer = threading.Timer(budget_s, stop)
    timer.start()
    frame = (s["start"] + s["end"]) // 2
    q, x = _size(s, 2), _size(s, 4)                      # a quarter of the pixels, a sixteenth
    t0 = time.perf_counter()
    try:
        engine.ensure_scene(scene)
        load_ms = (time.perf_counter() - t0) * 1000
        one = lambda wh, png: _frame_ms(engine, info, s, frame, wh, png)  # noqa: E731
        with tempfile.TemporaryDirectory(prefix="rostrum3d_probe_") as tmp:
            first_q, warm_q, warm_x = one(q, Path(tmp) / "a.png"), one(q, out / "probe.png"), one(x, Path(tmp) / "b.png")
            lo = max(1, s["samples"] // 4) if s["renderer"] == "cycles" else 0
            warm_lo = _frame_ms(engine, info, {**s, "samples": lo}, frame, q, Path(tmp) / "c.png") if 0 < lo < s["samples"] else None
    except Exception as e:
        if over.is_set():
            raise RostrumError(codes.RENDER_FAILED, where, f"the time probe of {info['id']}",
                               f"ran over its {budget_s:.0f} s budget at a quarter of the size, so one frame of the real job "
                               f"takes well over {budget_s * 4 / 60:.0f} min", hint="Lower the quality or the size, then ask again.") from e
        raise RostrumError(codes.RENDER_FAILED, where, f"the time probe of {info['id']}", f"failed: {e}") from e
    finally:
        timer.cancel()
    pq, px = q[0] * q[1], x[0] * x[1]
    per_px = max(0.0, (warm_q - warm_x) / (pq - px))     # ms a pixel at the probe's samples
    fixed = max(0.0, warm_q - per_px * pq)               # ms a frame whatever its size (sync, writing, the stage's time)
    # ms a pixel gains per extra sample: denoise, film and writing do not grow with samples, so time is NOT proportional to them
    per_px_sample = max(0.0, (warm_q - warm_lo) / (pq * (s["samples"] - lo))) if warm_lo is not None else per_px / max(1, s.get("samples", 1))
    return {"frame": frame, "samples": s.get("samples", 0), "load_ms": round(load_ms, 1), "warmup_ms": round(max(0.0, first_q - warm_q), 1),
            "fixed_ms": round(fixed, 2), "per_px_ms": per_px, "per_px_sample_ms": per_px_sample, "probe": {"size": list(q), "ms": [round(first_q, 1), round(warm_q, 1)]},
            "small": {"size": list(x), "ms": round(warm_x, 1)}, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def _size(s: dict, k: int) -> tuple[int, int]:
    return max(16, s["width"] // k), max(16, s["height"] // k)


def _frame_ms(engine, info, s, frame, wh, png: Path) -> float:
    cyc = {"samples": s["samples"], "denoise": s["denoise"]} if s["renderer"] == "cycles" else {}
    r = engine.render(camera=info["camera"], renderer=s["renderer"], frame=frame, width=wh[0], height=wh[1], png=str(png), **cyc)
    return float(r["frames"][0]["ms"])
