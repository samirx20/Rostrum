"""A cleaned clip plays its cached take, and fails loudly naming the clip when the take is not made (never the
original played silently in its place); split_stems adds its four tracks once, as one undo step. A stand-in step
replaces the models, on a cache folder of its own."""
import shutil
import types
import wave

import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_sound import KIND, cleanup, compile
from rostrum_sound.cleanup import chain

AGENT = Who.agent("test")


def _wav(path):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(b"\1\0" * 2400)
    return path


FAKE = types.SimpleNamespace(STEP="fake", ENGINE="fake@1", output=lambda **s: "out.wav",
                             run=lambda src, folder, **s: shutil.copyfile(src, folder / "out.wav"))


def make_doc(media):
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "dlg"}},
               {"op": "clip.add", "target": ["dlg"], "args": {"id": "dlg.take", "media": str(media), "at": 1.0,
                                                             "fadeIn": 0.1}}], Who.person())
    return doc


def test_a_cleaned_clip_plays_its_take_or_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(chain, "_steps", lambda recipe: [(FAKE, {})] if recipe else [])
    media = _wav(tmp_path / "take.wav")
    doc = make_doc(media)
    doc.apply([{"op": "clip.set", "target": ["dlg.take"], "args": {"denoise": 0.6}}], AGENT)

    with pytest.raises(RostrumError) as e:
        compile(doc)
    assert 'clip "dlg.take"\'s cleaned take' in str(e.value) and "not made yet" in str(e.value) \
        and "render_cleanup" in str(e.value)

    made = cleanup.make(str(media), cleanup.recipe_of(doc.item("dlg.take")))
    assert made.generated
    assert compile(doc)["tracks"][0]["clips"][0]["media"] == made.file

    doc.apply([{"op": "clip.set", "target": ["dlg.take"], "args": {"useCleaned": False}}], Who.person())
    assert compile(doc)["tracks"][0]["clips"][0]["media"] == str(media)


def test_split_stems_once_and_undo(tmp_path):
    doc = make_doc(_wav(tmp_path / "song.wav"))
    split = [{"op": "clip.split_stems", "target": ["dlg.take"]}]
    doc.apply(split, AGENT)
    tracks = doc.data["tracks"]
    assert [t["id"] for t in tracks] == ["dlg", *(f"dlg.take.{s}" for s in cleanup.STEMS)]
    for t, s in zip(tracks[1:], cleanup.STEMS):
        (c,) = t["clips"]
        assert t["name"] == f"dlg · {s}" and c["stem"] == s and c["at"] == 1.0 and c["fadeIn"] == 0.1
    assert doc.item("dlg.take")["volume"] == 0

    with pytest.raises(RostrumError) as e:
        doc.apply(split, AGENT)
    assert "already split" in str(e.value) and len(doc.data["tracks"]) == 5

    doc.undo(AGENT)
    assert [t["id"] for t in doc.data["tracks"]] == ["dlg"] and doc.item("dlg.take")["volume"] == 1
