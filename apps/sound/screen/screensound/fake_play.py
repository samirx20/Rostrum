"""TEST SEAM, never used to play or record for real: speaks the lines of the engine's live transport
(`rostrum-sound play`, ENGINE_CONTRACT.md § play) on a clock, without a sound device, so the screen's playback,
microphone takes and keyboard takes can be checked without speakers, a microphone or a keyboard.

    python fake_play.py [--fake-source take.wav] [--fake-notes <note list | file.mid>] [--fake-delay s]
                        <mix.wav> [--mic dir] [--midi n] [--bpm b] [--beats n] [--from t] [...]

A microphone take is the source WAV's first seconds, its `start` the mix time it began at minus `--fake-delay` (the
calibrated microphone delay the engine takes off). Notes ("60@0.2:0.45,64,…" or a MIDI file) are played from the
moment the mix rolls, reported in mix seconds while recording is armed. Input level every 100 ms with --mic. The
strips' levels are the render's own (`<mix>.levels.json`, written by the engine beside the mix), ~30 lines a second
while it plays and `{"levels": null}` at the stop, as the engine says them; without that file, one error line.
"""
import json
import queue
import sys
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

VALUED = {"--mic", "--midi", "--instrument", "--bpm", "--beats", "--beat-times", "--from", "--count-in",
          "--fake-source", "--fake-notes", "--fake-delay", "--monitor", "--master"}


def say(**kw):
    print(json.dumps(kw), flush=True)


def parse(argv):
    opts, pos, i = {}, [], 0
    while i < len(argv):
        a = argv[i]
        if a in VALUED:
            opts[a], i = argv[i + 1], i + 2
        else:
            (opts.__setitem__(a, True) if a.startswith("--") else pos.append(a))
            i += 1
    return opts, pos


def notes_of(text):
    if text.lower().endswith((".mid", ".midi")):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
        from rostrum_sound.midi.smf_in import read_events
        division, tracks = read_events(text)
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
    notes = []
    for i, tok in enumerate(t for t in text.split(",") if t.strip()):
        key, _, span = tok.strip().partition("@")
        start, _, end = span.partition(":")
        s = float(start) if start else 0.2 + 0.5 * i
        notes.append({"key": int(key), "velocity": 0.8, "start": s, "end": float(end) if end else s + 0.4})
    return notes


def levels_of(mix):
    """The engine's levels beside the mix ({hop, strips: {id: [peak, rms] per window}}), or None (said, like the engine)."""
    p = Path(mix).with_suffix(".levels.json")
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        say(error=f"meters: no levels for this mix, the Mixer's meters stay still ({p}: {e})")
        return None
    strips = {k: [(w[i] / 10, w[i + 1] / 10) for i in range(0, len(w) - 1, 2)] for k, w in v["strips"].items()}
    return {"hop": v["hop"], "strips": strips}


def levels_line(lv, a, b):
    i, j = int(max(a, 0) / lv["hop"]), int(max(b, 0) / lv["hop"])
    i = min(i, j)
    out = {}
    for k, w in lv["strips"].items():
        part = w[i:j + 1]
        out[k] = [max((p[0] for p in part), default=-120.0), max((p[1] for p in part), default=-120.0)]
    return {"t": round(b, 3), "strips": out}


