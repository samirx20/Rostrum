"""The song in one line, for agents: tempo, time signature, key and how long it is, in bars and seconds.

    Song: 96 bpm, 4/4, D minor; 8 bars long (ends where bar 9 starts, 20.0 s).

`length` is where the song ends (a time), so `length(bar(9))` is 8 bars: bar(n) is always the start of bar n. That trips
agents who read it as "9 bars", so run_script and inspect_item (the song) both end with this line, worked out from the
document (one source of truth: the meter and tempo maps).
"""
from __future__ import annotations

import dataclasses

from rostrum_core import RostrumError

from ..doc import meter, musical, tempo, times


def length_words(root: dict) -> str:
    """'8 bars long (ends where bar 9 starts, 20.0 s)'; 'no length set: ...' when the mix runs to its last sound."""
    if root.get("length") is None:
        return "no length set (the mix runs to its last sound + 2 s)"
    try:
        sec = times.seconds(root["length"], root, "length")
    except RostrumError as e:
        return f"length {root['length']!r} can't be worked out ({e.problem})"
    bars = meter.bar_at(root, tempo.beat_at(root, sec))
    if abs(bars - round(bars)) < 1e-6:
        n = round(bars)
        return f"{n} bar{'s' * (n != 1)} long (ends where bar {n + 1} starts, {sec:.1f} s)"
    return f"ends at {musical.position(sec, root)}, {musical.length(sec, root)} long ({sec:.1f} s)"


def song_line(root: dict) -> str:
    sig = f"{meter.start_per_bar(root)}/{meter.start_unit(root)}"
    keys = [k.get("key") for k in root.get("keys") or [] if k.get("key")]
    key = f", {keys[0]}" if keys else ""
    return f"Song: {root.get('tempo', 120):g} bpm, {sig}{key}; {length_words(root)}."


def with_song_line(runtime) -> None:
    """run_script and inspect_item (the song) end with the song line, so a length an agent misread shows at once."""
    for name, wanted in (("run_script", lambda a: True), ("inspect_item", lambda a: a.get("id") in (None, "root"))):
        old = runtime.tools.get(name)

        def wrapped(ctx, args, old=old, wanted=wanted):
            reply = old.fn(ctx, args)
            if wanted(args):
                root = ctx.document(args.get("item")).data
                reply.summary = f"{reply.summary} {song_line(root)}"
                reply.data = {**reply.data, "song": {"tempo": root.get("tempo"), "length": root.get("length"),
                                                     "length_said": length_words(root)}}
            return reply
        runtime.tools._tools[name] = dataclasses.replace(old, fn=wrapped)
