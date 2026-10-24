"""The render time estimate, measured, never guessed (SPEC §11.2): a probe through the same engine path as the real job.

`measure()` starts its own engine (as the Render button does), loads the shot's scene and renders the shot's middle frame
four times, each request a different size (the engine answers a repeat, or the same size with fewer samples, from the
picture it already has, so that would measure nothing; 2 px less costs nothing): tiny (it pays the kernel compile and
first sync, the warm-up); at a quarter of the pixels with FEW samples and with the job's samples (kept as the probe
picture); and once at the job's REAL size with FEW samples (noise clean-up as the
job), about 5 s at full HD.

What the reference laptop showed (2026-10-24, full HD, 8 / 32 / 128 samples: 5.0 / 12.5 / 19.8 s; at a quarter
0.7 / 1.85 / 3.3-4.2 s): a full-size frame costs 5-7× a quarter-size one, so it must be measured, not scaled up; time
grows with samples far less than in step (adaptive sampling) and close to a straight line in log(samples), at full
size more gently than at a quarter; and taking the real-size frame to the job's samples by
the quarter's ratio overshoots about as much as adding the quarter's extra time per pixel undershoots, so the frame at
the job's samples is their geometric mean. The line through the quarter-size point and that real-size point gives a
frame's fixed part (it may be below 0: the line holds between the two sizes; scale() never goes under the quarter's
cost per pixel) and its part per pixel. The sample curve is the real-size frame's own: "curve": [[FEW, its time at FEW
over its time at the job's samples], [samples, 1.0]], straight in log(samples). `mcp/estimate.scale()` turns that into the job's time for any size,
samples and frame count without a new probe.

The measurement is cached (rostrum_core.cache) by the scene, the engine build and what changes the picture's cost other
than size, samples and frames (renderer, noise clean-up, the shot's shape), so changing the scene re-measures and
changing only those three re-scales at once. The probe has a wall-time budget, kept by the caller's wait (see measure):
past it the engine is ended (our own child, by its PID) and the error says the job is at least that slow.

The graphics card: before the probe, `gpu_busy.busy()` checks whether another job is using it. Its sentence ("" when
free) is in every measurement as "gpu_busy" (read it with `card_note(m)`). A probe taken on a busy card is slower than
the truth, so it is never kept under the scene's key: it goes into an entry of its own (the key salted with the time),
which `cached()` and later `measure()` calls never find, so the next ask on a free card measures again. A clean
measurement read back from the cache carries the card's state of now, so the caveat is always current.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path

from rostrum_core.cache import CACHE, cache_key, file_hash
from rostrum_core.errors import RostrumError, codes

from . import gpu_busy
from .engine import Engine
from .runtime import VERSION as LIBS

KIND, VERSION = "3d-estimate", "probe@4"
BUDGET_S = 90.0
FEW = 8                                                  # samples of the real-size frame


def probe_key(scene: dict, s: dict, exe, salt: str = "") -> str:
    return cache_key(KIND, f"rostrum3d-core@{file_hash(exe)[:16]}+{LIBS}", [json.dumps(scene, sort_keys=True)],
                     {"v": VERSION, "renderer": s["renderer"], "denoise": s.get("denoise", True),
                      "shape": round(s["width"] / s["height"], 4), **({"busy": salt} if salt else {})})


def cached(scene: dict, s: dict, exe=None) -> dict | None:
    """The stored clean measurement for this scene and settings, or None (then the screen shows "Measuring…")."""
    folder = CACHE.get(KIND, probe_key(scene, s, exe or Engine().exe))
    return _read(folder, cached=True) if folder else None


def card_note(m: dict) -> str:
    """The graphics-card caveat of a measurement: "" or one plain sentence to show beside the estimate."""
    return m.get("gpu_busy", "")


def _read(folder: Path, cached: bool) -> dict:
    """The measurement, with the probe's picture (kept so the sheet shows what is about to be rendered)."""
    return {**json.loads((folder / "probe.json").read_text(encoding="utf-8")), "picture": str(folder / "probe.png"), "cached": cached}


