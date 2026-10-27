"""measure_text(body, **fields) in a script: the box (w, h) a text with those fields would have, in its own px, measured by the
engine code that draws it. It makes no layer, so nothing is left in the picture (a probe text made only to measure would stay
on screen). The text's own `t.measure()` is for a text the script already made."""
from __future__ import annotations

from . import fields as F
from .evaluate import resolve
from .textsize import size


def for_script() -> dict:
    def measure_text(body: str = "", **values) -> tuple[float, float]:
        names = [p.name for p in F.FIELDS["text"]]
        for name in values:
            if name not in names:
                raise ValueError(f'measure_text: a text has no field "{name}". Its fields: {", ".join(names)}')
        node = {"id": "measure_text", "type": "text", "keys": [], **F.defaults("text"),
                **{k: F.param("text", k).check(v, f"measure_text {k}") for k, v in {"body": body, **values}.items()}}
        return size(resolve(node, 0))
    return {"measure_text": measure_text}
