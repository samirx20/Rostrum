"""A text nobody named reads as its words, and so does its copy after it is retyped (hand maker row 7: a copy stuck at
"Mira Okafor copy 3"); counting texts are "Counter", "Counter 2" … among the counters (row 9: they were "Counter 7")."""
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source
from rostrum2d.names import copy_base, display_name

SAM = Who.person("sam")


def test_a_text_read_as_its_words_is_copied_unnamed_and_a_named_one_as_name_copy():
    assert copy_base({"id": "text_3", "type": "text", "name": "Text 3", "body": "Mira Okafor"}) == "Text"
    assert copy_base({"id": "t", "type": "text", "name": "Speaker", "body": "Mira"}) == "Speaker copy"
    assert copy_base({"id": "t", "type": "text", "name": "Speaker copy 2", "body": "Mira"}) == "Speaker copy"


def test_counters_are_named_among_counters_and_read_as_words_again_when_they_stop():
    d = Document.new(KIND)
    d.run_script("a.py", run_source('comp("c", duration=2)\n' + "".join(f'text(body="{i}")\n' for i in range(5)), "a.py"))
    texts = [l for l in d.data["comps"][0]["layers"] if l["type"] == "text"]
    for t in texts[1::2]:                                     # the 2nd and 4th texts count
        d.apply({"op": "text.set", "target": [t["id"]], "args": {"counter": True}}, SAM)
    assert [display_name(d.item(t["id"])) for t in texts[1::2]] == ["Counter", "Counter 2"]
    d.apply({"op": "text.set", "target": [texts[1]["id"]], "args": {"counter": False}}, SAM)
    assert display_name(d.item(texts[1]["id"])) == "1"
