"""A Sound script is plain Python (imports, classes, random.Random, print), and scripts are files in the project:
inline text is kept as <project>/scripts/<name>, and {"name": ...} runs the file again after the agent edits it."""
from rostrum_core import Who
from rostrum_sound import run_source
from rostrum_sound.script_scope import printed

from test_script_forms import server

SRC = """
from dataclasses import dataclass
import itertools, random
tempo(120); length(bar(5))
@dataclass
class Line:
    pitches: list
    def play(self, t):
        for i, p in zip(itertools.count(), self.pitches):
            t.note(p, at=bar(1) + beats(i), dur=beats(1), vel=random.Random(i).uniform(0.5, 0.9))
Line(["C4", "E4", "G4"]).play(track("k", builtIn="grandPiano"))
print("notes", 3)
"""


def test_plain_python_song():
    one = run_source(SRC, "song.py")
    assert len(one["tracks"][0]["notes"]) == 3 and printed() == ["notes 3"]
    assert run_source(SRC, "song.py") == one


def test_inline_script_is_kept_and_runs_by_name(tmp_path, monkeypatch):
    app, rt = server(tmp_path, monkeypatch)
    try:
        reply, _ = rt.call("run_script", {"source": SRC, "name": "song.py"}, Who.agent("tester"))
        kept = tmp_path / "song" / "scripts" / "song.py"
        assert reply["ok"], reply
        assert kept.read_text(encoding="utf-8") == SRC and any(str(kept) in w for w in reply["warnings"])
        kept.write_text(SRC.replace('"G4"]', '"G4", "C5"]'), encoding="utf-8")       # the agent edits the file itself
        reply, _ = rt.call("run_script", {"name": "song.py"}, Who.agent("tester"))
        assert reply["ok"], reply
        reply, _ = rt.call("inspect_notes", {"track": "k"}, Who.agent("tester"))
        assert "C5" in str(reply)
    finally:
        app.state.engine.close()
