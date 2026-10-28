"""What must never drift silently: the guide's list of instrument and kit names is the engine's table (agents have no other list
and the wrong-name error points at it), the length asked for is the length delivered, a resumed agent session gets its song back,
and a wrong name is refused with the close ones."""
import re
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from rostrum_core import Document, RostrumError, Who, agent_last

from rostrum_sound import KIND, deliver, lastproject, names, run_source
from rostrum_sound.mcp import session_clock

SOUND = Path(__file__).resolve().parents[2]
ENGINE_NAMES = (SOUND / "engine" / "src" / "contract" / "names_instruments.rs").read_text(encoding="utf-8")
GUIDE = (SOUND / "guides" / "start-here.md").read_text(encoding="utf-8")


def _guide_names() -> set[str]:
    """Every backticked name in the name cell (and the "also accepted as" cell of the three-column table) of the guide's tables."""
    section = GUIDE.split("## Instrument and kit names", 1)[1].split("\n## ", 1)[0]
    found = set()
    for line in section.splitlines():
        if line.startswith("| `"):
            cells = line.strip().strip("|").split("|")
            found |= set(re.findall(r"`([\w.]+)`", "|".join(cells[:2] if len(cells) == 3 else cells[:1])))
    return found


def _engine_names() -> tuple[set[str], set[str]]:
    plain = set(re.findall(r'\("(\w+)", (?:Rec|Synth|Classic)\(', ENGINE_NAMES))
    classic = re.search(r"pub const CLASSIC: &\[&str\] = &\[([^\]]*)\]", ENGINE_NAMES).group(1)
    return plain | {f"classic.{n}" for n in re.findall(r'"(\w+)"', classic)}, set(re.findall(r'Kit \{ name: "(\w+)"', ENGINE_NAMES))


def test_names_py_the_guide_and_the_engine_table_list_the_same_names():
    built_in, kits = _engine_names()
    assert set(names.BUILT_INS) == built_in
    assert set(names.KITS) == kits
    assert _guide_names() == built_in | kits, sorted(_guide_names() ^ (built_in | kits))


def _script_error(source: str) -> str:
    doc = Document.new(KIND)
    try:
        doc.run_script("t.py", run_source(source, "t.py"), Who.script("t.py"))
    except RostrumError as e:
        return str(e)
    return ""


def test_a_wrong_instrument_names_the_close_ones_and_the_guide_and_kit_prefix_is_accepted():
    said = _script_error("track('a', builtIn='contrabass')")
    assert "basses" in said and "uprightBass" in said and "Instrument and kit names" in said
    assert "Did you mean" not in _script_error("track('a', kit='classic')")
    assert _script_error("track('a', kit='kit:classic')") == "" and _script_error("track('a', builtIn='builtIn:piano')") == ""


def _wav(path, seconds, ring_to, rate=48000):
    """A loud tone to `ring_to`, a quiet tail to `seconds`: what the engine writes for a song whose ring-out runs past its length."""
    t = np.arange(int(seconds * rate)) / rate
    x = np.where(t < ring_to, 0.5, 0.02) * np.sin(2 * np.pi * 220 * t)
    sf.write(str(path), np.stack([x, x], axis=1).astype("float32"), rate, subtype="FLOAT")


@pytest.mark.parametrize("seconds, music_ends, asked", [(4.43, 4.1, 4.0), (4.449, 4.449, 4.5)])
def test_the_file_is_exactly_the_length_asked_whatever_rings_on_or_is_silent(tmp_path, seconds, music_ends, asked):
    _wav(tmp_path / "song_mix.wav", seconds, music_ends)
    r = deliver.deliver(tmp_path, {"file": str(tmp_path / "song_mix.wav"), "stems": {}, "warnings": ["The song's length is 4.00 s; its last sounds ring out until 4.43 s"] * (seconds > asked)},
                        {}, deliver.Options.read({"sampleRate": 48000, "length": asked}), "song")
    assert r["seconds"] == pytest.approx(asked, abs=1e-3) and sf.info(r["file"]).duration == pytest.approx(asked, abs=1e-3)
    assert not r["trimmed"] and not any("ring out until" in w for w in r["warnings"])
    if seconds > asked:
        x, rate = sf.read(r["file"])
        assert abs(x[-100:]).max() < 0.01 and "faded" in r["warnings"][-1]       # the tail went to nothing inside the length


def test_a_resumed_agent_session_gets_its_song_back(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from rostrum_sound.mcp.app import open_or_new
    open_or_new(tmp_path / "proj", "song").data           # makes the document
    agent_last.remember("rostrum-sound", tmp_path / "proj", "song")
    assert lastproject.last_project()["item"] == "song"


def test_the_fix_pass_asks_for_a_listen_names_the_time_and_counts_the_passes_left():
    class Time:
        now = 0.0
        def __call__(self): return self.now
    t = Time()
    clock = session_clock.Clock(t, budget_min=15)
    clock.begin()
    t.now = 180
    said = session_clock.fix_pass(clock, 20.0)
    assert "look_music" in said and "three weakest moments" in said and "12 min 00 s of your 15 min" in said and "about 4 more passes" in said
    assert "min" not in session_clock.fix_pass(session_clock.Clock(t))
