"""A voice line plays its cached take, and a line whose take is not made fails loudly naming the line
(never a silent gap in the mix). Works on a cache folder of its own; the voice model is not run."""
import wave

import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_sound import KIND, compile, voice

TEXT = "The night is long."


def make_doc():
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "vo", "instrument": "voice", "voice": "aiden", "style": "calm"}},
               {"op": "line.add", "target": ["vo"], "args": {"text": TEXT, "at": 2.0, "seed": 3}}], Who.person())
    return doc


def test_a_line_is_a_clip_on_its_take_or_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_CACHE_DIR", str(tmp_path))
    doc = make_doc()
    assert doc.item("vo.line_1")["text"] == TEXT

    with pytest.raises(RostrumError) as e:
        compile(doc)
    assert "vo.line_1" in str(e.value) and "not made yet" in str(e.value) and "voice tool" in str(e.value)

    take = voice.cache_dir() / voice.key(TEXT, "aiden", "calm", "auto", 3) / "take.wav"
    take.parent.mkdir(parents=True)
    with wave.open(str(take), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(b"\0\0" * 24000)

    track = compile(doc)["tracks"][0]
    assert track["clips"] == [{"media": str(take), "at": 2.0, "volume": 1}] and "instrument" not in track
