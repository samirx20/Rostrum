"""A line's length is estimated from its words before it is made (voice_estimate), within the range measured on real takes."""
from rostrum_sound import voice_estimate as V

# (words, language, the real take's seconds): measured with the Qwen3-TTS voice (VOICE.md "How long a line takes")
TAKES = [("Now I know it is only the room, breathing.", "auto", 3.2), ("Somewhere down the street, a radio hums an old song.", "auto", 3.52),
         ("Hold the day gently, and let it go.", "auto", 2.48), ("Wait. Stop. Listen to that.", "english", 2.8),
         ("Heute ist ein schöner Tag, und wir gehen zusammen im Park spazieren.", "german", 5.2),
         ("今天天气很好，我们一起去公园散步吧。", "chinese", 3.12)]


def test_estimate_lands_in_its_range_on_measured_takes():
    for text, lang, real in TAKES:
        e = V.estimate(text, lang)
        assert e["low"] <= real <= e["high"], (text, e, real)


def test_longer_words_take_longer_and_pauses_count():
    assert V.estimate("one two three four five six seven")["seconds"] > V.estimate("one two three")["seconds"]
    assert V.estimate("Yes, no, maybe.")["seconds"] > V.estimate("Yes no maybe")["seconds"]


def test_scripts_are_told_apart():
    assert V.estimate("今日はとても良い天気ですね。")["basis"] == "japanese"
    assert V.estimate("春天来了。")["basis"] == "chinese"
    assert V.estimate("hello")["basis"] == "latin"
    assert V.said({"seconds": 3.2, "low": 2.5, "high": 3.9}) == "about 3.2 s (2.5-3.9)"
