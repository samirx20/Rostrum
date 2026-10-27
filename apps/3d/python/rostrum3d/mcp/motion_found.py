"""look_motion's facts from a Track (rostrum3d/motion_track.py): per item its path, speed per frame, stops and sudden
jumps (the arithmetic is shared with 2D: rostrum_core.motion.spans), and the findings: leaving the picture, and two
shapes passing through each other (their oriented boxes overlap). Facts only, no scores."""
from __future__ import annotations

import itertools

from rostrum_core.motion.spans import frame_spans, jumps, moving_runs, peak, r, steps

STILL_M = 1e-5            # a step shorter than this (metres a frame) is standing still
JUMP_FLOOR_M = 0.01       # a jump is at least 1 cm in one frame (and JUMP_FACTOR times both neighbours)
DEEP_M = 5e-4             # boxes overlapping less than half a millimetre only touch (resting on the ground)
STOP_MIN_S = 0.25         # a still stretch between moves shorter than this isn't reported as a stop


def _span_words(info: dict, a: int, b: int) -> str:
    sec = lambda f: f'{r((f - info["start"]) / info["fps"], 2):g}'      # noqa: E731
    return f"frame {a} ({sec(a)} s)" if a == b else f"frames {a}–{b} ({sec(a)}–{sec(b)} s)"


def item_facts(id_: str, rows: list[dict], info: dict) -> dict:
    """Path, speed curve (m/s and on-screen px/s, one per frame after the first), stops and jumps of one item."""
    fps, frames = info["fps"], [x["frame"] for x in rows]
    world = [x["world"] for x in rows]
    step = steps(world)
    seen = [x["screen"] for x in rows]
    px = [r(steps([a, b])[0] * fps, 1) if a and b else None for a, b in zip(seen, seen[1:])]
    runs = moving_runs(step, STILL_M)
    facts = {"id": id_, "moves": bool(runs), "frames": [frames[0], frames[-1]],
             "path": {"from": [r(c, 3) for c in world[0]], "to": [r(c, 3) for c in world[-1]], "length_m": r(sum(step), 3),
                      "screen_from": [r(c, 1) for c in seen[0]] if seen[0] else None,
                      "screen_to": [r(c, 1) for c in seen[-1]] if seen[-1] else None},
             "speed_m_s": [r(d * fps, 3) for d in step], "screen_speed_px_s": px}
    if not runs:
        return facts
    top = peak(step)
    facts["moving"] = [[frames[a], frames[b]] for a, b in runs]
    facts["peak"] = {"m_s": r(step[top] * fps, 3), "frame": frames[top + 1]}
    facts["stops"] = [{"frames": [frames[a1], frames[b0]], "seconds": r((b0 - a1) / fps, 2)}
                      for (_, a1), (b0, _) in zip(runs, runs[1:]) if (b0 - a1) / fps >= STOP_MIN_S]
    facts["jumps"] = [{"frames": [frames[i], frames[i + 1]], "m": r(step[i], 3),
                       "around_m": r(max(step[j] for j in (i - 1, i + 1) if 0 <= j < len(step)), 4)}
                      for i in jumps(step, JUMP_FLOOR_M)]
    return facts


def leaving(id_: str, rows: list[dict], info: dict) -> list[dict]:
    """Frames where a shown shape is partly or wholly outside the camera's picture (by its box's corners)."""
    out = []
    for how, word in (("out", "wholly"), ("part", "partly")):
        for a, b in frame_spans([x["frame"] for x in rows if x["shown"] and x["view"] == how]):
            out.append({"kind": "leaves_frame", "item": id_, "how": word, "frames": [a, b],
                        "text": f"{id_} is {word} outside the picture at {_span_words(info, a, b)}."})
    return sorted(out, key=lambda x: x["frames"][0])


def _depth(a, b) -> float:
    """How deep two oriented boxes (corners, axes) overlap along the axis that separates them best; 0 when apart."""
    axes = [*a[1], *b[1], *([p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]]
                             for p in a[1] for q in b[1])]
    best = float("inf")
    for n in axes:
        size = sum(x * x for x in n) ** 0.5
        if size < 1e-9:
            continue
        pa = [sum(c[k] * n[k] for k in range(3)) / size for c in a[0]]
        pb = [sum(c[k] * n[k] for k in range(3)) / size for c in b[0]]
        best = min(best, min(max(pa), max(pb)) - max(min(pa), min(pb)))
        if best <= 0:
            return 0.0
    return best


def _near(a, b) -> bool:
    return all(min(p[k] for p in a[0]) <= max(p[k] for p in b[0]) and min(p[k] for p in b[0]) <= max(p[k] for p in a[0]) for k in range(3))


def passing_through(rows: dict, moving: set, info: dict) -> list[dict]:
    """Pairs of shown shapes, at least one of them moving, whose boxes overlap deeper than DEEP_M: both named, per span of frames."""
    out = []
    shapes = [i for i in rows if any(x["solid"] for x in rows[i])]
    for a, b in itertools.combinations(shapes, 2):
        if a not in moving and b not in moving:
            continue
        hit = {}
        for x, y in zip(rows[a], rows[b]):
            if x["shown"] and y["shown"] and x["solid"] and y["solid"] and _near(x["solid"], y["solid"]):
                if (d := _depth(x["solid"], y["solid"])) > DEEP_M:
                    hit[x["frame"]] = d
        for f0, f1 in frame_spans(list(hit)):
            deep = max(hit[f] for f in range(f0, f1 + 1))
            out.append({"kind": "passes_through", "items": [a, b], "frames": [f0, f1], "deepest_m": r(deep, 4),
                        "text": f"{a} and {b} overlap (pass through each other) at {_span_words(info, f0, f1)}, up to {r(deep * 100, 2):g} cm deep."})
    return out


def jump_findings(facts: list[dict], info: dict) -> list[dict]:
    around = lambda j: "standing still just before and after" if not j["around_m"] else f'at most {j["around_m"]:g} m a frame just before and after'  # noqa: E731
    return [{"kind": "jumps", "item": f["id"], "frames": j["frames"], "m": j["m"],
             "text": f'{f["id"]} jumps {j["m"]:g} m between frames {j["frames"][0]} and {j["frames"][1]} ({around(j)}).'}
            for f in facts for j in f.get("jumps", [])]
