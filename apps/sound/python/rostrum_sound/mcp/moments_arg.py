"""The `expect` argument of the listening tools: times a sound must start at, and moments that must come across.

A bare time (seconds, {"beat": n}, "#marker") only asks that a sound start there. {"at": time, "kind": …} also asks
that the moment come across as a listener hears it (listen/moments.py: a weak hit, a blurred stop, drums dropping early,
the loudest moment off the climax, a flat lift, a busy speech band in a voice span)."""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from ..doc.times import seconds
from ..listen.moments import KINDS

UNTIMED = ("climax", "lift", "voice", "drop")   # moments that are not "a sound starts here" (the onset check skips them)

EXPECT = {"expect": {"type": "array", "description": "Moments the music must deliver. Each is a time (seconds, {\"beat\": n} or \"#marker\": a sound must start there) or "
                     "{\"at\": time, \"kind\": \"hit\" | \"stop\" | \"drop\" | \"climax\" | \"lift\" | \"entry\" | \"voice\", \"end\": time (voice only)}: "
                     "with a kind the faults say whether it comes across (a weak or missing hit, a blurred stop, drums dropping early, "
                     "the loudest moment off the climax, a lift that does not lift, a busy speech band in a voice span)."}}


def parse(doc, items, where):
    """-> (times s, their labels as given, moments [{at, kind, end}]) of `expect`."""
    times, labels, moments = [], [], []
    for i, it in enumerate(items or []):
        w = f"{where} › expect[{i}]"
        if not (isinstance(it, dict) and "at" in it):
            times.append(seconds(it, doc.data, w))
            labels.append(it)
            continue
        kind = it.get("kind", "hit")
        if kind not in KINDS:
            raise RostrumError(codes.BAD_ARGUMENT, w, f'kind "{kind}"', "is not a moment", list(KINDS))
        if kind == "voice" and "end" not in it:
            raise RostrumError(codes.BAD_ARGUMENT, w, "voice", "needs end", hint='{"at": 0, "end": 30, "kind": "voice"}: the span the voice speaks over.')
        at = seconds(it["at"], doc.data, w)
        moments.append({"at": at, "kind": kind, **({"end": seconds(it["end"], doc.data, w)} if "end" in it else {})})
        if kind not in UNTIMED:
            times.append(at)
            labels.append(it["at"])
    return times, labels, moments
