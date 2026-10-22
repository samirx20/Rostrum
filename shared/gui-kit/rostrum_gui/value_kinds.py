"""One way to show each kind of value, for Python (agents' "what's here", reports, tests): the very same formatter and
parser the kit's fields use, qml/RostrumKit/ValueKinds.js, run here in a JS engine, so a screen and an agent never
disagree on "80 %", "−1.9 dB" or "L 30". The kinds and their rules are described in that file.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtQml import QJSEngine, QJSValue

SOURCE = Path(__file__).resolve().parent.parent / "qml" / "RostrumKit" / "ValueKinds.js"


@lru_cache(maxsize=1)
def _js():
    # A JS engine needs a Qt application (without one it crashes the process): the app's own, else a plain one.
    _js.app = QCoreApplication.instance() or QCoreApplication([])
    engine = QJSEngine()
    code = SOURCE.read_text(encoding="utf-8").replace(".pragma library", "", 1)
    done = engine.evaluate(code, str(SOURCE))
    if done.isError():
        raise RuntimeError(f"ValueKinds.js failed to load: {done.toString()}")
    return engine


def _call(name: str, *args):
    out = _js().globalObject().property(name).call([QJSValue(a) for a in args])
    if out.isError():
        raise RuntimeError(f"ValueKinds.{name}{args}: {out.toString()}")
    return out.toVariant()


def kinds() -> list[str]:
    return list(_js().globalObject().property("KINDS").toVariant())


def format(kind: str, value: float, step: float = 0.01) -> str:   # noqa: A001 — the kit's own word
    """The stored value as the screen shows it: format("percent", 0.8) == "80 %"."""
    return _call("format", kind or "", float(value), float(step))


def parse(kind: str, text: str) -> float | None:
    """Typed words as the stored value, None if they aren't one: parse("pan", "L 30") == -0.3."""
    v = _call("parse", kind or "", str(text))
    return None if v != v else float(v)       # NaN: not a value
