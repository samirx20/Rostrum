"""P-SFX redo of the 20.4 s door close-up, built FROM THE PICTURE (eyes/door_events.json).

Every cue below is one line of the event sheet: what touches what, how hard. Takes come from the
scored pool (redo.pool + redo.score) through redo.pick; level comes from the force word. Nothing
hits hard in this picture, so there are no low hits, whooshes, creaks or wind.

Run (main venv, from proofs/sound-sfx):
  python -m redo.door_redo <pool_scored.json> <out.wav> [--stems <dir>] [--picks <picks.json>]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sound"))
from rsnd import Session, effects as fx  # noqa: E402

from .pick import Picker  # noqa: E402

SECONDS = 20.4
ROOM = Path.home() / ".rostrum/assets/sounds/foley-h4/freesound/454166_room_tone_medium_quiet_Pablo_s_condo.flac.mp3"
SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\hem-H4-lead")
# force word -> peak level of the cut before mastering (dBFS); "-n" lowers one bounce of a swing
PEAK = {"soft": -20.0, "very soft": -30.0, "touch": -38.0}
TRACK = {"ring_clink": "metal", "padlock": "metal", "metal_touch": "metal",
         "finger_tap": "wood", "palm_pat": "wood", "palm_slide": "cloth", "sleeve": "cloth"}
LEVEL_OFFSET = {"palm_pat": -6, "finger_tap": 0, "palm_slide": -10, "sleeve": -10}

# (time s, kind, force, longest s, extra dB, event # in eyes/door_events.json)
CUES = [
    (0.32, "sleeve", "very soft", 0.30, 0, 2),          # arm enters, sleeve brushes air
    (0.60, "metal_touch", "touch", 0.12, 0, 3),         # fingertips reach the ring
    (0.76, "ring_clink", "very soft", 0.20, -4, 4),     # hand grips: one tiny clink
    (1.32, "padlock", "soft", 0.30, 0, 5),              # let go: padlock knocks the ring
    (1.50, "padlock", "soft", 0.25, -6, 5), (1.64, "padlock", "soft", 0.20, -10, 5),
    (1.76, "padlock", "soft", 0.20, -14, 5),
    (1.44, "sleeve", "soft", 0.36, 0, 6),               # sleeve sweeps across the lens
    (2.70, "sleeve", "very soft", 0.60, -4, 7),         # resting: faint cloth shift
    (4.68, "palm_slide", "soft", 0.28, 0, 8),           # palm slides over the door
    (4.72, "padlock", "soft", 0.25, -2, 9), (4.95, "padlock", "soft", 0.20, -6, 9),
    (5.18, "padlock", "soft", 0.20, -10, 9), (5.38, "padlock", "soft", 0.20, -14, 9),
    (5.12, "finger_tap", "very soft", 0.15, 0, 10),     # fingertip touches the door
    (5.60, "palm_pat", "soft", 0.25, 0, 11),            # palm lands flat
    (5.76, "sleeve", "soft", 0.60, -2, 12), (6.36, "sleeve", "soft", 0.60, -4, 12),
    (6.96, "sleeve", "soft", 0.60, -6, 12),             # forearm pushed across: cloth only
    (7.68, "ring_clink", "soft", 0.25, -2, 13), (7.84, "ring_clink", "soft", 0.20, -8, 13),
    (7.92, "metal_touch", "touch", 0.12, 0, 14),        # second hand takes the ring
    (8.60, "ring_clink", "very soft", 0.15, -6, 14),    # a faint ring shift while held
    (9.32, "padlock", "soft", 0.25, 0, 15), (9.40, "ring_clink", "soft", 0.20, -4, 15),
    (9.48, "palm_pat", "soft", 0.25, 0, 16),            # second palm lands
    (9.62, "padlock", "very soft", 0.15, 0, 17), (9.78, "ring_clink", "very soft", 0.15, -3, 17),
    (9.92, "padlock", "very soft", 0.15, -2, 17), (10.04, "metal_touch", "touch", 0.12, 2, 17),
    (10.16, "palm_pat", "very soft", 0.20, -4, 18),     # left palm settles
    (10.72, "padlock", "soft", 0.25, -3, 19), (10.95, "padlock", "soft", 0.20, -9, 19),
    (12.40, "padlock", "very soft", 0.12, -6, 20), (13.60, "padlock", "very soft", 0.12, -8, 20),
    (14.92, "palm_slide", "soft", 0.16, 0, 21),         # hand sweeps in over the plate
    (15.12, "sleeve", "soft", 0.60, 0, 22), (15.62, "sleeve", "soft", 0.50, -3, 22),
    (15.50, "padlock", "very soft", 0.15, -2, 22), (15.85, "padlock", "very soft", 0.15, -4, 22),
    (16.12, "ring_clink", "soft", 0.25, 0, 23), (16.22, "padlock", "soft", 0.20, -4, 23),
    (16.34, "ring_clink", "soft", 0.20, -7, 23),
    (16.50, "padlock", "very soft", 0.15, 0, 24), (16.70, "padlock", "very soft", 0.15, -4, 24),
    (16.92, "metal_touch", "touch", 0.10, 0, 25), (16.96, "padlock", "soft", 0.20, -4, 25),
    (17.12, "padlock", "soft", 0.20, -8, 26), (17.30, "ring_clink", "soft", 0.15, -11, 26),
    (17.45, "padlock", "soft", 0.15, -14, 26), (17.58, "padlock", "soft", 0.12, -18, 26),
]
HITS = {"ring_clink", "padlock", "finger_tap", "palm_pat"}  # cues with a sharp start, checked for sync


def build(s, pool):
    room = s.track("room", volume=0.12)  # the room under everything, ~20 dB below the cloth
    # the room recording, 18.2 s, carried to 20.4 s by a second piece under a 1 s crossfade
    room.sample(ROOM, at=0.0, length=18.2, fade_in=0.3, fade_out=1.0)
    room.sample(ROOM, at=17.2, offset=2.0, length=3.2, fade_in=1.0, fade_out=0.4)
    room.effect(fx.eq(("highpass", 160, 0, 0.7)))  # the recording hums at 100-150 Hz (seen on the spectrogram)
    tracks = {n: s.track(n, volume=1.0, pan=p, reverb=0.02) for n, p in (("cloth", -0.1), ("wood", 0.1), ("metal", -0.05))}
    picker, picks = Picker(pool), []
    for at, kind, force, longest, extra, ev in sorted(CUES):
        c = picker.pick(kind, min(longest, 0.05) if kind in HITS or kind == "metal_touch" else longest, at)
        length = min(c["length"], longest)
        db = PEAK[force] + LEVEL_OFFSET.get(kind, 0) + extra
        gain = 10 ** ((db - c["peak_db"]) / 20)
        # the cut starts 5 ms before its transient: start it 5 ms early so the hit lands on the frame
        start = max(0.0, at - 0.005) if kind in HITS else at
        tracks[TRACK[kind]].sample(c["path"], at=start, offset=c["offset"], length=length, volume=gain,
                                   fade_in=0.0 if kind in HITS else min(0.08, length / 3),
                                   fade_out=min(0.05, length / 3) if kind in HITS else min(0.15, length / 3))
        picks.append({"at": at, "kind": kind, "force": force, "event": ev, "peak_db_set": round(db, 1),
                      **{k: c[k] for k in ("label", "path", "offset", "length", "prob", "cosine", "heard_as",
                                           "centroid_hz", "attack_ms", "licence", "author", "source_url")},
                      "used_s": round(length, 3)})
    tracks["cloth"].effect(fx.eq(("highpass", 180, 0, 0.7)))  # handling rumble under the sleeve cuts
    tracks["metal"].effect(fx.eq(("highpass", 250, 0, 0.7)))
    tracks["wood"].effect(fx.eq(("highpass", 120, 0, 0.7)))  # a soft palm, not a thump: v2 put 86% of the sub here
    s.master(lufs=None, true_peak=-1.0)
    return picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pool")
    ap.add_argument("out")
    ap.add_argument("--stems")
    ap.add_argument("--picks")
    ap.add_argument("--gain-db", type=float, default=16.5, help="whole-mix gain before the limiter")
    a = ap.parse_args()
    pool = json.loads(Path(a.pool).read_text(encoding="utf-8"))
    s = Session(bpm=60, seconds=SECONDS, sample_rate=48000, cache_dir=SCRATCH / "pcm-cache", reverb_space="room",
                volume=10 ** (a.gain_db / 20))
    picks = build(s, pool)
    st = s.render(a.out)
    if a.picks:
        Path(a.picks).write_text(json.dumps(picks, indent=1), encoding="utf-8")
    hits = sorted(p["at"] for p in picks if p["kind"] in HITS)
    print(json.dumps({"lufs": st["lufs"], "truePeak": st["truePeak"], "lra": st["lra"], "cues": len(picks),
                      "hit_times": ",".join(f"{t:g}" for t in hits),
                      "tracks": {t["name"]: t["lufs"] for t in st["tracks"]}}))
    if a.stems:
        s.render_stems(a.stems)


if __name__ == "__main__":
    main()
