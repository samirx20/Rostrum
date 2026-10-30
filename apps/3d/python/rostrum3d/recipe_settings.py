"""A script's named settings (PR8 recipes, recipe.py): `setting("count", 12, min=1, max=200, label="Copies")` at the
top of a script declares a value a person can change; the call gives the setting's current value.

    count = setting("count", 12, min=1, max=200, label="Copies")     # a number (whole: the default is a whole number)
    tint = setting("tint", "#cc3322", label="Colour")                 # a colour: "#rrggbb"
    style = setting("style", "round", choices=["round", "square"])    # a choice
    lid = setting("lid", True)                                        # on / off
    title = setting("title", "Hello")                                 # text

Its kind comes from the default. The value used, in order: one recipe.set asked for this run; the recipe's value in the
scene (a person's change stays); the default. A default the script changes since its last run is the script saying
something new: it is used, whatever the recipe held.
"""
from __future__ import annotations

import re

COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]{0,39}$")


def kind_of(default, choices) -> str:
    if choices is not None:
        return "choice"
    if isinstance(default, bool):
        return "toggle"
    if isinstance(default, (int, float)):
        return "number"
    if isinstance(default, str):
        return "colour" if COLOUR.match(default) else "text"
    raise ValueError(f"a setting's default is a number, True / False, a colour \"#rrggbb\" or text, not {default!r}")


def accepted(d: dict) -> str:
    """What a setting takes, in words (every refusal says it)."""
    k = d["kind"]
    if k == "number":
        what = "a whole number" if d.get("whole") else "a number"
        lo, hi = d.get("min"), d.get("max")
        return what + (f" from {lo} to {hi}" if lo is not None and hi is not None else f" from {lo} up" if lo is not None
                       else f" up to {hi}" if hi is not None else "")
    return {"toggle": "true or false", "colour": 'a colour "#rrggbb"', "text": "text",
            "choice": "one of " + ", ".join(map(str, d.get("choices", [])))}[k]


def problem(d: dict, value) -> str | None:
    """Why `value` is not one this setting takes (None: it is)."""
    k = d["kind"]
    if k == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or (d.get("whole") and value != int(value)):
            return f"is {value!r}"
        if (d.get("min") is not None and value < d["min"]) or (d.get("max") is not None and value > d["max"]):
            return f"is {value}, out of range"
        return None
    ok = {"toggle": isinstance(value, bool), "colour": isinstance(value, str) and bool(COLOUR.match(value)),
          "text": isinstance(value, str), "choice": value in d.get("choices", [])}[k]
    return None if ok else f"is {value!r}"


def checked(d: dict, value):
    """`value` as the setting keeps it (a whole number as an int), or ValueError naming the setting and what it takes."""
    why = problem(d, value)
    if why:
        raise ValueError(f'setting "{d["name"]}" {why}; it takes {accepted(d)}')
    return int(value) if d["kind"] == "number" and d.get("whole") else value


def declare(name, default, min=None, max=None, label=None, choices=None) -> dict:
    """A setting's declaration, as the recipe stores it; a bad declaration fails loudly."""
    if not isinstance(name, str) or not NAME.match(name):
        raise ValueError(f"setting({name!r}): a setting's name is a short word (letters, digits, _ and spaces)")
    kind = kind_of(default, choices)
    d = {"name": name, "kind": kind, "default": default, "label": str(label or name)}
    if kind == "number":
        d["whole"] = isinstance(default, int) and not isinstance(min, float) and not isinstance(max, float)
        for k, v in (("min", min), ("max", max)):
            if v is not None:
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    raise ValueError(f'setting "{name}": {k}= is a number, not {v!r}')
                d[k] = v
    elif min is not None or max is not None:
        raise ValueError(f'setting "{name}": min= and max= are for a number setting')
    if kind == "choice":
        choices = list(choices)
        if not choices or default not in choices:
            raise ValueError(f'setting "{name}": its default {default!r} is one of its choices ({", ".join(map(str, choices))})')
        d["choices"] = choices
    checked(d, default)                     # a default out of its own range: said now
    return d


def value(d: dict, asked: dict, stored: dict | None):
    """The value a run uses (see the module's note). `stored`: the recipe's last {declaration, value} for this name."""
    if d["name"] in asked:
        return checked(d, asked[d["name"]])
    if stored is not None and stored["decl"].get("default") == d["default"] and stored["decl"].get("kind") == d["kind"] \
            and problem(d, stored["value"]) is None:
        return stored["value"]
    return d["default"]
