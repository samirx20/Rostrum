"""A played track's controller lanes and MIDI's controllers, both ways: the one place that knows which lane is
which controller and how their values map.

    sustain  ↔ CC 64 (pedal: 0 up … 1 down; down at 0.5 / 64 or more)
    dynamics ↔ CC 11 (expression: 0 … 1 ↔ 0 … 127; above 1 is written as 127, said aloud)
    vibrato  ↔ CC 1  (mod wheel: 0 … 1 ↔ 0 … 127)
    bend     ↔ the pitch wheel (-1 … 1 ↔ -8192 … 8191), its range (`bendRange`, semitones) ↔ RPN 0

    lanes, bend_range = to_lanes(events, division)    # import: {lane: [[{"beat": b}, v], …]}; None = MIDI's 2
    events = from_lanes(track, root, tick, channel, skipped)   # export: (tick, order, raw bytes)

A controller jump is a step (two points at one beat); a dense stream (a swell drawn as many messages) stays
a line through its points. A lane starts from its resting value (pedal up, full expression, no bend) until
its first message, so a pedal pressed at bar 2 doesn't ring from the start.
"""
from __future__ import annotations

from ..doc import lanes as LN
from ..doc import times

CC = {64: "sustain", 11: "dynamics", 1: "vibrato"}
LANE_CC = {v: k for k, v in CC.items()}
REST = {"sustain": 0.0, "dynamics": 1.0, "vibrato": 0.0, "bend": 0.0}
STEP = 1 / 32          # beats: messages further apart than this are steps, closer ones a line
SAMPLE = 20            # ticks between written values along a sloped stretch (1/24 beat at 480 per quarter)
MIDI_BEND_RANGE = 2


def _value(lane: str, raw: int) -> float:
    if lane == "sustain":
        return 1.0 if raw >= 64 else 0.0
    if lane == "bend":
        return round(raw / (8191 if raw > 0 else 8192), 4)
    return round(raw / 127, 4)


def to_lanes(events, division: int) -> tuple[dict, float | None]:
    """A MIDI track's controller events (its non-drum channels) as lanes, and the bend range RPN 0 set, if any."""
    msgs, rpn, bend_range = {}, {}, None
    for tick, kind, data in events:
        if kind == "bend":
            msgs.setdefault("bend", []).append((tick, data[1]))
        elif kind == "cc":
            ch, num, raw = data
            if num in (101, 100):
                rpn[(ch, num)] = raw
            elif num == 6 and rpn.get((ch, 101)) == 0 and rpn.get((ch, 100)) == 0:
                bend_range = float(raw)
            elif num in CC:
                msgs.setdefault(CC[num], []).append((tick, raw))
    lanes = {}
    for lane, ms in msgs.items():
        pts, last = [], None
        for tick, raw in ms:
            b, v = round(tick / division, 4), _value(lane, raw)
            if last is None:
                if b > 0 and v != REST[lane]:
                    pts.append([{"beat": 0}, REST[lane]])
                    last = (0.0, REST[lane])
            if last is not None and v == last[1]:
                continue
            if last is not None and (lane == "sustain" or b - last[0] > STEP):
                pts.append([{"beat": b}, last[1]])          # held until here, then a step
            pts.append([{"beat": b}, v])
            last = (b, v)
        if any(p[1] != REST[lane] for p in pts):
            lanes[lane] = pts
    return lanes, (bend_range if bend_range not in (None, MIDI_BEND_RANGE) else None)


def _raw(lane: str, v: float) -> int:
    if lane == "sustain":
        return 127 if v >= 0.5 else 0
    if lane == "bend":
        return max(-8192, min(8191, round(v * (8191 if v > 0 else 8192))))
    return max(0, min(127, round(v * 127)))


def _message(lane: str, channel: int, raw: int) -> bytes:
    if lane == "bend":
        u = raw + 8192
        return bytes([0xE0 | channel, u & 0x7F, u >> 7])
    return bytes([0xB0 | channel, LANE_CC[lane], raw])


def from_lanes(track: dict, root: dict, tick, channel: int, skipped: list) -> list:
    """The track's controller lanes as MIDI events: the value at the start, then each change (a slope sampled
    every SAMPLE ticks, only where the written number changes). `tick(seconds)` is the writer's clock."""
    out = []
    for lane in REST:
        pts = [(tick(times.seconds(t, root, track["id"])), float(v)) for t, v in LN.points(track, lane)]
        if not pts:
            continue
        if lane == "dynamics" and any(v > 1 for _, v in pts):
            skipped.append(f"{track['id']}: expression above 1 is written as 127 (MIDI's top)")
        vals = [(0, _raw(lane, pts[0][1]))]
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            vals += [(t0 + s, _raw(lane, v0 + (v1 - v0) * s / (t1 - t0))) for s in range(SAMPLE, t1 - t0, SAMPLE)]
            vals.append((t1, _raw(lane, v1)))
        last = None
        for t, raw in vals:
            if raw != last:
                out.append((t, 0, _message(lane, channel, raw)))
                last = raw
    if LN.points(track, "bend"):
        semis = round(float(track.get("bendRange", MIDI_BEND_RANGE)))
        rpn = [(101, 0), (100, 0), (6, semis), (38, 0), (101, 127), (100, 127)]
        out += [(0, -1, bytes([0xB0 | channel, n, v])) for n, v in rpn]
    return out
