"""The engine's half of diagnose.py, and the whole list: fonts the engine can't find (each one, not only the first; from
the engine's one font list, fontlist.py)
and anything else it refuses when the scene loads (a refused mask, font feature or axis, a bad curve or .cube file).
The engine checks a scene whole and stops at the first refusal, so the fonts are looked up in its list and the scene
asked once. A refusal the document's own checks already name is not listed twice.
"""
from __future__ import annotations

from . import diagnose, fields as F, fontlist
from .diagnose import _p
from rostrum_core import RostrumError

from .engine import Engine, EngineError
from .exprbake import items_of
from .scene import describe

SAID_BEFORE = ("broken-link", "missing-marker", "expression", "missing-file", "missing-render")    # kinds the engine may refuse for too


def everything(doc_data: dict, comp_id: str, folder=None, markers: dict | None = None, engine: Engine | None = None,
               keeper=None) -> list[dict]:
    """Every problem of one composition: the engine's first (it can't draw the scene), then the document's. `keeper`
    (scene_keep.Keeper): describes only what changed since its last call, so a held engine is sent only the change."""
    comp = next(c for c in doc_data["comps"] if c["id"] == comp_id)
    found = problems(doc_data, comp_id, markers, engine, folder, keeper)
    own = diagnose.problems(comp, folder, markers)
    if any(p["kind"] == "missing-font" for p in found):     # "can't measure every text" is that font again
        own = [p for p in own if p["kind"] != "refused"]
    said = {p["item"] for p in own if p["kind"] in SAID_BEFORE}
    return [p for p in found if not (p["kind"] == "refused" and p["item"] in said)] + own


def problems(doc_data: dict, comp_id: str, markers: dict | None = None, engine: Engine | None = None, folder=None,
             keeper=None) -> list[dict]:
    comp = next(c for c in doc_data["comps"] if c["id"] == comp_id)
    own = engine is None
    engine = engine or Engine()
    try:
        out = _fonts(comp)
        try:
            # A 3D layer not rendered yet is reported by `_renders`, not refused here. Only whether the engine accepts the
            # scene is asked, never its pixels: paint pictures not made yet stay stand-ins (`later`), so this check never
            # stamps strokes (seconds of work, a second time, taking the screen's thread's turn).
            engine.load((keeper.describe if keeper else describe)(doc_data, comp_id, markers, folder, (0.0, comp.get("duration", 5.0)), later=[]))
        except (EngineError, ValueError, RostrumError) as e:
            msg = str(e)
            if not (out and "font" in msg and ("not found" in msg or "italic" in msg)):     # that font is listed already
                item = msg.split(".", 1)[0].split(":")[-1].strip()
                out.append(_p("refused", item if item in items_of(comp) else "", f"The engine refuses the scene: {msg}",
                              "Fix what it names; the picture can't be drawn until then"))
        return out
    finally:
        if own:
            engine.close()


def _fonts(comp: dict) -> list[dict]:
    """A Missing font problem per family the texts use that the app and this computer don't have (fontlist.py, the
    engine's one list), naming every text that uses it; and an italic the family lacks."""
    users: dict[str, list[str]] = {}
    slanted: dict[str, list[str]] = {}
    for item in items_of(comp).values():
        if item["type"] == "text":
            family = item.get("font", F.defaults("text")["font"])
            users.setdefault(family, []).append(item["id"])
            if item.get("italic"):
                slanted.setdefault(family, []).append(item["id"])
    have = fontlist.names()
    out = []
    for family, ids in sorted(users.items()):
        if family not in have:
            said = fontlist.missing_words(family).split("; inspect_fonts")[0]       # (the agents' hint is not for the list)
            out.append({**_p("missing-font", ids[0], f'{", ".join(ids)}: {said}',
                             f'Pick another font, or install "{family}" on this computer. Until then each of them shows as a dashed red box '
                             "with the font's name, and an export is refused"),
                        "action": "Use another font", "family": family})      # the list's picker: font.replace on all of them
        elif ids_ := slanted.get(family):
            if not (fontlist.family(family) or {}).get("italic"):
                out.append(_p("missing-font", ids_[0], f'{", ".join(ids_)}: the font "{family}" has no italic',
                              "Turn Italic off, or pick a font that has one"))
    return out
