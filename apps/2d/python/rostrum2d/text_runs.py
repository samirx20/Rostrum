"""Styled runs inside one text layer (engine: scene/runs.rs): up to COUNT stretches of its body, each with its own
colour, weight, scale and opacity, all keyable. The words stay one layer and flow as one line (or one wrapped box);
nothing is placed by hand.

    t = text("line", body=["Make it ", ("move", {"color": "#ff5a36", "weight": 800}), " on cue"])
    t.run("move").key("color", {"#reveal": "#ffffff", "#reveal+0.3": "#ff5a36"})     # or t.run(1)

In the document a run is plain fields on the text: `run<n>From` ≤ letter < `run<n>To` (letters counted in `body`,
line breaks included; the run is used while To > From), `run<n>Color`, `run<n>Weight` (0 = the text's), `run<n>Scale`
(about the run's own centre, the line keeps its room), `run<n>Opacity`. A run with no colour given takes the text's.
"""
from __future__ import annotations

from rostrum_core import Param

COUNT = 4
STYLE = {"color": "Color", "weight": "Weight", "scale": "Scale", "opacity": "Opacity"}


def _fields(n: int) -> list:
    used = {"not": {"is": [f"run{n}To", 0]}}
    first = None if n == 1 else {"not": {"is": [f"run{n - 1}To", 0]}}      # the next run's range shows once one is used
    g, imp = f"Styled words {n}", "deep"
    return [
        Param.number(f"run{n}From", label="From letter", group=g, min=0, max=100000, step=1, integer=True, importance=imp,
                     default=0.0, valid_when=first, help="The first letter of the run, counted from 0 in the text (line breaks count)"),
        Param.number(f"run{n}To", label="To letter", group=g, min=0, max=100000, step=1, integer=True, importance=imp,
                     default=0.0, valid_when=first, help="Just past the run's last letter; equal to From = no run"),
        Param.color(f"run{n}Color", label="Colour", group=g, importance=imp, valid_when=used, default="#ffffff"),
        Param.number(f"run{n}Weight", label="Weight", group=g, min=0, max=1000, step=1, importance=imp, valid_when=used, default=0.0,
                     words={0: "The text's"}, help="0 = the text's own weight"),
        Param.number(f"run{n}Scale", label="Scale", group=g, min=0, max=20, step=0.01, unit="×", importance=imp,
                     valid_when=used, default=1.0, display="percent", help="About the run's own centre; the line keeps its room"),
        Param.number(f"run{n}Opacity", label="Opacity", group=g, min=0, max=1, step=0.01, importance=imp, valid_when=used,
                     default=1.0, display="percent"),
    ]


FIELDS = [p for n in range(1, COUNT + 1) for p in _fields(n)]
MEASURED = tuple(f"run{n}{f}" for n in range(1, COUNT + 1) for f in ("From", "To", "Weight", "Scale"))   # what changes the box
STILL = {f"run{n}{end}" for n in range(1, COUNT + 1) for end in ("From", "To")}


def split(node: dict, values: dict) -> dict:
    """`body` given as a list of plain strings and (words, {style}) pairs → the body string and the run fields."""
    body = values.get("body")
    if not isinstance(body, (list, tuple)):
        return values
    out, text, n = {k: v for k, v in values.items() if k != "body"}, "", 0
    colour = values.get("color", node.get("color"))
    for i, part in enumerate(body):
        if isinstance(part, str):
            text += part
            continue
        if not (isinstance(part, (list, tuple)) and len(part) == 2 and isinstance(part[0], str) and isinstance(part[1], dict)):
            raise ValueError(f'{node["id"]}.body[{i}]: each part is a string or ("words", {{"color": …, "weight": …}}); got {part!r}')
        n += 1
        if n > COUNT:
            raise ValueError(f'{node["id"]}.body: at most {COUNT} styled runs in one text; split the line into two texts in a row')
        bad = sorted(set(part[1]) - set(STYLE))
        if bad:
            raise ValueError(f'{node["id"]}.body[{i}]: a run takes {", ".join(STYLE)}; not {", ".join(bad)}')
        out[f"run{n}From"], out[f"run{n}To"] = len(text), len(text) + len(part[0])
        out[f"run{n}Color"] = part[1].get("color", colour)
        for k in ("weight", "scale", "opacity"):
            out[f"run{n}{STYLE[k]}"] = part[1].get(k, {"weight": 0, "scale": 1.0, "opacity": 1.0}[k])
        text += part[0]
    for m in range(n + 1, COUNT + 1):           # a re-run with fewer runs leaves none behind
        if node.get(f"run{m}To"):
            out[f"run{m}From"], out[f"run{m}To"] = 0, 0
    out["body"] = text
    return out


def number(node: dict, which) -> int:
    """A run by its number (1 …) or its words."""
    if isinstance(which, int) and 1 <= which <= COUNT and node.get(f"run{which}To", 0) > node.get(f"run{which}From", 0):
        return which
    body = node.get("body", "")
    for n in range(1, COUNT + 1):
        a, b = int(node.get(f"run{n}From", 0)), int(node.get(f"run{n}To", 0))
        if b > a and body[a:b] == which:
            return n
    have = [body[int(node[f"run{n}From"]):int(node[f"run{n}To"])] for n in range(1, COUNT + 1) if node.get(f"run{n}To", 0) > node.get(f"run{n}From", 0)]
    raise ValueError(f'{node["id"]}.run({which!r}): no such run; its runs: {", ".join(repr(h) for h in have) or "none"} '
                     '(make one with body=["… ", ("words", {"color": …}), " …"])')


class Run:
    """One run of a text, keyed and set by its own names: `run.key("color", {...})`, `run.set(weight=800)`."""

    def __init__(self, item, n: int):
        self.item, self.n = item, n

    def _f(self, prop: str) -> str:
        if prop not in STYLE:
            raise ValueError(f'{self.item.id}.run({self.n}): a run has {", ".join(STYLE)}; not "{prop}"')
        return f"run{self.n}{STYLE[prop]}"

    def key(self, prop: str, keys: dict, ease: str = "smooth") -> "Run":
        self.item.key(self._f(prop), keys, ease)
        return self

    def set(self, **values) -> "Run":
        self.item.set(**{self._f(k): v for k, v in values.items()})
        return self
