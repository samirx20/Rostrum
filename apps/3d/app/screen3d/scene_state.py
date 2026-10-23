"""What the settings panel shows while nothing is selected (the Scene, SPEC §3.4): the shot's own values as plain lines,
and the scene's sky (its dome light) if it has one. Read-only; the shot's settings are where it is edited. No Qt."""
from __future__ import annotations

from .outline import label_of


def _walk(items):
    for it in items:
        yield it
        yield from _walk(it.get("children", []))


def find_item(data: dict, item_id: str) -> dict | None:
    return next((i for i in _walk(data.get("items", [])) if i["id"] == item_id), None)


def sky(data: dict) -> dict:
    """{id, label} of the first dome light, {} when the scene has none."""
    dome = next((i for i in _walk(data.get("items", [])) if i.get("type") == "light" and i.get("kind") == "dome"), None)
    return {"id": dome["id"], "label": label_of(dome)} if dome else {}


def _number(x: float) -> str:
    return f"{x:g}"


def shot_lines(data: dict, info: dict) -> dict:
    """{id, label, rows: [{label, value}]} for the shot `info` (bridge.shotInfo: id, label, camera, fps, start, end, width, height)."""
    if "fps" not in info:
        return {"id": info.get("id", ""), "label": info.get("label", ""), "rows": []}
    cam = find_item(data, info.get("camera", ""))
    seconds = (info["end"] - info["start"] + 1) / info["fps"]
    rows = [{"label": "Size", "value": f"{info['width']} × {info['height']}"},
            {"label": "Frame rate", "value": f"{_number(info['fps'])} fps"},
            {"label": "Length", "value": f"{seconds:.2f} s"}]
    if cam:
        rows.append({"label": "Camera", "value": label_of(cam)})
    return {"id": info["id"], "label": info["label"], "rows": rows}


def scene_state(data: dict, info: dict) -> dict:
    return {"shot": shot_lines(data, info), "sky": sky(data)}
