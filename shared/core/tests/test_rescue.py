"""Open the last version that works: a damaged document is rebuilt from its history up to the last step that applies
cleanly, and the damaged files are kept beside it, never overwritten (INTERACTION.md 1.19)."""
from rostrum_core import Document, Who, rescue, toy

KIND = toy.KIND


def test_rebuilds_to_the_last_good_step_and_keeps_the_damaged_files(tmp_path):
    doc = toy.sample(tmp_path, "main")
    doc.save()
    for layer, name in (("title", "One"), ("card", "Two"), ("cam_1", "Three")):
        doc.apply({"op": "layer.rename", "target": [layer], "args": {"name": name}}, Who.person("sam"))
        doc.save()
    hist = tmp_path / ".rostrum" / "main.history.jsonl"
    lines = [ln for ln in hist.read_text(encoding="utf-8").splitlines() if not ln.startswith('{"hash"')]
    lines[-1] = lines[-1][:40]                                   # the last step is cut off (a crash while saving)
    hist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    damaged = tmp_path / "docs" / f"main{KIND.ext}"
    damaged.write_text("{ not json", encoding="utf-8")

    plan = rescue.plan(KIND, tmp_path, "main")
    assert (plan.step, plan.steps, plan.lost) == (2, 3, 1)       # nothing written by plan
    assert damaged.read_text(encoding="utf-8") == "{ not json"

    made, r = rescue.rebuild(KIND, tmp_path, "main")
    assert made.item("card")["name"] == "Two" and made.item("cam_1")["name"] != "Three" and made.seq == 2
    assert Document.open(tmp_path, "main", KIND).item("card")["name"] == "Two"      # opens normally now
    kept = list(tmp_path.rglob("*.damaged-*"))
    assert len(kept) == 2 and "{ not json" in [p.read_text(encoding="utf-8") for p in kept]
    assert "step 2 of 3" in r.words()