class Fake:
    def __init__(self, opts, mix):
        self.o, self.length = opts, sf.info(mix).duration
        self.levels = levels_of(mix)
        self.pos, self.playing, self.count, self.armed, self.bars = float(opts.get("--from", 0)), False, 0.0, None, 0
        self.beat = 60.0 / float(opts.get("--bpm", 120)) * int(opts.get("--beats", 4))     # a bar, in seconds
        self.take, self.taken, self.rolled_at, self.notes = None, 0, None, []
        self.source = opts.get("--fake-source")
        self.all_notes = notes_of(opts["--fake-notes"]) if "--fake-notes" in opts else []

    def command(self, m):
        if m.get("quit"):
            return False
        if "play" in m:
            self.finish()
            self.pos = float(m["play"]["from"]) if isinstance(m["play"], dict) else self.pos
            self.count, self.playing = self.bars * self.beat, True
            if not self.count:
                self.roll()
        elif m.get("stop"):
            self.finish()
            self.release()
            self.playing, self.count = False, 0.0
        elif "seek" in m:
            self.finish()
            self.pos = float(m["seek"])
        elif "countIn" in m:
            self.bars = int(m["countIn"])
        elif "record" in m:
            r = m["record"]
            if not r:
                self.finish()
                self.release()
            self.armed = None if not r else (tuple(r["punch"]) if isinstance(r, dict) else (-1e9, 1e9))
        elif "load" in m:
            if not Path(m["load"]).is_file():
                say(error=f"{m['load']}: not found")
            else:
                self.length = sf.info(m["load"]).duration
                self.levels = levels_of(m["load"])
        elif "hear" in m or "metronome" in m:
            pass
        else:
            say(error=f"unknown command {json.dumps(m)}")
        return True

    def roll(self):
        self.rolled_at, self.notes = self.pos, sorted(self.all_notes, key=lambda n: n["end"])
        say(rolling=self.pos)

    def step(self, dt):
        if not self.playing:
            return
        if self.count > 0:
            self.count -= dt
            if self.count <= 0:
                self.roll()
            return
        a, self.pos = self.pos, self.pos + dt
        if self.armed and "--mic" in self.o:
            lo, hi = self.armed
            if self.take is None and lo <= self.pos < hi:
                self.take = max(a, lo)
            if self.take is not None and self.pos >= hi:
                self.finish(hi)
        while self.notes and self.rolled_at + self.notes[0]["end"] <= self.pos:
            self.say_note(self.notes.pop(0), None)
        if self.pos >= self.length:
            self.pos, self.playing = self.length, False
            self.finish()
            say(end=self.length)

    def say_note(self, n, end):
        s, e = self.rolled_at + n["start"], self.rolled_at + n["end"] if end is None else end
        if self.armed and self.armed[0] <= s < self.armed[1]:
            say(note={"key": n["key"], "velocity": n["velocity"], "start": s, "end": min(e, self.armed[1])})

    def release(self):
        for n in self.notes:
            if self.rolled_at is not None and self.rolled_at + n["start"] <= self.pos:
                self.say_note(n, self.pos)
        self.notes = []

    def finish(self, end=None):
        if self.take is None:
            return
        start, end = self.take, end if end is not None else self.pos
        self.take = None
        if end - start < 1e-3:
            return
        data, rate = sf.read(self.source, dtype="float32") if self.source else (np.zeros(480000, "float32"), 48000)
        out = Path(self.o["--mic"]) / f"take-fake-{self.taken}.wav"
        self.taken += 1
        sf.write(out, data[: int((end - start) * rate)], rate)
        say(take={"file": str(out), "start": start - float(self.o.get("--fake-delay", 0)), "seconds": end - start,
                  "rate": rate, "peakDb": round(20 * np.log10(max(float(np.abs(data).max()), 1e-6)), 1)})


def main(argv):
    opts, pos = parse(argv)
    try:
        f = Fake(opts, pos[0])
    except Exception as e:  # noqa: BLE001  like the engine: one line on stderr, exit 1
        print(f"rostrum-sound: {e}", file=sys.stderr)
        sys.exit(1)
    lines: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: ([lines.put(x) for x in sys.stdin], lines.put(None)), daemon=True).start()
    mic = {"rate": 48000, "device": "Fake microphone", "inputOffsetMs": float(opts.get("--fake-delay", 0)) * 1000} \
        if "--mic" in opts else None
    say(ready={"mode": "fake", "rate": 48000, "device": "fake", "seconds": f.length, "mic": mic})
    last, shown, said, level, going = time.monotonic(), None, 0.0, 0.0, True
    metered, meter_at = None, 0.0
    while going:
        try:
            while True:
                line = lines.get_nowait()
                if line is None or (line.strip() and not f.command(json.loads(line))):
                    going = False
                    break
        except queue.Empty:
            pass
        now = time.monotonic()
        f.step(now - last)
        last = now
        t = round(f.pos, 3) if f.playing and f.count <= 0 else None
        if t != shown and now - said >= 0.05:
            say(pos={"t": t, "playing": t is not None})
            shown, said = t, now
        if f.levels and t is not None and now - meter_at >= 0.033:
            a = metered if metered is not None and metered <= t < metered + 0.25 else t
            say(levels=levels_line(f.levels, a, t))
            metered, meter_at = t, now
        elif f.levels and t is None and metered is not None:
            say(levels=None)
            metered = None
        if mic and now - level >= 0.1:
            level = now
            say(input={"peakDb": -23.0})
        time.sleep(0.01)
    f.finish()
    say(done={"takes": f.taken})


if __name__ == "__main__":
    main(sys.argv[1:])
