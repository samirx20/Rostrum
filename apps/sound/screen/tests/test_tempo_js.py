"""The screen places notes in beats through its own port of the tempo map (qml/Tempo.js): it must give the very
seconds tempo.py gives, ramps and changes in seconds included, or notes drift off their bars only on screen."""
from pathlib import Path

from PySide6.QtQml import QJSEngine
from rostrum_sound.doc import tempo

JS = Path(__file__).resolve().parents[1] / "qml" / "Tempo.js"


def test_tempo_js_gives_tempo_pys_seconds():
    root = {"tempo": 120, "tempos": [{"at": {"beat": 16}, "bpm": 90, "ramp": True},
                                     {"at": {"beat": 48}, "bpm": 140},
                                     {"at": 60.0, "bpm": 100, "ramp": True},
                                     {"at": {"beat": 160}, "bpm": 70}]}
    engine = QJSEngine()
    src = JS.read_text(encoding="utf-8").replace(".pragma library", "")
    engine.evaluate(src)
    segs = [list(s) for s in tempo.segments(root)]
    js_map = engine.toScriptValue(segs)
    seconds = engine.globalObject().property("seconds")
    for beat in [0, 0.25, 15.99, 16, 23.5, 47.999, 48, 70.125, 100, 131.3, 159.75, 160, 400]:
        got = seconds.call([js_map, beat]).toNumber()
        assert abs(got - tempo.seconds_at(root, beat)) < 1e-9, beat
