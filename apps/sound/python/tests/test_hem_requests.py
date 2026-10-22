"""What 2D relies on: a voice line's word times are heard once and then only read back; a line not heard is a loud
error on read; "main mix" is marked on the project and round-trips. The speech model is not run (a stand-in listens)."""
import wave

import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_sound import KIND, main_mix, voice, voice_words

TEXT = "The night is long"


def make(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_CACHE_DIR", str(tmp_path / "cache"))
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "vo", "instrument": "voice", "voice": "aiden"}},
               {"op": "line.add", "target": ["vo"], "args": {"text": TEXT, "at": 2.0}}], Who.person())

    def silence(folder):
        with wave.open(str(folder / "take.wav"), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(b"\0\0" * 24000)
    voice.store().put("voice", voice.key(TEXT, "aiden", "", "auto", 1), silence)
    return doc


def test_words_are_heard_once_and_read_back(tmp_path, monkeypatch):
    doc, heard = make(tmp_path, monkeypatch), []

    def listen(wav):
        heard.append(wav)
        return [{"word": w, "start": 0.2 * i, "end": 0.2 * i + 0.15} for i, w in enumerate(TEXT.lower().split())]

    with pytest.raises(RostrumError) as e:
        voice_words.read(doc)
    assert "not stored yet" in str(e.value) and "vo.line_1" in str(e.value)

    first = voice_words.compute(doc, listen=listen)[0]
    again = voice_words.compute(doc, listen=listen)[0]
    assert len(heard) == 1 and first["heard_now"] and not again["heard_now"]
    stored = voice_words.read(doc)[0]
    assert stored["words"] == first["words"] and len(heard) == 1
    assert [w["word"] for w in stored["words"]] == TEXT.split()                 # the line's own spelling
    assert stored["words"][1]["start"] == 2.2 and stored["start"] == 2.0         # song seconds


def test_pieces_become_words():
    got = voice_words._pieces_to_words([" The", " ni", "ght", "▁is"], [0.0, 0.3, 0.4, 0.8], 1.0)
    assert [w["word"] for w in got] == ["The", "night", "is"] and got[1]["start"] == 0.3 and got[1]["end"] == 0.56


def test_main_mix_round_trip(tmp_path):
    for i in ("a", "b"):
        Document.new(KIND, folder=str(tmp_path), item=i).save()
    assert main_mix.is_main(tmp_path, "a") and not main_mix.is_main(tmp_path, "b")   # the first by name until marked
    assert main_mix.make_main(tmp_path, "b")["was"] == "a"
    assert main_mix.is_main(tmp_path, "b") and not main_mix.is_main(tmp_path, "a")
    with pytest.raises(RostrumError):
        main_mix.make_main(tmp_path, "nope")
