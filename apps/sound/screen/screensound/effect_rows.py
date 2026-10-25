"""An effect's own rows in its own terms (no Qt). Effects share field names (several have a `mix`, a `width`, a
`freq`), and the document holds one Param per name, so a shared row came with the first type's default and the widest
range and unit: Stereo width read "1" (De-hum's 1–200 width made it no amount), a Delay's Mix reset to the Reverb's
25 %. Here each row takes its effect type's own default, range, unit and kind (rostrum_sound.doc.effects.EFFECTS, the
one table), and the words a person reads. Called from inspect.py, like eq_rows.py."""
from __future__ import annotations

from rostrum_sound.doc import effects

LABELS = {"pingPong": "Ping-pong", "monoBelow": "Mono below", "freq": "Frequency", "makeup": "Make-up gain"}
OWN_LABELS = {("dehum", "freq"): "Hum at", ("dehum", "width"): "Notch width", ("width", "width"): "Width"}
OWN_WORDS = {("dehum", "freq"): [{"value": 0, "label": "Found in the clip"}]}     # 0 = the hum is found in the clip
OWN_UNITS = {("dehum", "width"): "Hz"}                                              # the notch's width (engine dehum.rs)


def own_rows(item: dict, rows: list[dict]) -> list[dict]:
    if item.get("type") != "effect" or item.get("effect") not in effects.EFFECTS:
        return rows
    kind, table, out = item["effect"], effects.EFFECTS[item["effect"]], []
    for r in rows:
        spec = table.get(r["id"]) if r.get("row") == "param" else None
        if spec is None or spec.lo is None or isinstance(spec.default, str):
            out.append({**r, "label": LABELS.get(r["id"], r["label"])} if r.get("row") == "param" else r)
            continue
        unit = OWN_UNITS.get((kind, r["id"]), spec.unit)
        amount = not unit and spec.lo == 0 and spec.hi <= 2                  # a unit-less amount reads in percent
        out.append({**r, "min": spec.lo, "max": spec.hi, "unit": unit, "display": "percent" if amount else "",
                    "default": spec.default, "words": OWN_WORDS.get((kind, r["id"]), r.get("words") or []),
                    "label": OWN_LABELS.get((kind, r["id"]), LABELS.get(r["id"], r["label"]))})
    return out
