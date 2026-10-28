"""A script writes the mix's routing (buses, sends, ducks); taking a line out of the script takes it out of the song."""
from rostrum_core import Document, Who

from rostrum_sound import KIND, run_source
from rostrum_sound.builder import Song

S = Who.script("song.py")
SRC = """
tempo(90); length(bar(3))
d = track("drums", kit="drums"); b = track("bass", builtIn="bass")
d.hit("kick", at=beat(0)); b.note("A1", at=beat(0), dur=1)
{lines}
"""


def test_send_and_duck_come_and_go_with_the_script():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SRC.format(lines='b.duck(under=["drums"], depth=0.4); b.send("fx", level=0.2)').replace(
        'b.send("fx", level=0.2)', ''), "song.py", doc), S)
    bass = doc.data["tracks"][1]
    assert [d["under"] for d in bass["ducks"]] == [["drums"]]
    doc.run_script("song.py", run_source(SRC.format(lines=""), "song.py", doc), S)
    assert doc.data["tracks"][1]["ducks"] == []


def test_a_bus_is_a_checked_item_of_the_song():
    song = Song()
    verb = song.bus("verb", volume=0.8)
    verb.effect("reverb", space="hall", mix=1.0)
    song.track("keys", builtIn="piano", output="verb").send("verb", level=0.3)
    tree = song.tree()
    assert [(b["id"], b["effects"][0]["effect"]) for b in tree["buses"]] == [("verb", "reverb")]
    assert tree["tracks"][0]["sends"][0]["bus"] == "verb"
