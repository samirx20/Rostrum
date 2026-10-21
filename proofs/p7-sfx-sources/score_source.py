"""The P6 slide deck scored with one sound-effect library's recordings, placed the way a careful sound designer
would: each whoosh's loudest moment on the card's fastest moment, panned with the card, louder for faster moves;
a click where a card lands hard; ticks varied in pitch and level; the button's press and release; everything on
the P6 "ui" glue bus. Only the source of the sounds changes between libraries, so Sam hears the source.

    python score_source.py <source> [picks.json] [events.json]

Writes C:\\Users\\Sam\\.rostrum\\waves\\results\\stage2\\sound-sources\\slides-<source>.wav (-16 LUFS).
picks.json: {source: {role: {path, start_s, ...}}}, roles slow_whoosh, flick, snap, tick, press, release?,
exit_whoosh; optional length_s plays only part of a file (the libraries member's picks, plus the lead's
additions in picks-p7.json).
"""
import json
import math
import sys
from pathlib import Path

import librosa
import numpy as np
from rostrum_core import Document, Who
from rostrum_sound import KIND, compile as compile_schedule, run_source
from rostrum_sound.engine import Engine
from rostrum_sound.motion import score

SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-P7-lead")
HERE = Path(__file__).resolve().parent
PICKS = HERE / "picks-p7.json"
EVENTS = HERE / "slides-events.json"              # P6's motion events (proofs/p6-motion-sfx, read.events)
RESULTS = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2\sound-sources")
W = 1920.0
TRACK = {"whoosh": "ui_whoosh", "click": "ui_clicks", "tick": "ui_ticks"}


def peak_s(path: str, start: float) -> float:
    """Seconds from `start` to the take's loudest moment (smoothed over 10 ms)."""
    y, sr = librosa.load(path, sr=48000, mono=True, offset=start, duration=4.0)
    if y.size == 0:
        raise SystemExit(f"{path}: nothing after {start} s")
    env = np.convolve(np.abs(y), np.ones(480) / 480, mode="same")
    return float(np.argmax(env)) / sr


def onset_s(path: str, start: float) -> float:
    """Seconds from `start` to where the take first reaches -30 dB of its peak (its attack)."""
    y, sr = librosa.load(path, sr=48000, mono=True, offset=start, duration=2.0)
    a = np.abs(y)
    return float(np.argmax(a >= a.max() * 10 ** (-30 / 20))) / sr


def pan(x: float) -> float:
    return round(max(-0.9, min(0.9, (x - W / 2) / (W / 2))), 3)


def sounds(evs: list[dict], picks: dict) -> list[tuple[str, dict]]:
    """(track, clip fields) for every event."""
    out = []

    def take(role, at_moment, align="onset", tail=None, **f):
        p = picks.get(role) or (picks.get("press") if role == "release" else None)
        if not p:
            raise SystemExit(f"no take for {role}")
        start = float(p.get("start_s", 0.0))
        lead = (peak_s if align == "peak" else onset_s)(p["path"], start)
        at = at_moment - lead
        if at < 0:                     # the take's build-up is longer than the time before the moment: start later in it
            start, at = start - at, 0.0
        if p.get("length_s"):          # one part of a file that holds two sounds (a press and its release)
            f.update(length=float(p["length_s"]))
        if tail is not None:           # trimmed as a designer would: it dies away `tail` s after the moment
            f.update(length=round(lead + tail, 4), fadeOut=round(min(0.25, tail * 0.6), 3))
        return {"media": p["path"], "at": round(at, 4), "in_": round(start, 4), **f}

    for e in evs:
        k = e["kind"]
        if k == "move":
            dur, entering = e["end"] - e["at"], not e["on_screen"][0]
            role = "flick" if dur < 0.3 or e["peak_speed"] > 15000 else ("slow_whoosh" if entering else "exit_whoosh")
            loud = min(1.0, 0.45 + 0.55 * math.log10(max(e["peak_speed"], 800) / 800) / math.log10(40))
            out.append((TRACK["whoosh"], take(role, e["peak_at"], "peak", tail=e["end"] - e["peak_at"] + 0.35, volume=round(loud, 3),
                                              pan=pan(e["x"][0]), panTo=pan(e["x"][-1]))))
            land = e.get("lands")
            if land and land["hardness"] >= 0.15:
                out.append((TRACK["click"], take("snap", land["at"], volume=round(0.4 + 0.6 * land["hardness"], 3),
                                                 pan=pan(e["x"][-1]))))
        elif k == "snap":
            out.append((TRACK["click"], take("snap", e["at"], volume=0.8)))
        elif k == "step":
            n = int(e["layer"].split("_")[-1])
            out.append((TRACK["tick"], take("tick", e["at"], volume=round(0.55 + 0.08 * (n % 3), 3),
                                            pitch=round(((n * 7) % 5 - 2) * 0.15, 2))))
        elif k == "press":
            out.append((TRACK["click"], take("press", e["at"], volume=0.7)))
            rel = "release" if "release" in picks else "press"
            out.append((TRACK["click"], take(rel, e["release"], volume=0.45, pitch=2.0 if rel == "press" else 0.0)))
    return out


def main() -> None:
    source = sys.argv[1]
    picks = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else PICKS).read_text(encoding="utf-8"))[source]
    evs = json.loads(Path(sys.argv[3] if len(sys.argv) > 3 else EVENTS).read_text(encoding="utf-8"))
    placed = sounds(evs, picks)
    src = ["tempo(120); length(10.5)"]
    names = {t: f"t{i}" for i, t in enumerate(dict.fromkeys(t for t, _ in placed))}
    src += [f"{v} = track({t!r})" for t, v in names.items()]
    for t, f in placed:
        media = f.pop("media")
        src.append(f"{names[t]}.clip(r{media!r}, " + ", ".join(f"{k}={v!r}" for k, v in f.items()) + ")")
    src.append("master(loudness=-16); master.effect('limiter', ceiling=-1)")
    source_text = "\n".join(src)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / f"score-{source}.py").write_text(source_text, encoding="utf-8")

    doc = Document.new(KIND, folder=str(SCRATCH / "sound-doc"), item=f"slides-{source}")
    doc.run_script(f"{source}.py", run_source(source_text, f"{source}.py"), Who.script("score_source.py"))
    doc.apply(score.glue_ops(doc.data, list(names)), Who.script("score_source.py"), label="UI glue bus")
    doc.save()
    wav = RESULTS / f"slides-{source}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    with Engine() as eng:
        r = eng.request("render", schedule=compile_schedule(doc), out=str(wav))
    print(json.dumps({"source": source, "sounds": len(placed), "file": r["file"], "lufs": round(r["lufs"], 1),
                      "truePeak": round(r["truePeak"], 1)}))


if __name__ == "__main__":
    main()
