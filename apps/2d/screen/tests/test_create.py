"""A drawn shape is one undo step; a typing session (new text or an edit) is one undo step, never one per letter."""
from test_screen import bridge  # noqa: F401  (the headless bridge)


def steps(b):
    return len(b.doc.history.changes)


def test_shape_and_typing_are_one_undo_step_each(bridge):
    create, n = bridge.create, steps(bridge)
    create.addShape("ellipse", 100, 100, 60, 40)
    assert steps(bridge) == n + 1 and bridge.doc.item("shape_1")["shape"] == "ellipse"
    create.beginText(20, 20, 0)
    for i in range(1, 6):
        create.typeText("hello"[:i])
    create.commitText("hello")
    assert steps(bridge) == n + 2 and bridge.doc.item("text_1")["body"] == "hello"
    create.editText("text_1")
    for body in ("h", "he", "hey"):
        create.typeText(body)
    create.commitText("hey")
    assert steps(bridge) == n + 3 and bridge.doc.item("text_1")["body"] == "hey"
    bridge.undo()
    assert bridge.doc.item("text_1")["body"] == "hello"
    create.beginText(20, 20, 0)
    create.commitText("")                                  # nothing typed: nothing added
    assert steps(bridge) == n + 4 and not bridge.doc.has("text_2")      # (the undo is itself a recorded step)


def test_a_new_text_is_selected_from_its_first_letter(bridge):
    """The settings panel shows the text being typed (never an empty block); typed and emptied again, it is gone."""
    create = bridge.create
    create.beginText(40, 40, 0)
    create.typeText("a")
    new = bridge.selected
    assert new and bridge.doc.item(new)["type"] == "text" and create.typing, new
    create.commitText("")
    assert bridge.selected == "" and not bridge.doc.has(new), (new, bridge.selected)
