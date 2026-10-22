"""The engine's half of diagnose.py, and the whole list: fonts the engine can't find (each one, not only the first)
and anything else it refuses when the scene loads (a refused mask, font feature or axis, a bad curve or .cube file).
The engine checks a scene whole and stops at the first refusal, so each font is asked alone (`measure`, which needs no
scene) and the scene once. A refusal the document's own checks already name is not listed twice.
"""
from __future__ import annotations

from . import diagnose, fields as F, textsize
from .diagnose import _p
from rostrum_core import RostrumError

from .engine import Engine, EngineError
from .exprbake import items_of
from .scene import describe

SAID_BEFORE = ("broken-link", "missing-marker", "expression", "missing-file", "missing-render")    # kinds the engine may refuse for too


def everything(doc_data: dict, comp_id: str, folder=None, markers: dict | None = None, engine: Engine | None = None) -> list[dict]:
    """Every problem of one composition: the engine's first (it can't draw the scene), then the document's."""
    comp = next(c for c in doc_data["comps"] if c["id"] == comp_id)
    found = problems(doc_data, comp_id, markers, engine, folder)
    own = diagnose.problems(comp, folder, markers)
    if any(p["kind"] == "missing-font" for p in found):     # "can't measure every text" is that font again
        own = [p for p in own if p["kind"] != "refused"]
    said = {p["item"] for p in own if p["kind"] in SAID_BEFORE}
    return [p for p in found if not (p["kind"] == "refused" and p["item"] in said)] + own


def problems(doc_data: dict, comp_id: str, markers: dict | None = None, engine: Engine | None = None, folder=None) -> list[dict]:
    comp = next(c for c in doc_data["comps"] if c["id"] == comp_id)
    own = engine is None
    engine = engine or Engine()
    try:
        out = _fonts(comp, engine)
        try:
            engine.load(describe(doc_data, comp_id, markers, folder, (0.0, comp.get("duration", 5.0))))    # a 3D layer not rendered yet is reported by `_renders`, not refused here
        except (EngineError, ValueError, RostrumError) as e:
            msg = str(e)
            if not (out and "not found" in msg and "font" in msg):     # that font is listed already
                item = msg.split(".", 1)[0].split(":")[-1].strip()
                out.append(_p("refused", item if item in items_of(comp) else "", f"The engine refuses the scene: {msg}",
                              "Fix what it names; the picture can't be drawn until then"))
        return out
    finally:
        if own:
            engine.close()


def _fonts(comp: dict, engine: Engine) -> list[dict]:
    users: dict[str, list[str]] = {}
    for item in items_of(comp).values():
        if item["type"] == "text":
            users.setdefault(item.get("font", F.defaults("text")["font"]), []).append(item["id"])
    plain = {f: F.defaults("text")[f] for f in textsize.FIELDS if f in F.defaults("text")}
    out = []
    for n, (family, ids) in enumerate(sorted(users.items())):
        try:
            engine.measure([{**plain, "id": f"font{n}", "body": "A", "font": family}])
        except EngineError as e:
            have = str(e).split("there is:", 1)[-1].strip() if "there is:" in str(e) else str(e)
            out.append(_p("missing-font", ids[0], f'{", ".join(ids)}: the font "{family}" is not in the app (it has: {have})',
                          "Pick a font the app has, or add the font file to the project"))
    return out
