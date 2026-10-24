"""Does a render made right after the estimate probe run slower than one on a rested card (GPU clock throttling)? Three runs of:
fresh cache -> estimate_job.measure (the probe) -> real still at once -> 60 s idle -> the same real still again. Reuses estimate_check's
scene and real_still. Prints a table and writes %TEMP%/rostrum3d_after_probe/after_probe.json.
Result (2026-10-24, reference laptop, full HD, 128 samples, three fresh probes): no throttling. The real still took
20.5 / 21.0 / 20.5 s right after the probe and 20.1 / 20.1 / 20.7 s after 60 s rest (within 1 s, the card at 1710-1717 MHz
both times), but the probes predicted 23.1 / 21.1 / 26.4 s: the error is the probe's own run-to-run spread, not the render.
Through the lock: heavy.ps1 run "<team>: after-probe check" gpu python apps/3d/tools/after_probe_check.py (PYTHONPATH apps/3d/python;shared/core;shared/gui-kit)."""
import json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import estimate_check as ec                                      # noqa: E402  (its scene, real_still and env setup)
from rostrum_core import Document                                # noqa: E402
from rostrum_core.cache import Cache                             # noqa: E402
from rostrum3d import KIND, run_source, estimate_job             # noqa: E402
from rostrum3d.compile import describe, shot_info                # noqa: E402
from rostrum3d.render_fields import settings                     # noqa: E402
from rostrum3d.mcp import estimate                               # noqa: E402

OUT = Path(tempfile.gettempdir()) / "rostrum3d_after_probe"
RUNS, REST_S = 3, 60


def gpu():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=clocks.sm,temperature.gpu,power.draw", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "n/a"
    except Exception:
        return "n/a"


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    scratch = OUT / "project"
    scratch.mkdir()
    (scratch / "project.json").write_text('{"items": []}', encoding="utf-8")
    doc = Document.new(KIND, str(scratch), "est")
    doc.run_script("est.py", run_source(ec.SCENE, "est.py"))
    scene, info = describe(doc.data, "s", None), shot_info(doc.data, "s")
    s = settings({"renderQuality": "good"}, info)
    s["start"] = s["end"] = (s["start"] + s["end"]) // 2
    rows = []
    for i in range(1, RUNS + 1):
        estimate_job.CACHE = Cache(OUT / f"cache{i}")                  # fresh cache each run: the probe really measures
        t0 = time.perf_counter()
        m = estimate_job.measure(scene, info, s)
        probe_s = time.perf_counter() - t0
        pred = estimate.scale(m, s, 1, mp4=False)["seconds"]
        g1 = gpu()
        after = ec.real_still(scene, info, s)[0]
        time.sleep(REST_S)
        g2 = gpu()
        rested = ec.real_still(scene, info, s)[0]
        rows.append({"run": i, "predicted_s": pred, "probe_s": round(probe_s, 1), "after_s": round(after, 1), "rested_s": round(rested, 1),
                     "after_err_pct": round((pred - after) / after * 100, 1), "rested_err_pct": round((pred - rested) / rested * 100, 1),
                     "gpu_before_after": g1, "gpu_before_rested": g2, "cached": m["cached"], "gpu_busy": m["gpu_busy"]})
        print(json.dumps(rows[-1]), flush=True)
    (OUT / "after_probe.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f'\n{"run":>3}{"pred s":>8}{"after s":>9}{"err %":>8}{"rested s":>10}{"err %":>8}  clocks MHz,C,W before-after | before-rested')
    for r in rows:
        print(f'{r["run"]:>3}{r["predicted_s"]:>8}{r["after_s"]:>9}{r["after_err_pct"]:>8}{r["rested_s"]:>10}{r["rested_err_pct"]:>8}  {r["gpu_before_after"]} | {r["gpu_before_rested"]}')


if __name__ == "__main__":
    try:
        main()
    finally:
        for p in OUT.glob("cache*"):
            shutil.rmtree(p, ignore_errors=True)
        shutil.rmtree(OUT / "project", ignore_errors=True)
        shutil.rmtree(ec.OUT, ignore_errors=True)
