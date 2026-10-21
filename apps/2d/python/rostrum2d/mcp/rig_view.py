"""Rig facts for agents: the skeleton drawn over a frame, and the IK chains' motion read from the engine's posed bones.
Facts only (ids, times, pixels); no scores. The engine poses (`Engine.bones`); this file only draws and measures."""
from __future__ import annotations

import math
from pathlib import Path

from rostrum_core.errors import RostrumError, codes

from rostrum2d.camera.view import undo
from rostrum2d.evaluate import value_at

PIN_ON = 0.5                  # RIG.md: a pin is held while its value is >= 0.5
SLIDE_PX = 0.5                # a pinned tip that moves more than this is sliding
BONE, PIVOT, TARGET, PINNED = (255, 214, 10), (255, 255, 255), (255, 59, 48), (48, 209, 88)


def rig_layers(comp: dict) -> dict[str, dict]:
    """{rig id: the rig layer} for every rig in the composition, groups and rigs included."""
    found, todo = {}, list(comp.get("layers", []))
    while todo:
        layer = todo.pop()
        if layer.get("type") == "rig":
            found[layer["id"]] = layer
        todo.extend(layer.get("layers", []))
    return found


def iks_of(rig: dict) -> dict[str, dict]:
    return {ik["id"]: ik for ik in rig.get("iks", [])}


def pin_at(ik: dict, t: float) -> float:
    try:
        return float(value_at({"type": "ik", **ik}, "pin", t))
    except KeyError:
        return 0.0


def posed(eng_rigs: dict, comp: dict, where: str) -> dict:
    """The engine's rigs checked against the document: a rig the document has but the engine didn't pose is loud."""
    missing = [r for r in rig_layers(comp) if r not in eng_rigs]
    if missing:
        raise RostrumError(codes.RENDER_FAILED, where, f'rig {", ".join(missing)}', "was not posed by the engine", hint="Is the engine build new enough for rigs?")
    return eng_rigs


def draw_skeleton(png: Path, rigs: dict, comp: dict, t: float, dest: Path, comp_w: int) -> tuple[int, int]:
    """Write `png` with every posed bone, IK target and pin drawn on it to `dest`; positions are screen px (the engine's,
    through the camera)."""
    from PIL import Image, ImageDraw
    img = Image.open(png).convert("RGBA")
    k = img.width / comp_w
    d = ImageDraw.Draw(img)
    r = max(3, round(4 * k))
    pins = {(rid, i): pin_at(ik, t) >= PIN_ON for rid, layer in rig_layers(comp).items() for i, ik in iks_of(layer).items()}
    for rig in rigs.values():
        for bid, b in rig["bones"].items():
            d.line([(b["x"] * k, b["y"] * k), (b["tipX"] * k, b["tipY"] * k)], fill=BONE, width=max(2, round(2 * k)))
            d.text((b["x"] * k + r + 2, b["y"] * k - r - 8), bid, fill=BONE)
        for b in rig["bones"].values():
            d.ellipse([b["x"] * k - r, b["y"] * k - r, b["x"] * k + r, b["y"] * k + r], fill=PIVOT, outline=(0, 0, 0))
    for rid, rig in rigs.items():
        for iid, ik in rig["iks"].items():
            x, y, s = ik["targetX"] * k, ik["targetY"] * k, 2 * r
            pinned = pins.get((rid, iid), False)
            col = PINNED if pinned else TARGET
            d.line([(x - s, y), (x + s, y)], fill=col, width=2)
            d.line([(x, y - s), (x, y + s)], fill=col, width=2)
            if pinned:
                d.rectangle([x - s, y - s, x + s, y + s], outline=col, width=2)
    img.convert("RGB").save(dest, "PNG")
    return img.width, img.height


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def chain_facts(samples: list[dict], rig: dict, iid: str, rid: str, where: str) -> dict:
    """One IK chain over the sampled frames ({"t", "rigs"}): the tip's path, its largest gap, and each pinned span's drift,
    in comp px: the engine's screen px with the camera undone, so a moving camera doesn't make a planted foot slide."""
    ik = iks_of(rig)[iid]
    bone = ik.get("bone")
    pts, gaps, pinned = [], [], []
    for s in samples:
        eng = s["rigs"][rid]
        if bone not in eng["bones"]:
            raise RostrumError(codes.RENDER_FAILED, where, f'bone "{bone}" of ik {iid}', "was not posed by the engine")
        b = eng["bones"][bone]
        cam = eng.get("camera", (1, 0, 0, 1, 0, 0))
        pts.append(undo(cam, b["tipX"], b["tipY"]))
        gaps.append(eng["iks"][iid]["gap"] / math.sqrt(abs(cam[0] * cam[3] - cam[1] * cam[2])))
        pinned.append(pin_at(ik, s["t"]) >= PIN_ON)
    step = max(1, len(pts) // 24)
    at = max(range(len(gaps)), key=gaps.__getitem__)
    spans, i = [], 0
    while i < len(pts):
        if not pinned[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(pts) and pinned[j + 1]:
            j += 1
        moved = max(_dist(pts[i], p) for p in pts[i:j + 1])
        spans.append({"start": round(samples[i]["t"], 4), "end": round(samples[j]["t"], 4), "tip_moved_px": round(moved, 2), "sliding": moved > SLIDE_PX})
        i = j + 1
    return {"rig": rid, "ik": iid, "bone": bone, "tip_path": [[round(samples[n]["t"], 4), round(pts[n][0], 1), round(pts[n][1], 1)] for n in range(0, len(pts), step)],
            "tip_travelled_px": round(sum(_dist(a, b) for a, b in zip(pts, pts[1:])), 1),
            "largest_gap_px": round(gaps[at], 2), "largest_gap_at": round(samples[at]["t"], 4), "pinned_spans": spans}
