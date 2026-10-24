"""A text's type settings the font can't do (a feature or axis it lacks, a bad tag), refused when the document would take
them: part of the whole-document check (kind.check), so run_script, edit_document and the screen all refuse it up
front, naming the layer by its id, not when the first picture is drawn. A font that is neither in the app nor on this
computer is refused where it is set (fontlist.setting_refusal), and is a Missing font problem in an opened file.

The refusal is the engine's own (render/src/scene/type_font.rs), asked once per distinct set of settings and kept; a
text that asks nothing of its font is never measured. A font the engine can't find is diagnose's business, and no engine
built is no refusal (the look tools fail loudly then).
"""
from __future__ import annotations

from . import fields as F, textsize
from .engine import EngineError

ASKS = ("figures", "smallCaps", "features", "slant", "grade", "axes")     # the fields that ask the font a question
_REFUSED = "2D engine refused measure: "
_kept: dict[tuple, str] = {}


def _asks(p: dict) -> bool:
    return any(p[f] not in (0, 0.0, "", False, "default") for f in ASKS)


def _refusal(p: dict) -> str:
    """The engine's refusal of these settings as "<field>: …" (no layer id yet); "" when the font takes them."""
    k = tuple(p[f] for f in (*ASKS, "font", "size"))
    if k not in _kept:
        try:
            textsize._engine().measure([{**{f: p[f] for f in textsize.FIELDS}, "id": "t", "body": "A"}])
            _kept[k] = ""
        except EngineError as e:
            text = str(e)
            refused = text.startswith(_REFUSED) and "not found" not in text
            _kept[k] = text[len(_REFUSED):].split(".", 1)[-1] if refused else ""
        if len(_kept) > textsize.KEEP:
            _kept.clear()
    return _kept[k]


def problems_of_doc(data: dict) -> list[str]:
    """One line per text whose settings its font refuses: "fc_time.figures: the font "Roboto Flex" has no tnum feature; …"."""
    out, stack = [], [data]
    defaults = F.defaults("text")
    while stack:
        item = stack.pop()
        for key in ("comps", "layers"):
            stack += item.get(key, [])
        if item.get("type") == "text":
            p = {**defaults, **{f: item[f] for f in textsize.FIELDS if f in item}}
            if _asks(p) and (why := _refusal(p)):
                out.append(f'{item["id"]}.{why}')
    return out
