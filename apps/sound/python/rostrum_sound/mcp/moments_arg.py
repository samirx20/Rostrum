"""The `expect` argument of the listening tools: times a sound must start at, and moments that must come across.

A bare time (seconds, {"beat": n}, "#marker") only asks that a sound start there. {"at": time, "kind": …} also asks
that the moment come across as a listener hears it (listen/moments.py: a weak hit, a blurred stop, drums dropping early,
the loudest moment off the climax, a flat lift, a busy speech band in a voice span)."""
from __future__ import annotations

from rostrum_core import RostrumError, codes

from ..doc import tempo
from ..doc.times import seconds
from ..listen.moments import KINDS

UNTIMED = ("climax", "lift", "voice", "drop")   # moments that are not "a sound starts here" (the onset check skips them)

EXPECT = {"expect": {"type": "array", "description": "Moments the music must deliver. Each is a time (seconds, {\"beat\": n} or \"#marker\": a sound must start there) or "
                     "{\"at\": time, \"kind\": \"hit\" | \"stop\" | \"drop\" | \"climax\" | \"lift\" | \"entry\" | \"voice\", \"end\": time (voice only)}: "
                     "with a kind the faults say whether it comes across (a weak or missing hit, a blurred stop, drums dropping early, "
                     "a climax cut short or off its time, a build already at the ceiling, a lift that does not lift, a busy speech band in a voice span). "
                     "{\"kind\": \"tempo\", \"bpm\": 132} (no `at`): the brief's tempo; the song's start tempo or the tempo it holds for most of its length "
                     "off by more than 0.5 % is named, with the ways to land a sync moment that keep it."}}


def _tempo(doc, it, w) -> dict:
    """A {"kind": "tempo", "bpm"} entry with the song's start tempo and the tempo it holds longest (the median of the
    tempo every 0.1 s from bar 1 to the end), so a short `land` glide or a pickup before bar 1 is not called bent."""
    bpm = it.get("bpm")
    if not isinstance(bpm, (int, float)) or isinstance(bpm, bool) or not 20 <= bpm <= 400:
        raise RostrumError(codes.BAD_ARGUMENT, w, "tempo", "needs bpm, a number from 20 to 400", hint='{"kind": "tempo", "bpm": 132}')
    start = tempo.start_bpm(doc.data)
    length = seconds(doc.data["length"], doc.data, w) if doc.data.get("length") is not None else 0.0
    t0 = tempo.seconds_at(doc.data, 0.0)
    steps = int((length - t0) * 10)
    held = sorted(tempo.bpm_at(doc.data, t0 + i / 10) for i in range(steps))[steps // 2] if steps > 0 else start
    return {"kind": "tempo", "bpm": float(bpm), "start_bpm": start, "held_bpm": held}


def parse(doc, items, where):
    """-> (times s, their labels as given, moments [{at, kind, end}]) of `expect`."""
    times, labels, moments = [], [], []
    for i, it in enumerate(items or []):
        w = f"{where} › expect[{i}]"
        if isinstance(it, dict) and it.get("kind") == "tempo":
            moments.append(_tempo(doc, it, w))
            continue
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
