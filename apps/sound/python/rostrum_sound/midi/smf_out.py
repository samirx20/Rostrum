"""A Sound document as a Standard MIDI File (format 1, 480 ticks per quarter note): the notes and drum hits of
every track, the tempo map, the time signature, key changes, markers, and sections (as cue points "<name>" at
the start and "<name>/end" at the end, which `song.py` reads back as sections).

    data, skipped = to_bytes(root)            # skipped: what MIDI can't hold (a drum with no GM key), said aloud
    write(root, path)

Times go through the tempo map (doc/tempo.py), so a note in seconds lands on the beat it plays at. Track 1 holds
the song's map; each Sound track with notes or hits is one MIDI track (drum hits on channel 10). Recorded clips,
designed sounds and voice lines are audio, not MIDI: they are not written.
"""
from __future__ import annotations

import struct
from pathlib import Path

from ..doc import keys as K
from ..doc import tempo, times
from .song import DRUM_CHANNEL, DRUM_TO_GM

DIVISION = 480


def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    while n > 0x7F:
        n >>= 7
        out.append(0x80 | (n & 0x7F))
    return bytes(reversed(out))


def _meta(kind: int, data: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(data)) + data


def _chunk(events: list[tuple[int, int, bytes]]) -> bytes:
    """events: (tick, order, raw bytes); at one tick, lower order first (note-offs before note-ons)."""
    body, last = b"", 0
    for tick, _, raw in sorted(events, key=lambda e: (e[0], e[1])):
        body += _vlq(tick - last) + raw
        last = tick
    body += _vlq(0) + _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(body)) + body


def _tick(root, sec: float) -> int:
    return max(0, round(tempo.beat_at(root, sec) * DIVISION))


def _map_track(root) -> list:
    ev = [(0, 0, _meta(0x58, bytes([int(root.get("beatsPerBar", 4)), 2, 24, 8])))]
    for beat, bpm, _ in tempo.segments(root):
        ev.append((round(beat * DIVISION), 0, _meta(0x51, round(60_000_000 / bpm).to_bytes(3, "big"))))
    for k in root.get("keys", []):
        sharps, minor = K.signature(k["key"])
        ev.append((_tick(root, times.seconds(k["at"], root, k["id"])), 1,
                   _meta(0x59, struct.pack("bB", sharps, int(minor)))))
    for m in root.get("markers", []):
        ev.append((_tick(root, times.seconds(m["at"], root, m["id"])), 2,
                   _meta(0x06, m.get("name", m["id"]).encode())))
    for s in root.get("sections", []):
        for key, text in (("at", s["name"]), ("end", f"{s['name']}/end")):
            ev.append((_tick(root, times.seconds(s[key], root, s["id"])), 2, _meta(0x07, text.encode())))
    return ev


def _vel(v) -> int:
    return max(1, min(127, round(float(v) * 127)))


def _track(root, track, channel, skipped) -> list:
    ev = [(0, 0, _meta(0x03, (track.get("name") or track["id"]).encode()))]
    for n in track.get("notes", []):
        start = times.seconds(n["at"], root, n["id"])
        a, b = _tick(root, start), _tick(root, start + times.length_seconds(n["dur"], root, start))
        for k in K.midis(n["pitch"]):
            ev += [(a, 2, bytes([0x90 | channel, k, _vel(n.get("vel", 0.8))])), (max(b, a + 1), 1,
                                                                                bytes([0x80 | channel, k, 0]))]
    for h in track.get("hits", []):
        key = h["drum"] if isinstance(h["drum"], int) else DRUM_TO_GM.get(h["drum"])
        if key is None:
            skipped.append(f"{h['id']}: drum {h['drum']!r} has no General MIDI key")
            continue
        a = _tick(root, times.seconds(h["at"], root, h["id"]))
        ev += [(a, 2, bytes([0x90 | DRUM_CHANNEL, key, _vel(h.get("vel", 0.85))])),
               (a + DIVISION // 8, 1, bytes([0x80 | DRUM_CHANNEL, key, 0]))]
    return ev


def to_bytes(root: dict) -> tuple[bytes, list[str]]:
    skipped, chunks, channel = [], [_chunk(_map_track(root))], 0
    for t in root.get("tracks", []):
        if not (t.get("notes") or t.get("hits")):
            continue
        chunks.append(_chunk(_track(root, t, channel, skipped)))
        if t.get("notes"):
            channel = (channel + 1) % 16
            channel += channel == DRUM_CHANNEL
    head = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), DIVISION)
    return head + b"".join(chunks), skipped


def write(root: dict, path) -> list[str]:
    """Write the .mid (made with a temporary name, then renamed); returns what could not be written."""
    data, skipped = to_bytes(root)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(p)
    return skipped
