"""The curve of one number field, as a curve editor or an agent draws it: its keys, the Bézier handles of each stretch
and samples from the one evaluation (track_value). Every app's curve view reads this (rostrum_gui/curve_view.py); 2D's
look_motion (what: curve) too. Moved here from 2D's ops_keys so 3D draws the same curves."""
from __future__ import annotations

from . import marked
from .easing import BEZIERS
from .evaluate import keys_of, track_value

HANDLES = ("x1", "y1", "x2", "y2")
CUSTOM_START = (0.25, 0.1, 0.25, 1.0)          # a `custom` key with no numbers yet reads as smooth


def handles_of(key: dict) -> dict | None:
    """The four Bézier numbers {x1, y1, x2, y2} of the stretch from this key, or None where the ease has none
    (linear, hold, spring, bounce). A named cubic gives its own numbers: they are where a `custom` ease starts."""
    ease = key.get("ease", "smooth")
    if ease in BEZIERS:
        return dict(zip(HANDLES, BEZIERS[ease]))
    if ease == "custom":
        return {n: key.get(n, d) for n, d in zip(HANDLES, CUSTOM_START)}
    return None


def curve_of(owner: dict, prop: str, per_stretch: int = 24, markers: dict | None = None, origin: float = 0.0) -> dict:
    """{"keys": [{id, t, v, ease, handles, marker?}], "samples": [[t, v] …]} of a number field in the owner's own
    seconds, the samples from the one evaluation (track_value). A key on a shared marker is placed through `markers`
    (`origin`: where the owner's time 0 sits, retime.offset_of) and carries `marker`, its words ("drop +0.2 s").
    Colour fields have no value curve: they raise ValueError."""
    keys = [dict(k) for k in keys_of(owner, prop)]
    marked.resolve({"keys": keys}, markers, origin)
    keys.sort(key=lambda k: k["t"])
    if keys and "c" in keys[0]:
        raise ValueError(f"{owner['id']}.{prop} is a colour field: it has no value curve")
    samples: list[list[float]] = []
    for k0, k1 in zip(keys, keys[1:]):
        steps = 1 if k0.get("ease") == "hold" else per_stretch
        for i in range(steps):                       # a hold stays flat, then jumps at the next key
            t = k0["t"] + (k1["t"] - k0["t"]) * i / steps
            samples.append([t, track_value(keys, t)])
        if k0.get("ease") == "hold":
            samples.append([k1["t"], k0["v"]])
    if keys:
        samples.append([keys[-1]["t"], keys[-1]["v"]])
    return {"keys": [{"id": k["id"], "t": k["t"], "v": k["v"], "ease": k.get("ease", "smooth"),
                      "handles": handles_of(k) if i < len(keys) - 1 else None,
                      **({"marker": marked.label(k["ref"])} if "ref" in k else {})} for i, k in enumerate(keys)],
            "samples": samples}
