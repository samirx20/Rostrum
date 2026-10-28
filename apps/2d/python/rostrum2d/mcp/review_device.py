"""review's device facts (a phone, laptop or browser made by device(): a group holding <id>_body and <id>_screen): a device
cut by the frame edge, and why. Cut where it is placed (the camera at rest would cut it too): a layout fault. Cut only
because the camera pushed in: a nibble (its sides showing, part of it off the top or bottom) reads as an accident, a fault
naming the camera key and the fix; a deep push-in (the device fills most of the picture) is meant, kept as info. The
screen texts a push-in cuts are not named again one by one (`quiet_texts`)."""
from __future__ import annotations

from .geometry import drawn_box, flatten
from .review_sample import Sampled, runs
from . import edge_cut

DEEP = 0.6                # a pushed-in device filling this share of the frame or more is a meant close-up
PART = 0.5                # a part to push onto: a group in the device under the frame's centre, up to this share of it


def devices(comp: dict) -> list[str]:
    found, todo = [], list(comp.get("layers", []))
    while todo:
        layer = todo.pop()
        kids = {c["id"] for c in layer.get("layers", [])}
        if layer.get("type") == "group" and {f'{layer["id"]}_body', f'{layer["id"]}_screen'} <= kids:
            found.append(layer["id"])
        todo.extend(layer.get("layers", []))
    return found


def _raw(comp: dict, t: float) -> dict:
    """The layers at t where they are placed, without the camera."""
    return {n["id"]: n for n in flatten({**comp, "layers": [l for l in comp.get("layers", []) if l["type"] != "camera"]}, t)}


def _camera_key(comp: dict, t: float) -> float | None:
    cam = next((l for l in comp.get("layers", []) if l["type"] == "camera"), None)
    keys = sorted({k["t"] for k in (cam or {}).get("keys", []) if k.get("prop") in ("x", "y", "zoom") and k["t"] <= t + 1e-9})
    return keys[-1] if keys else None


def _part(s: Sampled, nodes: list[dict], did: str, body) -> str | None:
    """The biggest group inside the device under the frame's centre, up to PART of the device (a card to push onto)."""
    area = (body[2] - body[0]) * (body[3] - body[1])
    best = None
    for n in nodes:
        if n["type"] == "group" and did in n["within"] and n["in_time"] and n["opacity"] >= 0.1 and not n["id"].endswith("_screen"):
            x0, y0, x1, y1 = drawn_box(n)
            a = (x1 - x0) * (y1 - y0)
            if x0 <= s.W / 2 <= x1 and y0 <= s.H / 2 <= y1 and a <= PART * area and (best is None or a > best[0]):
                best = (a, n["id"])
    return best and best[1]


def stretches(s: Sampled) -> list[dict]:
    """Each device's cut stretches: {id, how: placed | push | deep, start, end, a, b, edges, out_pct, part}; cached on s."""
    if "_device_cuts" in s.__dict__:
        return s.__dict__["_device_cuts"]
    out = []
    for did in devices(s.comp):
        rows = []
        for i, (t, nodes) in enumerate(s.frames):
            by = {n["id"]: n for n in nodes}
            body = by.get(f"{did}_body")
            if not body or not s.seen(body) or not (edges := edge_cut.cut_edges(drawn_box(body), s.W, s.H, True)):
                rows.append(None)
                continue
            raw = _raw(s.comp, t).get(f"{did}_body")
            placed = raw is not None and edge_cut.cut_edges(drawn_box(raw), s.W, s.H, True)
            box = drawn_box(body)
            inside = s.share(box) * s.W * s.H / max((box[2] - box[0]) * (box[3] - box[1]), 1.0)
            how = "placed" if placed else "deep" if s.share(box) >= DEEP else "push"
            rows.append((how, edges, round(100 * (1 - inside)), _part(s, nodes, did, box)))
        for how in ("placed", "push", "deep"):
            for t0, t1, a, b in runs([r is not None and r[0] == how for r in rows], s.times, s.step, s.step):
                got = rows[a:b + 1]
                edges = sorted({e for r in got for e in r[1]})
                out.append({"id": did, "how": how, "start": t0, "end": t1, "a": a, "b": b, "edges": edges,
                            "out_pct": max(r[2] for r in got), "part": next((r[3] for r in got if r[3]), None),
                            "film_pct": round(100 * sum(r is not None for r in rows) / max(len(rows), 1))})
    s.__dict__["_device_cuts"] = out
    return out


def facts(s: Sampled) -> list[dict]:
    """One line per device and cause: every stretch, the longest one's camera key and part, the share of the film it is cut."""
    groups: dict[tuple, list[dict]] = {}
    for c in stretches(s):
        groups.setdefault((c["id"], c["how"]), []).append(c)
    out = []
    for (did, how), cs in groups.items():
        c = max(cs, key=lambda c: c["end"] - c["start"])
        spans = ", ".join(f'{x["start"]:g}–{x["end"]:g} s' for x in cs)
        edges, pct = " and ".join(sorted({e for x in cs for e in x["edges"]})), max(x["out_pct"] for x in cs)
        share = f'cut in {c["film_pct"]} % of the film'
        if how == "placed":
            text = (f'{spans}: device "{did}" runs off the {edges} edge where it is placed, camera aside (up to {pct} % of it '
                    f'outside, {share}): move or scale it into the frame')
        elif how == "push":
            key = _camera_key(s.comp, c["start"])
            at = f'at={key if key is not None else c["start"]:g}, '
            onto = f', or push further onto the part: frame().fit(["{c["part"]}"], {at}pad=0.04)' if c["part"] else ""
            text = (f'{spans}: camera push-ins cut device "{did}" at the {edges} edge (up to {pct} % of it outside while its sides '
                    f'still show, {share}): even when the push is meant, a device sliced at the top or bottom with its sides in view '
                    f'reads to a client as a framing mistake; a meant close-up fills the frame with one part. Longest at {c["start"]:g} s'
                    f'{f" (frame key at {key:g} s)" if key is not None else ""}: show it whole with frame().fit(["{did}"], {at}pad=0.06){onto}')
        else:
            text = (f'{spans}: deep push-ins into device "{did}" (up to {pct} % of it outside, it fills most of the picture): '
                    f'a meant close-up past its edge, not a fault')
        out.append({"kind": {"placed": "device_cut", "push": "push_cut", "deep": "push_in"}[how], "start": c["start"],
                    "end": c["end"], "id": did, "ids": [did] + ([c["part"]] if c["part"] else []), "out_pct": pct,
                    "spans": [(x["start"], x["end"]) for x in cs], "film_pct": c["film_pct"], "info": how == "deep", "text": text})
    return out


def quiet_texts(faults: list[dict], s: Sampled) -> list[dict]:
    """Texts cut by the frame edge only while a camera push-in cuts the device they sit on: named by the device line, kept as info."""
    pushed = [c for c in stretches(s) if c["how"] != "placed"]
    if not pushed:
        return faults
    inside = {n["id"]: set(n["within"]) for _, nodes in s.frames[:1] for n in nodes}

    def covered(i: str, t: float) -> bool:
        return any(c["id"] in inside.get(i, ()) and c["start"] <= t < c["end"] for c in pushed)

    for f in faults:
        ts = [t for t in s.times if f["start"] - 1e-9 <= t < max(f["end"], f["start"] + s.step) - 1e-9]
        if f["kind"] in ("text_edge", "small_text_edge") and ts and all(covered(i, t) for i in f.get("ids") or [f["id"]] for t in ts):
            f["info"] = True
    return faults
