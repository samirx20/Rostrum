"""H8 package A: scrubbing Meridian into shared memory (`pixels`), timed, with every frame's bytes hashed so two builds'
frames can be compared byte for byte.

    set PYTHONPATH=apps\\2d\\python;shared\\core;shared\\painting-kit
    .venv\\Scripts\\python.exe proofs\\2d-engine-output\\scrub.py <rostrum2d-render.exe> <scratch dir> <out.json>
"""
import hashlib
import json
import mmap
import random
import sys
import time
from pathlib import Path

from rostrum_core import Document
from rostrum2d import KIND, run_source
from rostrum2d import engine as E
from rostrum2d.scene import describe

TITLE = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\2d\agent\title.py")


def main(exe: Path, scratch: Path, out: Path):
    scratch.mkdir(parents=True, exist_ok=True)
    doc = Document.new(KIND, folder=scratch / "meridian-project", item="shot")
    doc.run_script(TITLE.name, run_source(TITLE.read_text(encoding="utf-8"), TITLE.name))
    scene = describe(doc.data)
    p = scene["comp"]["props"]
    fps, n = p["fps"], round(p["duration"] * p["fps"])
    report, hashes = {}, {}
    with E.Engine(exe) as eng:
        eng.load(scene)
        maps = {}
        for label, times in (("forward", [i / fps for i in range(n)]),
                             ("jumps", [random.Random(i).uniform(0, p["duration"]) for i in range(60)])):
            rows = []
            for t in times:
                rep = eng._request({"frame": {"t": t, "pixels": True}})
                s = rep["shm"]
                m = maps.get(s["name"]) or maps.setdefault(s["name"], mmap.mmap(-1, s["size"], tagname=s["name"]))
                if label == "forward":
                    hashes[f"{t:.4f}"] = hashlib.sha1(m[s["offset"]:s["offset"] + s["bytes"]]).hexdigest()
                rows.append({"ms": rep["ms"], **{k: rep["timing"].get(k, 0) for k in ("paintMs", "readMs", "convertMs")}})
            med = lambda k: round(sorted(r[k] for r in rows)[len(rows) // 2], 2)  # noqa: E731
            report[label] = {"frames": len(rows), "roundTripMedianMs": med("ms"),
                             "worstMs": round(max(r["ms"] for r in rows), 1),
                             **{f"{k}Median": med(k) for k in ("paintMs", "readMs", "convertMs")}}
        for m in maps.values():
            m.close()
    report["frameHashes"] = hashes
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "frameHashes"}, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
