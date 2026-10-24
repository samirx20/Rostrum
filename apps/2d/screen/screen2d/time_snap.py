"""2D's targets for snapping in time (the rule itself is the kit's: rostrum_gui/time_snap.py), the ONE source (UX_SPEC 6.2, INTERACTION 1.11): a key drag, a key stretch and a bar drag all ask
here for its targets: shared markers, the playhead, other layers' bar ends and keys (of every layer shown), the
music's bar starts, then its beats, when the project has a tempo. `snap`, `label` and `TimeSnap` (backend.timeSnap)
are the kit's, imported here for 2D's importers.
"""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum2d.retime import END_OF_COMP

from rostrum_gui.time_snap import RANK, Target, TimeSnap, label, snap  # noqa: F401  (the kit's one rule; 2D's importers)

from . import beat_words


def _layer_keys(item: dict):
    yield from item.get("keys", [])
    for part in ("effects", "masks"):
        for child in item.get(part, []):
            yield from child.get("keys", [])


def targets(bridge, skip_keys=(), skip_layers=(), carried=()) -> list[Target]:
    """Everything a time drag may catch now, minus what the drag itself moves (it never snaps to itself): `skip_keys`,
    the bar ends of `skip_layers` (a trim), and all of `carried` with what it holds (a bar moved in time)."""
    out = [Target("marker", name, at) for name, at in bridge.times().items()]
    out.append(Target("playhead", "playhead", bridge.time))
    skip_keys, skip_layers, carried = set(skip_keys), set(skip_layers), set(carried)

    def walk(layers):
        for lay in layers:
            if lay.get("hidden") or lay.get("type") not in F.LAYERS or lay["id"] in carried:
                continue
            name = bridge.label_of(lay)
            if lay["id"] not in skip_layers:
                out.append(Target("edge", f"{name} start", lay.get("start", 0.0)))
                if lay.get("end", END_OF_COMP) < END_OF_COMP:
                    out.append(Target("edge", f"{name} end", lay["end"]))
            out.extend(Target("key", f"key · {name}", k["t"]) for k in _layer_keys(lay)
                       if k["id"] not in skip_keys and isinstance(k["t"], (int, float)))
            walk(lay.get("layers", []))
    walk(bridge.placed().get("layers", []))
    sound = getattr(bridge, "soundtrack", None)          # the project's music (member "sound": soundtrack*.py)
    bars = sound.bar_times() if sound is not None else []
    beats = sound.beat_times() if sound is not None else []
    fps = bridge.comp()["fps"]                           # their names are the one beat wording (beat_words.py)
    out.extend(Target("measure", beat_words.words(t, beats, bars, fps) or f"bar {n + 1}", t) for n, t in enumerate(bars))
    out.extend(Target("beat", beat_words.words(t, beats, bars, fps) or f"beat {n + 1}", t) for n, t in enumerate(beats)
               if not any(abs(t - b) < 1e-6 for b in bars))
    return out


