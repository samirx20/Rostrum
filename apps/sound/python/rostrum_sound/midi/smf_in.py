"""Reading a Standard MIDI File (format 0 or 1, ticks per quarter note) into plain events. Ours, from the public
SMF 1.0 layout: chunks, variable-length numbers, running status, meta and sysex events.

    division, tracks = read_events(path)      # tracks: [[(tick, kind, data), …], …], ticks from the track start
    kinds: on (channel, key, velocity 1 … 127) · off (channel, key) · program (channel, number) · tempo (µs per
           quarter) · timesig (numerator, denominator) · key (sharps -7 … 7, minor) · marker / cue / name (text)

A broken file is a loud BAD_ARGUMENT naming the file and the byte where it broke; nothing half-read is returned.
"""
from __future__ import annotations

import struct
from pathlib import Path

from rostrum_core import RostrumError, codes

TEXT_META = {0x03: "name", 0x06: "marker", 0x07: "cue"}


class _Bad(Exception):
    pass


def _vlq(b: bytes, i: int) -> tuple[int, int]:
    n = 0
    for _ in range(4):
        if i >= len(b):
            raise _Bad("the file ends inside a number")
        c = b[i]
        i += 1
        n = (n << 7) | (c & 0x7F)
        if not c & 0x80:
            return n, i
    raise _Bad("a number is longer than 4 bytes")


def _text(data: bytes) -> str:
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError:
        return data.decode("latin-1").strip()


def _meta(kind: int, data: bytes):
    if kind in TEXT_META:
        return TEXT_META[kind], _text(data)
    if kind == 0x51 and len(data) == 3:
        return "tempo", int.from_bytes(data, "big")
    if kind == 0x58 and len(data) >= 2:
        return "timesig", (data[0], 2 ** data[1])
    if kind == 0x59 and len(data) == 2:
        return "key", (struct.unpack("b", data[:1])[0], bool(data[1]))
    return None


def _track(b: bytes) -> list[tuple[int, str, object]]:
    out, i, tick, status = [], 0, 0, 0
    while i < len(b):
        dt, i = _vlq(b, i)
        tick += dt
        if i >= len(b):
            raise _Bad("the track ends after a time")
        if b[i] & 0x80:
            status, i = b[i], i + 1
        elif not status:
            raise _Bad("data byte with no status before it")
        if status == 0xFF:
            kind = b[i]
            n, i = _vlq(b, i + 1)
            ev = _meta(kind, b[i:i + n])
            i += n
            if kind == 0x2F:
                break
            if ev:
                out.append((tick, *ev))
            status = 0                      # meta and sysex cancel running status
            continue
        if status in (0xF0, 0xF7):
            n, i = _vlq(b, i)
            i, status = i + n, 0
            continue
        high, ch = status & 0xF0, status & 0x0F
        size = 1 if high in (0xC0, 0xD0) else 2
        if i + size > len(b):
            raise _Bad("the track ends inside an event")
        d = b[i:i + size]
        i += size
        if high == 0x90 and d[1] > 0:
            out.append((tick, "on", (ch, d[0], d[1])))
        elif high in (0x80, 0x90):
            out.append((tick, "off", (ch, d[0])))
        elif high == 0xC0:
            out.append((tick, "program", (ch, d[0])))
    return out


def parse(b: bytes, where: str = "MIDI file") -> tuple[int, list[list]]:
    """(ticks per quarter note, the tracks' events) from a file's bytes."""
    try:
        if b[:4] != b"MThd" or len(b) < 14:
            raise _Bad("is not a Standard MIDI File (no MThd header)")
        hlen = struct.unpack(">I", b[4:8])[0]
        fmt, ntracks, division = struct.unpack(">HHh", b[8:14])
        if fmt not in (0, 1):
            raise _Bad(f"is format {fmt} (only 0 and 1 are read: one song)")
        if division <= 0:
            raise _Bad("counts time in SMPTE frames (only ticks per quarter note are read)")
        i, tracks = 8 + hlen, []
        while i + 8 <= len(b) and len(tracks) < ntracks:
            tag, n = b[i:i + 4], struct.unpack(">I", b[i + 4:i + 8])[0]
            if tag == b"MTrk":
                tracks.append(_track(b[i + 8:i + 8 + n]))
            i += 8 + n
        if len(tracks) < ntracks:
            raise _Bad(f"says {ntracks} tracks but holds {len(tracks)}")
        return division, tracks
    except _Bad as e:
        raise RostrumError(codes.BAD_ARGUMENT, "import MIDI", where, str(e)) from None


def read_events(path) -> tuple[int, list[list]]:
    p = Path(path)
    if not p.is_file():
        raise RostrumError(codes.NOT_FOUND, "import MIDI", str(p), "is not a file")
    return parse(p.read_bytes(), str(p))
