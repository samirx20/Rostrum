"""Tell QML only news: a part's `changed` sent only when a property it notifies reads differently than last time.

A part (a QObject whose properties QML reads, all notified by one `changed`) that relays a broad signal (the document
changed, the outline changed) made every binding on every one of its properties run again on every edit, even when
nothing it shows moved: the canvas overlays redid their handles, the rail rebuilt its tools. `relay(part)` returns the
slot to connect instead of `changed`: it reads the part's own properties (those `changed` notifies) and sends `changed`
only when one differs. A part that changes for its own reasons still sends `changed` itself; the next relay then sends
it again (what QML read in between is not known).

    bridge.outlineChanged.connect(news.relay(self))      # instead of bridge.outlineChanged.connect(self.changed)
"""
from __future__ import annotations


def _names(part, signal: str) -> list[str]:
    mo = part.metaObject()
    out = []
    for i in range(mo.propertyOffset(), mo.propertyCount()):
        p = mo.property(i)
        if p.hasNotifySignal() and bytes(p.notifySignal().name()).decode() == signal:
            out.append(p.name())
    return out


def relay(part, signal: str = "changed"):
    """The slot that sends `part.<signal>` only when a property it notifies reads differently. When the part sends it
    itself, what QML read is unknown: the next relay sends it again."""
    names, state = _names(part, signal), {"told": None, "mine": False}
    sig = getattr(part, signal)

    def own():
        if not state["mine"]:
            state["told"] = None

    def check():
        now = tuple(getattr(part, n) for n in names)
        if now != state["told"]:
            state["told"], state["mine"] = now, True
            try:
                sig.emit()
            finally:
                state["mine"] = False
    sig.connect(own)
    return check
