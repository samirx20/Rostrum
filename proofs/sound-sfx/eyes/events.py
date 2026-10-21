"""`events`: validate a hand-written event sheet and render it as one picture."""
import json
import cv2
import numpy as np
from .common import open_video, read_frame, out, fail
from .frames import tile

REQUIRED = ["frame", "time_s", "objects", "material", "action", "force", "distance", "sound"]
FORCES = {"very soft", "soft", "medium", "hard"}
BG = 24


def wrap(text, width):
    lines, cur = [], ""
    for w in text.split():
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + [cur]


def row_for(cap, fps, n, k, e):
    c = e["frame"]
    end = e.get("end_frame", c)
    pts = [max(0, c - 2), c, min(n - 1, c + 1)] + ([min(n - 1, end)] if end > c + 2 else [])
    strip = np.hstack([tile(read_frame(cap, j), f"f{j} {j / fps:.2f}s", 256) for j in pts])
    txt = np.full((strip.shape[0], 400, 3), BG, np.uint8)
    dur = f" ({e['time_s']:.2f}-{end / fps:.2f}s)" if end > c else f" ({e['time_s']:.2f}s)"
    lines = (wrap(f"#{k + 1} {e['action'].upper()} - {e['objects']}{dur}", 50)
             + wrap(f"{e['material']} | {e['force']} | {e['distance']}", 54) + wrap("SOUND: " + e["sound"], 54))
    for li, line in enumerate(lines[:11]):
        cv2.putText(txt, line, (6, 18 + li * 18), cv2.FONT_HERSHEY_SIMPLEX, .42,
                    (255, 220, 120) if li == 0 else (230, 230, 230), 1, cv2.LINE_AA)
    return np.hstack([strip, txt])


def run(args):
    cap, fps, n = open_video(args.video)
    evs = json.load(open(args.events, encoding="utf-8"))["events"]
    rows = []
    for k, e in enumerate(evs):
        miss = [r for r in REQUIRED if r not in e]
        if miss:
            fail(f"event {k} missing {miss}")
        if e["force"] not in FORCES:
            fail(f"event {k} force '{e['force']}' not in {sorted(FORCES)}")
        if abs(e["frame"] / fps - e["time_s"]) > 0.021:
            fail(f"event {k}: frame {e['frame']} is {e['frame'] / fps:.3f}s, not {e['time_s']}")
        rows.append(row_for(cap, fps, n, k, e))
    wmax = max(r.shape[1] for r in rows)
    rows = [np.hstack([r, np.full((r.shape[0], wmax - r.shape[1], 3), BG, np.uint8)]) for r in rows]
    cv2.imwrite(args.out, np.vstack(rows))
    out(dict(cmd="events", count=len(evs), png=args.out))
