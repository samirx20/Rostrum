"""What agents rely on: a checked reply with a loudness miss opens with it, and `keep` marks it as left on purpose
(synthetic numbers, no engine). Faults are notes: no render is refused (Sam, 2026-10-29)."""
from rostrum_core.mcp import Reply
from rostrum_core.mcp import faults as shared

from rostrum_sound.listen import fault_shape


def test_loudness_miss_opens_the_reply_and_keep_marks_it(tmp_path):
    found = fault_shape.loudness_fault(-16.9, -14.0)
    assert [f["id"] for f in found] == ["loudness"]
    assert Reply("Rendered.", faults=found).to_dict()["summary"].startswith("NOT DONE: 1 fault. [loudness]")
    assert Reply("Rendered.", faults=fault_shape.loudness_fault(-14.2, -14.0)).to_dict()["summary"].startswith("DONE:")
    kept = fault_shape.loudness_fault(-16.9, -14.0)
    assert shared.apply_keep(kept, {"loudness": "a quiet documentary bed on purpose"}) == []
    assert Reply("Rendered.", faults=kept).to_dict()["summary"].startswith("DONE:")   # a note, kept with its why: no gate
