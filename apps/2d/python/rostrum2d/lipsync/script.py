"""The `lipsync(...)` script call (LIPSYNC.md § In a script):

    with rig("puppet", w=1920, h=1080):
        rest = path("mouth_X", d=...); mbp = path("mouth_A", d=...); wide = path("mouth_D", d=...)
        ...
        said = lipsync("take.wav", at=0.5, text="Every city keeps one hour.",
                       shapes={"X": rest, "A": mbp, "D": wide}, start=0, end=None, rest_gap=0.25)

`source` is a WAV, or "voice:<line id>": a RostrumSound voice line of the project (its made take, and its words when
`text` is left out; voice_line.py). It keys the mouth layers made earlier in the same script (opacity, hold), so a re-run merges key by key and a
person's edit to any mouth key stays. With `slot=<swap group>` (the mouths are its children) it keys the slot's
`show` instead: one choice per change of mouth. The phones are computed once and cached; a re-run reads the cache. It returns
the job's answer: phones, words and cues in comp seconds.
"""
from __future__ import annotations

from rostrum_core.lipsync.keys import check_shapes, slot_keys
from rostrum_core.lipsync.track import track

from . import voice_line


def _folder():
    """The project folder of the program running the script (placement's host), or None."""
    from .. import placement
    return placement._host.folder() if placement._host else None


def _node(build, id_):
    stack = [build.root]
    while stack:
        n = stack.pop()
        if n.get("id") == id_:
            return n
        stack += [c for v in n.values() if isinstance(v, list) for c in v if isinstance(c, dict)]
    raise ValueError(f'lipsync: no layer "{id_}" was made earlier in this script')


def for_script(build) -> dict:
    def lipsync(source, at=0.0, shapes=None, text=None, start=0.0, end=None, language="english", pronounce=None,
                slot=None, **timing):
        from ..script import Item
        if not build.holders:
            raise ValueError("make a composition first: comp(...) before lipsync(...)")
        shapes = check_shapes(shapes, "lipsync")
        fps = build.holders[0].get("fps", 30)
        source, words = voice_line.resolve(source, _folder())          # "voice:<line id>": a Sound voice line's take
        job = track(source, at, fps, shapes, text if text is not None else words, start, end, language, pronounce, **timing)
        if slot is not None:            # a swap set: key its `show` instead of each layer's opacity
            node = _node(build, getattr(slot, "id", slot))
            kids = [c["id"] for c in node["layers"]]
            if not node.get("swap") or not set(shapes.values()) <= set(kids):
                raise ValueError(f'lipsync: slot "{node["id"]}" must be a group with swap=True holding the mouth '
                                 f"layers; its children are: {', '.join(kids) or 'none'}")
            Item(build, node).key("show", {t: (i, "hold") for t, i in slot_keys(job["shown"], kids).items()})
            return job
        for layer, ks in job["keys"].items():
            Item(build, _node(build, layer)).key("opacity", {t: (v, "hold") for t, v in ks.items()})
        return job

    return {"lipsync": lipsync}
