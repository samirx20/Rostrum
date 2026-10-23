"""What agents and old files rely on: a retired choice still opens but is never offered; a warning never blocks a
file opening and is never silent."""
import dataclasses

import pytest

from rostrum_core import Document, Param, RostrumError
from rostrum_core import toy


def test_a_kept_choice_opens_but_is_never_offered_or_newly_set():
    p = Param.choice("design", ["click", "riser"], kept=["whoosh"], labels={"whoosh": "Whoosh (no longer made)"})
    assert [c["value"] for c in p.choices()] == ["click", "riser"] and p.json_schema()["enum"] == ["click", "riser"]
    with pytest.raises(RostrumError, match="no longer offered"):
        p.check("whoosh", "edit")
    op = type("Op", (), {"param": lambda self, name: p if name == "design" else None})()
    kind = dataclasses.replace(toy.KIND, registry=type("Reg", (), {"field_op": lambda self, t: op})())
    assert not list(kind.bad_values([{"type": "layer", "id": "a", "design": "whoosh"}]))      # an old file still opens
    assert list(kind.bad_values([{"type": "layer", "id": "a", "design": "swoosh"}]))


def test_a_warning_lets_the_file_open_and_is_said(tmp_path):
    toy.sample(tmp_path, "itm").save()
    said = "card: this card is no longer made; remove it or replace it"
    kind = dataclasses.replace(toy.KIND, warn=lambda data: [said])
    opened = Document.open(tmp_path, "itm", kind)
    assert kind.warnings(opened.data) == [said] and toy.KIND.warnings(opened.data) == []
