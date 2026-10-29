""""Did you mean …": the closest real names to a wrong one, for every app's scripts and edit tools.

Only names, never a guess applied: the script still fails, the field is still unknown; the agent reads the names and
decides. `closest` ranks the names; `script_hint` reads a Python error from a script run (a wrong name, a wrong field or
call on an object, a wrong keyword argument) and says it in one line:
`"eas" isn't an argument of key(); did you mean ease?`.
"""
from __future__ import annotations

import difflib
import inspect
import re

# Words other tools use for the same thing, tried before spelling: an agent writing `from` / `to` is told `start` / `end`.
SAME_AS = {"from": ("start", "t0"), "to": ("end", "t1"), "begin": ("start",), "stop": ("end",), "until": ("end",),
           "columns": ("cols",), "frames": ("count",), "n": ("count",), "time": ("t", "at"), "script": ("source", "path"),
           "code": ("source",), "file": ("path",), "dir": ("folder",), "project": ("folder",), "doc": ("item",)}


def closest(word, choices, n: int = 3) -> list[str]:
    """The real names nearest to `word`, best first: a same-meaning word, a different case, then spelling. A second or
    third name only when it is about as close as the first, so one clear match stays one name."""
    named = list(dict.fromkeys(str(c) for c in choices))
    word = str(word)
    same = [s for s in SAME_AS.get(word.lower(), ()) if s in named]
    if same:
        return same[:1]
    cased = [c for c in named if c.lower() == word.lower() and c != word]
    if cased:
        return cased[:1]
    scored = sorted(((difflib.SequenceMatcher(None, word.lower(), c.lower()).ratio(), c) for c in named if c != word),
                    key=lambda s: -s[0])
    scored = [s for s in scored if s[0] >= 0.6]
    if not scored:
        return []
    best = scored[0][0]
    return [c for r, c in scored[:n] if r >= best - 0.08]


def said(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def did_you_mean(word, choices) -> str | None:
    near = closest(word, choices)
    return f"Did you mean {said(near)}?" if near else None


def _public(obj) -> list[str]:
    try:
        return [n for n in dir(obj) if not n.startswith("_")]
    except Exception:
        return []


def _callee(qualname: str, frames) -> object | None:
    """The function a failed call meant, found among what the calling line could see (its locals and globals, and the
    methods of those values' types)."""
    for frame in reversed(frames):
        for v in [*frame.f_locals.values(), *frame.f_globals.values()]:
            if getattr(v, "__qualname__", None) == qualname and callable(v):
                return v
            meth = getattr(type(v), qualname.rpartition(".")[2], None) if "." in qualname else None
            if meth is not None and getattr(meth, "__qualname__", None) == qualname:
                return meth
    return None


def _arguments(fn) -> list[str]:
    try:
        ps = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return []
    return [p.name for p in ps if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY) and p.name != "self"]


def script_hint(e: BaseException, scope: dict | None = None, more=None) -> str | None:
    """One line naming the closest real names for a script's wrong name, field / call, or keyword argument; None when
    the error is not about a name. `scope`: the names the script could use. `more(obj)`: extra names an object answers
    to that dir() doesn't show (an item's fields)."""
    if isinstance(e, NameError) and getattr(e, "name", None):
        names = [k for k in (scope or {}) if not k.startswith("_")]
        builtins = (scope or {}).get("__builtins__")
        names += list(builtins) if isinstance(builtins, dict) else []
        near = closest(e.name, names)
        return f'"{e.name}" isn\'t a name the script knows; did you mean {said(near)}?' if near else None
    if isinstance(e, AttributeError) and getattr(e, "name", None) and getattr(e, "obj", None) is not None:
        obj = e.obj
        names = _public(obj) + (list(more(obj) or []) if more else [])
        near = closest(e.name, names)
        node = getattr(obj, "__dict__", {}).get("node")           # an app's item handle: say its kind ("a mesh")
        what = (f'a {node["type"]}' if isinstance(node, dict) and node.get("type")
                else obj.__name__ if isinstance(obj, type) else type(obj).__name__)
        return f'"{e.name}" isn\'t a field or call of {what}; did you mean {said(near)}?' if near else None
    if isinstance(e, TypeError) and (m := re.match(r"(\S+)\(\) got an unexpected keyword argument '(\w+)'", str(e))):
        qualname, word = m[1], m[2]
        frames, tb = [], e.__traceback__
        while tb:
            frames.append(tb.tb_frame)
            tb = tb.tb_next
        fn = _callee(qualname, frames) if qualname != "<lambda>" else None
        names = _arguments(fn) if fn is not None else []
        call = qualname.rpartition(".")[2] + "()"
        near = closest(word, names)
        if near:
            return f'"{word}" isn\'t an argument of {call}; did you mean {said(near)}?'
        return f'"{word}" isn\'t an argument of {call}; it takes {", ".join(names)}' if names else None
    return None
