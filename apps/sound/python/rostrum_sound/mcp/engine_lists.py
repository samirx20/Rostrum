"""What inspect_engine tells an agent beyond the engine's own lists: every effect's settings and the master's, with units
and ranges, read from the document's one table (doc/effects.py, doc/fields.py) so the guide, the tools and the checks
never disagree; and which sounds are recorded and which are synthesized, read from the engine's own instrument data.
"""
from __future__ import annotations

from .. import names, roles
from ..doc import effects as FX
from ..doc import fields as FD


def _num(n):
    return int(n) if float(n).is_integer() else n


def _field(name: str, spec: FX.F) -> dict:
    if spec.default == FX.BANDS:
        return {"name": name, "about": f"a list of bands {{shape, freq (Hz), gain (dB), q}}; shape is one of {', '.join(names.EQ_SHAPES)}"}
    if spec.default == FX.SPACE:
        return {"name": name, "options": names.SPACES, "default": "hall"}
    if spec.default == FX.TOGGLE:
        return {"name": name, "about": "true or false", "default": False}
    row = {"name": name, "default": spec.default, "min": _num(spec.lo), "max": _num(spec.hi), "unit": spec.unit,
           "curve": spec.env}
    if name in FX.FREEVERB_ONLY:
        row["only_with"] = "a freeverb.* space"
    return row


def effect_rows() -> dict[str, list[dict]]:
    """{effect type: its settings}: name, default, min, max, unit; `curve` true = also takes a list of [time, value] points."""
    return {t: [_field(n, s) for n, s in fs.items()] for t, fs in FX.EFFECTS.items() if t != "plugin"}


def master_rows() -> list[dict]:
    """The master's settings (`master(...)` in a script, `master.set`): name, unit, range, default, what it does."""
    out = []
    for p in FD.FIELDS["master"]:
        row = {"name": p.name, "type": p.type, "default": FD.DEFAULTS["master"].get(p.name), "help": p.help}
        if p.type == "number":
            row |= {"min": _num(p.min), "max": _num(p.max), "unit": p.unit}
        if p.type == "choice":
            row["options"] = p.options
        out.append(row)
    return out


def _range(r: dict) -> str:
    unit = f" {r['unit']}" if r.get("unit") else ""
    curve = "~" if r.get("curve") else ""
    return (f"{r['default']}{unit} ({r['min']} to {r['max']}){curve}" if r.get("default") is not None
            else f"({r['min']} to {r['max']}{unit}){curve}")


def _options(r: dict) -> str:
    return f"{r['name']} one of the reverb spaces" if r["options"] == names.SPACES else f"{r['name']} one of {', '.join(r['options'])}"


def effect_line(t: str, rows: list[dict]) -> str:
    """'compressor: threshold -18 dB (-80 to 0), ratio 3 :1 (1 to 30), …' (the default first, then the range)."""
    parts = []
    for r in rows:
        if "min" in r:
            parts.append(f"{r['name']} {_range(r)}")
        elif "options" in r:
            parts.append(_options(r))
        else:
            parts.append(f"{r['name']} ({r['about']})")
    return f"{t}: " + ", ".join(parts)


def master_line(rows: list[dict]) -> str:
    parts = []
    for r in rows:
        parts.append(f"{r['name']} {_range(r)}" if "min" in r else
                     _options(r) if "options" in r else f"{r['name']} (true or false)")
    return "master(...) / master.set: " + ", ".join(parts)


def made_by(described: dict) -> dict[str, str]:
    """{role key: "recorded" | "synthesized"} for every row of the role table, from the engine's `describe`: a plain name is
    recorded when the engine says it plays a recording; a modelled instrument, a synth wave and the classic kit are synthesized."""
    plays = {i["name"]: i["plays"] for i in described.get("instruments", [])}
    kits = {k["name"]: k for k in described.get("kits", [])}
    out = {}
    for key in roles.ROLES:
        form, name = key.split(":", 1)
        if form == "builtIn":
            made = "recorded" if plays.get(name) == "recorded" else "synthesized"
        elif form == "kit":
            made = "recorded" if kits.get(name, {}).get("packs") else "synthesized"
        else:
            made = "synthesized"
        out[key] = made
    return out
