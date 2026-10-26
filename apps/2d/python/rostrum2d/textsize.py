"""A text's own size, measured by the 2D engine (ENGINE_CONTRACT.md § 1 `measure`): the one source of truth for a
text's box, read through sizes.own_size by auto layout, the agents' geometry and the screen's boxes. Each distinct
set of a text's fields is measured once and kept, so a layout solved on every frame asks the engine only when a
text's fields change; `prime` measures many in one round trip (layout.py and layoutbake.py prime a frame's texts).

The engine: one a caller already runs, registered with `use(engine)` for the thread that runs it (a script or a
render that has one open); else a measuring engine of this module's own, started on the first text not seen yet
(it needs no scene) and closed when Python exits. No engine built → EngineError, loudly: there is no estimate.
"""
from __future__ import annotations

import atexit
import threading
from contextlib import contextmanager

from .engine import EngineError

# What decides a text's box: what the engine's measure takes (render/src/scene/measure.rs). Colour, outline and
# the rest don't change it.
FIELDS = ("body", "font", "size", "weight", "italic", "stretch", "tracking", "lineHeight", "align", "boxWidth",
          "ligatures", "figures", "smallCaps", "features", "slant", "grade", "axes",
          "path", "pathOffset", "pathAlign", "pathOverflow", "letterDelay",
          "counter", "count", "countDecimals", "countDigits", "countSeparator", "countPrefix", "countSuffix")   # a counter: its number now
KEEP = 4096                 # sizes kept; past it the table starts again (a slider dragged through many sizes)

_lock = threading.RLock()
_sizes: dict[tuple, tuple[float, float]] = {}
_local = threading.local()  # .engines: the engines registered on this thread (use), innermost last
_own = None                 # this module's own measuring engine


def open_engine():
    """The measuring engine started when none is registered (tests swap this)."""
    from .engine import Engine
    return Engine()


@contextmanager
def use(engine):
    """Measure with `engine` (an open Engine) on this thread while the block runs."""
    stack = _local.__dict__.setdefault("engines", [])
    stack.append(engine)
    try:
        yield engine
    finally:
        stack.pop()


def _engine():
    global _own
    stack = getattr(_local, "engines", [])
    if stack:
        return stack[-1]
    if _own is None:
        _own = open_engine()
        atexit.register(_own.close)
    return _own


def warm() -> None:
    """Start this module's own measuring engine now, on a thread of its own: an engine takes over a second to give its
    first answer, and the screen's first boxes (while its window loads) would otherwise wait for it on the GUI thread.
    A start that fails here fails again, loudly, at the first real measure (the engine is then still None)."""
    def start():
        from . import fields as F
        with _lock:
            if _own is None:
                try:
                    sizes([F.defaults("text")])      # a real text: the engine reads its fonts now, not at the first
                except Exception:  # noqa: BLE001     text picked (~230 ms); a failure is said by the first real measure
                    pass
    threading.Thread(target=start, daemon=True, name="textsize-warm").start()


def key(p: dict) -> tuple:
    """The fields of a text that decide its box (`p`: its evaluated fields, evaluate.resolve). A font this computer lacks
    is measured in the stand-in font (the box the canvas draws in its place, missing_font.py), never refused."""
    return tuple(_measured_font(p) if f == "font" else p[f] for f in FIELDS)


def _measured_font(p: dict) -> str:
    from . import fields as F, fontlist
    try:
        return p["font"] if p["font"] in fontlist.names() else F.defaults("text")["font"]
    except EngineError:         # no engine built: the measure says so
        return p["font"]


def sizes(texts: list[dict]) -> list[tuple[float, float]]:
    """(w, h) of each text (its evaluated fields); the ones not seen yet measured in one round trip."""
    with _lock:
        keys = [key(p) for p in texts]
        new = list(dict.fromkeys(k for k in keys if k not in _sizes))
        if not new:
            return [_sizes[k] for k in keys]
        got = _engine().measure([{"id": str(i), **dict(zip(FIELDS, k))} for i, k in enumerate(new)])
        fresh = {k: got[str(i)] for i, k in enumerate(new)}
        out = [fresh[k] if k in fresh else _sizes[k] for k in keys]
        if len(_sizes) + len(fresh) > KEEP:
            _sizes.clear()
        _sizes.update(fresh)
        return out


def size(p: dict) -> tuple[float, float]:
    return sizes([p])[0]


def prime(texts: list[dict]) -> None:
    """Measure these texts now, together (the next `size` of any of them is kept)."""
    if texts:
        sizes(texts)
