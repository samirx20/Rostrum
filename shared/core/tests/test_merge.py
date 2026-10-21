"""Re-running a script never wipes a person's work (OPERATIONS.md § 7): the rule users rely on most."""
import copy

from rostrum_core import Who, toy

SAM, SCRIPT = Who.person("sam"), Who.script("intro.py")


def produce(**over):
    """What the script 'intro.py' builds: a card and a title, with overrides per run."""
    out = toy.KIND.blank()
    card = {"id": "card", "type": "rect", "name": "Card", **toy.DEFAULTS["rect"], "x": 400}
    title = {"id": "title", "type": "text", "name": "Title", **toy.DEFAULTS["text"], "body": "Hi"}
    for k, v in over.items():
        item_id, field = k.split("__")
        (card if item_id == "card" else title)[field] = v
    out["layers"] = [card, title]
    return out


def fresh():
    doc = toy.Document.new(toy.KIND)
    r = doc.run_script("intro.py", produce(), SCRIPT)
    assert r.applied and not r.held and doc.item("card")["x"] == 400
    return doc


def move(doc, x):
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": x}}, SAM, label="Move card")


def test_rerun_keeps_a_persons_move_and_says_so():
    doc = fresh()
    move(doc, 620)
    r = doc.run_script("intro.py", produce(card__x=500, title__body="Hello"), SCRIPT)
    assert doc.item("card")["x"] == 620                      # the person's value stays
    assert doc.item("title")["body"] == "Hello"              # the script's other change lands
    assert [h["key"] for h in r.held] == ["card.x"]
    assert r.held[0]["kept"] == 620 and r.held[0]["who"] == "person:sam" and "Move card" in r.summary()


def test_held_change_is_reported_again_and_force_applies_it():
    doc = fresh()
    move(doc, 620)
    doc.run_script("intro.py", produce(card__x=500), SCRIPT)
    again = doc.run_script("intro.py", produce(card__x=500), SCRIPT)
    assert [h["key"] for h in again.held] == ["card.x"] and again.change is None
    forced = doc.run_script("intro.py", produce(card__x=500), SCRIPT, force=["card.x"])
    assert not forced.held and doc.item("card")["x"] == 500


def test_same_script_twice_changes_nothing():
    doc = fresh()
    move(doc, 620)
    seq = doc.seq
    r = doc.run_script("intro.py", produce(), SCRIPT)
    assert r.change is None and not r.held and doc.seq == seq and doc.item("card")["x"] == 620


def test_person_added_and_deleted_things_survive_a_rerun():
    doc = fresh()
    doc.apply({"op": "layer.add", "args": {"type": "rect", "id": "sticker"}}, SAM)
    doc.apply({"op": "layer.remove", "target": ["title"]}, SAM)
    r = doc.run_script("intro.py", produce(title__body="Changed"), SCRIPT)
    assert doc.has("sticker") and not doc.has("title")      # not re-added, not wiped
    assert [h["key"] for h in r.held] == ["title.body"]
    assert r.removed == []                                     # a person's sticker is never taken out


def test_script_delete_of_an_edited_item_is_held():
    doc = fresh()
    move(doc, 620)
    out = produce()
    out["layers"] = [l for l in out["layers"] if l["id"] != "card"]
    r = doc.run_script("intro.py", out, SCRIPT)
    assert doc.item("card")["x"] == 620 and [h["key"] for h in r.held] == ["card"]


def test_untouched_items_follow_the_script_including_delete_and_reorder():
    doc = fresh()
    move(doc, 620)
    out = produce()
    out["layers"].reverse()
    out["layers"].append({"id": "logo", "type": "rect", "name": "Logo", **toy.DEFAULTS["rect"]})
    doc.run_script("intro.py", out, SCRIPT)
    assert [l["id"] for l in doc.data["layers"]] == ["title", "card", "logo"] and doc.item("card")["x"] == 620
    out = copy.deepcopy(out)
    out["layers"] = [l for l in out["layers"] if l["id"] != "logo"]
    r = doc.run_script("intro.py", out, SCRIPT)
    assert not doc.has("logo")
    assert r.removed == [{"id": "logo", "type": "rect"}] and "removed: logo (rect)" in r.summary()     # the reply names what went
    assert any("Removed \"logo\"" in w for w in r.warnings())


def test_bad_script_value_is_refused_whole():
    import pytest
    from rostrum_core import RostrumError
    doc = fresh()
    with pytest.raises(RostrumError, match="out of range"):
        doc.run_script("intro.py", produce(card__x=10**9, title__body="New"), SCRIPT)
    assert doc.item("title")["body"] == "Hi" and doc.seq == 1
