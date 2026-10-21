"""The `lipsync(...)` script call (LIPSYNC.md § In a script):

    with rig("puppet", w=1920, h=1080):
        rest = path("mouth_X", d=...); mbp = path("mouth_A", d=...); wide = path("mouth_D", d=...)
        ...
        said = lipsync("take.wav", at=0.5, text="Every city keeps one hour.",
                       shapes={"X": rest, "A": mbp, "D": wide}, start=0, end=None, rest_gap=0.25)

It keys the mouth layers made earlier in the same script (opacity, hold), so a re-run merges key by key and a
person's edit to any mouth key stays. The phones are computed once and cached; a re-run reads the cache. It returns
the job's answer: phones, words and cues in comp seconds.
"""
from __future__ import annotations

from .keys import check_shapes
from .track import track


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
                **timing):
        from ..script import Item
        if not build.holders:
            raise ValueError("make a composition first: comp(...) before lipsync(...)")
        shapes = check_shapes(shapes, "lipsync")
        fps = build.holders[0].get("fps", 30)
        job = track(source, at, fps, shapes, text, start, end, language, pronounce, **timing)
        for layer, ks in job["keys"].items():
            Item(build, _node(build, layer)).key("opacity", {t: (v, "hold") for t, v in ks.items()})
        return job

    return {"lipsync": lipsync}
