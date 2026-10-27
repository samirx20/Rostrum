"""Lip sync without the model: mouth cues rest in silences, hold over short gaps and lead the sound; a script re-run
keeps a person's mouth key; the cache key changes with the words."""
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source
from rostrum_core.lipsync import phonemes, visemes

SAM = Who.person("sam")
PHONES = [{"phone": "m", "start": 0.50, "end": 0.52}, {"phone": "ɑː", "start": 0.60, "end": 0.62},   # 1 frame of D
          {"phone": "f", "start": 0.64, "end": 0.645},                                                 # short gap
          {"phone": "uː", "start": 1.50, "end": 1.54}]                                                 # after silence
SRC = '''
comp("c", fps=25, duration=3)
with group("face"):
    rest = shape("m_X"); closed = shape("m_A"); wide = shape("m_D")
    lipsync("take.wav", at=1.0, shapes={"X": rest, "A": closed, "D": wide})
'''


def test_cues_rest_in_silence_hold_short_gaps_and_lead():
    cues = visemes.cues(PHONES, fps=25, lead_frames=1, min_frames=2, rest_gap=0.25, tail=0.08, start=0, end=2)
    assert [(c["shape"], c["start"]) for c in cues] == [("X", 0), ("A", 0.48), ("G", 0.6), ("X", 0.72),
                                                        ("F", 1.44), ("X", 1.6)]
    assert visemes.resolve("F", {"X", "A", "D"}) == "A" and visemes.resolve("E", {"X", "C"}) == "C"


def test_a_line_ends_on_the_rest_mouth_even_when_the_clip_ends_on_its_last_sound():
    """Hand maker C, C10: a voice take cut right after its last word left the last shape open to the scene's end."""
    cues = visemes.cues(PHONES, fps=25, tail=0.08, start=0, end=1.54)          # the file ends on the last phone
    assert cues[-1]["shape"] == "X" and abs(cues[-1]["start"] - 1.64) < 0.05 and cues[-2]["shape"] != "X"
    assert visemes.cues(PHONES, fps=25, start=0, end=2)[-1]["shape"] == "X"   # with silence after it, as before


def test_rerun_keeps_a_persons_mouth_key_and_words_change_the_cache_key(monkeypatch, tmp_path):
    monkeypatch.setattr(phonemes, "analyse", lambda *a, **k: {"phones": PHONES, "words": [], "end": 2.0,
                                                              "mode": "decoded", "device": "cpu", "computed": False})
    d = Document.new(KIND)
    d.run_script("talk.py", run_source(SRC, "talk.py"))
    wide_on = d.item("m_D.opacity.k1560")                      # comp 1.0 + 0.56 s: the wide mouth opens
    assert wide_on["v"] == 1 and wide_on["ease"] == "hold"
    d.apply({"op": "key.set", "target": wide_on["id"], "args": {"t": 1.58}}, SAM)      # a person retimes it
    report = d.run_script("talk.py", run_source(SRC, "talk.py"))
    assert d.item("m_D.opacity.k1560")["t"] == 1.58 and not report.held
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    assert phonemes.key(wav, text="one hour") != phonemes.key(wav, text="one hour.") != phonemes.key(wav)