def measure(scene: dict, info: dict, s: dict, where: str = "render_estimate", budget_s: float = BUDGET_S, make_engine=Engine,
            card=gpu_busy.busy, own_pids=()) -> dict:
    """The measurement (kept when the card was free). `s`: render_fields.settings(). `own_pids`: the caller's own
    programs on the card (the window's viewport engine), not counted as another job. Blocking: call it from a job.

    The budget is kept by the one waiting here, not by the work: the card check, the engine's start, the scene and the
    test frames all run on a thread of their own, and when `budget_s` is up, whatever that thread is stuck on (a reply
    that never comes, a driver call), its engine is ended by its PID and a RENDER_FAILED error says so."""
    box, done, engines = {}, threading.Event(), []

    def made():
        engines.append(e := make_engine())
        return e

    def work():
        try:
            box["m"] = _measure(scene, info, s, where, made, card, own_pids)
        except BaseException as e:  # noqa: BLE001  handed to the waiter, which raises it
            box["e"] = e
        finally:
            for e in engines:
                e.close()
            done.set()
    threading.Thread(target=work, name="render-estimate-probe", daemon=True).start()
    if not done.wait(budget_s):
        for e in engines:
            e.kill()                                     # our own engine, by its PID; the thread then fails and ends
        raise RostrumError(codes.RENDER_FAILED, where, f"the time probe of {info['id']}",
                           f"ran over its {budget_s:.0f} s budget (a few test frames, a quarter-size and a real-size one), "
                           f"so one frame of the real job takes well over {budget_s / 60:.1f} min, or the engine stopped answering; "
                           "its engine was ended", hint="Lower the quality or the size, then ask again.")
    if "e" in box:
        e = box["e"]
        raise e if isinstance(e, RostrumError) else RostrumError(codes.RENDER_FAILED, where, f"the time probe of {info['id']}",
                                                                 f"failed: {e}") from e
    return box["m"]


def _measure(scene, info, s, where, make_engine, card, own_pids) -> dict:
    note = card(own_pids)                                        # before our own engine touches the card
    engine = make_engine()
    key = probe_key(scene, s, engine.exe)
    if (folder := CACHE.get(KIND, key)) is not None:
        return {**_read(folder, cached=True), "gpu_busy": note}

    def make(tmp: Path):
        m = _probe(engine, scene, info, s, tmp)
        (tmp / "probe.json").write_text(json.dumps({**m, "gpu_busy": note}), encoding="utf-8")
    if note:                                             # a busy-card probe: its own entry, never found as the scene's
        key = probe_key(scene, s, engine.exe, salt=f"{time.time_ns()}")
    return _read(CACHE.put(KIND, key, make, {"shot": info["id"], "gpu_busy": bool(note)}), cached=False)


def _probe(engine, scene: dict, info: dict, s: dict, out: Path) -> dict:
    frame, S = (s["start"] + s["end"]) // 2, s.get("samples", 0)
    q, full = _size(s, 2), (s["width"], s["height"])     # a quarter of the pixels; the real size
    q_lo = (q[0] - 2, q[1] - 2)                          # 2 px smaller: a new size makes the engine start afresh
    cycles = s["renderer"] == "cycles"
    few = min(S, FEW) if cycles and S > FEW else 0       # 0: no sample curve (Storm, or the job's samples are few already)
    t0 = time.perf_counter()
    engine.ensure_scene(scene)
    load_ms = (time.perf_counter() - t0) * 1000
    one = lambda wh, png, n=S: _frame_ms(engine, info, {**s, "samples": n}, frame, wh, png)  # noqa: E731
    with tempfile.TemporaryDirectory(prefix="rostrum3d_probe_") as tmp:
        first = one(_size(s, 16), Path(tmp) / "a.png")                 # warm-up: a tiny frame (kernels, first sync)
        q_few = one(q_lo, Path(tmp) / "c.png", few) if few else None
        warm_q = one(q, out / "probe.png")
        full_few = one(full, Path(tmp) / "f.png", few or S)
    pq, pf = q[0] * q[1], full[0] * full[1]
    full_s = full_few
    curve = []
    if few and warm_q > 0:                               # see the docstring: the geometric mean of two bounds
        full_s = ((full_few * warm_q / max(q_few, 1e-3)) * (full_few + (warm_q - q_few) * pf / pq)) ** 0.5
        curve = [[few, round(min(1.0, full_few / full_s), 4)], [S, 1.0]]
    per_px = max(0.0, (full_s - warm_q) / (pf - pq)) if pf > pq else 0.0       # ms a pixel at the job's samples
    fixed = warm_q - per_px * pq                         # ms a frame whatever its size (may be < 0, see the docstring)
    return {"frame": frame, "samples": S, "curve": curve, "load_ms": round(load_ms, 1),
            "warmup_ms": round(first, 1), "fixed_ms": round(fixed, 2), "per_px_ms": per_px,
            "probe": {"size": list(q), "ms": [round(first, 1), round(warm_q, 1)], "few_ms": round(q_few or 0, 1)},
            "full": {"size": list(full), "samples": few or S, "ms": round(full_few, 1), "at_job_samples_ms": round(full_s, 1)},
            "probe_s": round(time.perf_counter() - t0, 1), "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S")}


def _size(s: dict, k: int) -> tuple[int, int]:
    return max(16, s["width"] // k), max(16, s["height"] // k)


def _frame_ms(engine, info, s, frame, wh, png: Path) -> float:
    cyc = {"samples": s["samples"], "denoise": s["denoise"]} if s["renderer"] == "cycles" else {}
    r = engine.render(camera=info["camera"], renderer=s["renderer"], frame=frame, width=wh[0], height=wh[1], png=str(png), **cyc)
    return float(r["frames"][0]["ms"])
