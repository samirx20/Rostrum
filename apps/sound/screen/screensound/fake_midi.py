"""TEST SEAM, never used for real recording: speaks the engine's `live --midi` lines ({"ready"}, then a {"note"} per
finished note, seconds since the stream started; ends on {"quit": true} or the end of stdin, releasing keys still
down) from a note list or a MIDI file instead of a keyboard, so keyboard takes can be checked without one.

    python fake_midi.py <file.mid | note list>
    note list: comma-separated keys, played half a second apart from 0.2 s, each 0.4 s long ("60,64,67"), or
               key@start:end in seconds ("60@0.5:0.9,64@1:1.5"). A MIDI file plays at its first tempo.
"""
import json
import sys
import threading
import time
from pathlib import Path


def say(**kw):
    print(json.dumps(kw), flush=True)


def from_list(text):
    notes = []
    for i, tok in enumerate(t for t in text.split(",") if t.strip()):
        key, _, span = tok.strip().partition("@")
        start, _, end = span.partition(":")
        s = float(start) if start else 0.2 + 0.5 * i
        notes.append({"key": int(key), "velocity": 0.8, "start": s, "end": float(end) if end else s + 0.4})
    return notes


def from_file(path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
    from rostrum_sound.midi.smf_in import read_events
    division, tracks = read_events(path)
    events = sorted(e for tr in tracks for e in tr)
    us = next((d for _, k, d in events if k == "tempo"), 500000)
    sec, down, notes = (lambda tick: tick / division * us / 1e6), {}, []
    for tick, kind, data in events:
        if kind == "on":
            down[data[1]] = (sec(tick), data[2] / 127)
        elif kind == "off" and data[1] in down:
            s, v = down.pop(data[1])
            notes.append({"key": data[1], "velocity": round(v, 3), "start": s, "end": sec(tick)})
    return notes


def main(source):
    notes = from_file(source) if source.lower().endswith((".mid", ".midi")) else from_list(source)
    stop = threading.Event()

    def listen():
        for line in sys.stdin:
            if '"quit"' in line:
                break
        stop.set()

    threading.Thread(target=listen, daemon=True).start()
    say(ready={"mode": "fake", "rate": 48000, "device": "fake", "midi": 0, "midiDevices": ["Fake keyboard (test)"]})
    t0, left = time.monotonic(), sorted(notes, key=lambda n: n["end"])
    while left and not stop.is_set():
        now = time.monotonic() - t0
        while left and left[0]["end"] <= now:
            say(note=left.pop(0))
        time.sleep(0.01)
    now = time.monotonic() - t0
    for n in left:                                   # keys still down at the end are released now
        if n["start"] <= now:
            say(note={**n, "end": now})
    stop.wait()


if __name__ == "__main__":
    main(sys.argv[1])
