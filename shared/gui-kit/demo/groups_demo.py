"""A 3D-style light and mesh for the open-if-changed groups option (sections.OWN): the kit's look harness and test use
it. Not an app: Rostrum3D fills `sections.OWN` and its own params the same way."""
from __future__ import annotations

from rostrum_core import toy
from rostrum_core.document import Document
from rostrum_core.kind import DocKind
from rostrum_core.params import Param
from rostrum_core.registry import Registry

from rostrum_gui import DocBridge, sections


def N(name, label, group, lo, hi, step, unit="", default=0.0):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance="secondary", default=default)


LIGHT = [Param.choice("lightType", ["Point", "Spot", "Area", "Sun"], label="Type", group="Light", importance="secondary", default="Area"),
         Param.color("colour", label="Colour", group="Light", importance="secondary", default="#fff1dc"),
         N("power", "Brightness", "Light", 0, 5000, 1, "W", 800),
         *(N(a, a.upper(), "Position", -50, 50, 0.01, "m") for a in "xyz"),
         N("spread", "Spread", "Spread", 0, 180, 1, "°", 40),
         N("card", "Card", "Card", 0, 1, 0.01, "", 0),
         Param.list("only", "choice", options=["Hero", "Props"], label="Lights only", group="Lights only", importance="secondary", default=[]),
         Param.toggle("shadow", label="Cast shadows", group="Shadow", importance="secondary", default=True)]
REGISTRY = Registry()


@REGISTRY.operation("light.set", "Change a light's settings.", target="light", params=LIGHT, fields=True, label="Edit light")
def _set(ctx, targets, args):
    toy._set_fields(ctx, targets, args)


KIND = DocKind("groupsdemo", ".groupsdemo", REGISTRY, lists={"doc": ["layers"]},
               new=lambda: {"id": "root", "type": "doc", "layers": []})
sections.OWN["light"] = "Light"


class Bridge(DocBridge):
    sections = True


def sample() -> Document:
    """A light placed at x = 1.2 m: Position is changed, so it opens; the rest are names."""
    data = KIND.blank()
    data["layers"] = [{"id": "key", "type": "light", "name": "Key", **{p.name: p.default for p in LIGHT}, "x": 1.2, "y": 2.0}]
    return Document(KIND, data)
