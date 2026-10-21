"""A 3-second animated shot driven from Python through the archive renderer, encoded to mp4.

Python holds the document (layers with base styles) and its keyframes, evaluates every property at each frame
and sends that frame's stage markup; Rust (rostrum-motion serve) diffs it into the kept page, restyles, lays
out, paints on the GPU and pipes the pixels straight into ffmpeg.

  python shot.py <scratch dir> <out.mp4> [fps]
"""
import json
import sys
import time
from pathlib import Path

import frames
from rostrum2d import Renderer, ffmpeg_h264

DUR = 3.0


def bezier(x1, y1, x2, y2):
    """CSS cubic-bezier easing, solved by bisection (fine for a proof)."""
    def f(t):
        lo, hi = 0.0, 1.0
        for _ in range(40):
            m = (lo + hi) / 2
            x = 3 * (1 - m) ** 2 * m * x1 + 3 * (1 - m) * m * m * x2 + m ** 3
            lo, hi = (m, hi) if x < t else (lo, m)
        m = (lo + hi) / 2
        return 3 * (1 - m) ** 2 * m * y1 + 3 * (1 - m) * m * m * y2 + m ** 3
    return f


EASE = {"out": bezier(.16, 1, .3, 1), "inout": bezier(.65, 0, .35, 1), "linear": lambda t: t}


def track(keys, t):
    """keys: [(time, value, ease into this key)]; values are numbers."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0, _), (t1, v1, ease) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * EASE[ease]((t - t0) / (t1 - t0))
    return keys[-1][1]


# The document: layers, each with a markup template whose {names} are animated properties.
LAYERS = [
    ("orb1", '<div class="abs orb" style="left:{x}px;top:180px;width:640px;height:640px;opacity:{o};'
             'background:radial-gradient(circle at 35% 35%, #ff6a3d, #c2185b 60%, #4a148c)"></div>',
     {"x": [(0, 160, "out"), (3, 360, "inout")], "o": [(0, 0, "out"), (1.0, 1, "out")]}),
    ("orb2", '<div class="abs orb" style="left:{x}px;top:360px;width:720px;height:560px;opacity:{o};'
             'background:linear-gradient(140deg, #00c6ff, #0072ff 50%, #7b2ff7)"></div>',
     {"x": [(0, 1260, "out"), (3, 1000, "inout")], "o": [(0.2, 0, "out"), (1.2, 1, "out")]}),
    ("ring", '<div class="abs ringglow" style="transform:rotate({r}deg) scale({s});opacity:{o}"></div>'
             '<div class="abs ring" style="transform:rotate({r}deg) scale({s});opacity:{o}"></div>',
     {"r": [(0, -40, "out"), (3, 40, "linear")], "s": [(0, .8, "out"), (1.6, 1, "out")], "o": [(0, 0, "out"), (1.0, 1, "out")]}),
    ("pro", '<div class="abs" style="left:0;right:0;top:250px;text-align:center;font-size:400px;line-height:1;'
            'font-weight:{w};letter-spacing:{ls}em;color:#fff;transform:translateY({y}px);'
            'text-shadow:0 0 60px rgba(255,140,90,{g});'
            '-webkit-mask-image:linear-gradient(180deg,#000 {m}%,rgba(0,0,0,0) {m2}%);'
            'mask-image:linear-gradient(180deg,#000 {m}%,rgba(0,0,0,0) {m2}%)">Pro</div>',
     {"w": [(0.3, 200, "out"), (2.2, 860, "out")], "ls": [(0.3, .12, "out"), (2.2, -.06, "out")],
      "y": [(0.3, 80, "out"), (1.8, 0, "out")], "g": [(1.2, 0, "out"), (2.6, .8, "out")],
      "m": [(0.3, -40, "out"), (2.0, 70, "out")], "m2": [(0.3, 0, "out"), (2.0, 100, "out")]}),
    ("card", '<div class="abs card" style="left:560px;top:{y}px;width:800px;height:150px;opacity:{o}">'
             '<div class="abs" style="left:0;right:0;top:44px;text-align:center;font-size:52px;font-weight:300;'
             'letter-spacing:{ls}em;color:#fff">BEYOND PRO</div></div>',
     {"y": [(1.4, 1000, "out"), (2.6, 820, "out")], "o": [(1.4, 0, "out"), (2.2, 1, "out")],
      "ls": [(1.4, .5, "out"), (3.0, .16, "out")]}),
]

CSS = frames.CSS["reveal"].replace("conic-gradient(from 210deg", "conic-gradient(from 210deg") + """
#rostrum-stage { background: radial-gradient(120% 90% at 50% 110%, #1a0b2e 0%, #07040d 55%, #000 100%); }
.orb { border-radius: 50%; filter: blur(80px); }
.card { border-radius: 75px; background: linear-gradient(160deg, rgba(255,255,255,.16), rgba(255,255,255,.04));
  backdrop-filter: blur(40px) saturate(180%); border: 1px solid rgba(255,255,255,.22);
  box-shadow: 0 40px 120px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.35); }
"""


def stage_at(t: float) -> str:
    out = []
    for _, tpl, props in LAYERS:
        vals = {k: round(track(keys, t), 4) for k, keys in props.items()}
        out.append(tpl.format(**vals))
    return "".join(out)


def main(scratch: Path, mp4: Path, fps: int):
    scratch.mkdir(parents=True, exist_ok=True)
    n = int(DUR * fps)
    py_ms, rt_ms, rows = [], [], []
    t_all = time.perf_counter()
    with Renderer(scratch / "renderer-shot.log") as r:
        opened = r.open(frames.W, frames.H, frames.shell(CSS), encode=ffmpeg_h264(mp4, frames.W, frames.H, fps))
        for i in range(n):
            t0 = time.perf_counter()
            stage = stage_at(i / fps)  # Python: evaluate every keyframe track, write the markup
            py_ms.append((time.perf_counter() - t0) * 1000)
            rep = r.encode_frame(stage, i)  # Rust: diff, restyle, layout, paint, read back, hand to ffmpeg
            rt_ms.append(rep["roundTripMs"])
            rows.append(rep.get("timing", {}))
        fin = r.finish()
        peak_mb = r.peak_memory_mb()
    total = time.perf_counter() - t_all
    if not mp4.exists() or mp4.stat().st_size == 0:
        raise RuntimeError(f"no video written: {mp4}")
    med = lambda v: sorted(v)[len(v) // 2]
    tk = lambda k: med([row.get(k, 0) for row in rows[1:]])
    summary = {"frames": n, "fps": fps, "wallSeconds": round(total, 2), "open": opened.get("timing"),
               "adapter": opened.get("adapter"), "finish": fin, "rendererPeakMemoryMB": round(peak_mb),
               "medianMs": {"python": round(med(py_ms), 3), "roundTrip": round(med(rt_ms[1:]), 2),
                            "diff": tk("diffMs"), "layout": tk("layoutMs"), "paint": tk("paintMs"),
                            "record": tk("recordMs"), "gpu": tk("gpuMs"), "encoderWait": tk("encodeWaitMs")},
               "maxRoundTripMs": round(max(rt_ms[1:]), 1), "firstFrameMs": round(rt_ms[0], 1)}
    print(json.dumps(summary, indent=1))
    (scratch / "shot-timing.json").write_text(json.dumps({"summary": summary, "frames": rows}, indent=1), encoding="utf-8")
    return summary


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 60)
