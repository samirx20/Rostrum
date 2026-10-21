"""P-SND effects pass: 20.4 s of a hand trying a padlocked wooden door (Mixkit clip, private), every sound a
recorded take from the CC0 libraries, placed on the on-screen events (proofs/sound/LIBRARIES.md section 4.1).

Layers: room bed / hands and cloth / wood / iron ring and padlock / low weight under the big moments / tail.
Run (from proofs/sound): ..\\..\\.venv\\Scripts\\python.exe sfx\\door_pass.py <out.wav> [--stems <dir>]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rsnd import Library, Session, effects as fx  # noqa: E402

FS = Path.home() / ".rostrum" / "assets" / "sounds" / "freesound"
SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\sfx")
SECONDS = 20.4
# The events the picture shows (seconds), used for the timing check after the render.
EVENTS = [1.05, 2.0, 4.6, 5.6, 7.6, 9.35, 10.1, 10.8, 15.0, 16.0]


def build(s: Session, lib: Library):
    def put(track, name, at, n=0, **kw):
        track.sample(at=at, **lib.take(name, n), **kw)

    # --- the room: a quiet bed under everything, wind outside the door -------------------------
    room = s.track("room", volume=1.0)
    room.sample(**lib.take("ambience.room-tone-office", 0), at=0.0, duration=SECONDS, fade_in=0.5, fade_out=1.0)
    room.sample(FS.parent / "bigsoundbank" / "0146.ogg", at=0.0, duration=SECONDS, volume=0.12, fade_in=1.0, fade_out=1.5)
    # highpass 140: the room recording carries a steady 50-150 Hz hum (seen on the spectrogram)
    room.effect(fx.eq(("highpass", 140, 0, 0.7), ("highshelf", 6000, -4, 0.7)))

    # --- hands and sleeve ---------------------------------------------------------------------
    cloth = s.track("cloth", volume=3.0, pan=-0.2, reverb=0.05)
    put(cloth, "whoosh.cloth", 0.30, 0, volume=0.7)                 # arm enters
    put(cloth, "cloth.blanket", 2.4, 5, volume=0.35, fade_out=0.3)  # palm held, sleeve settles
    put(cloth, "whoosh.cloth", 4.9, 1, volume=0.6)                  # into the push
    put(cloth, "cloth.blanket", 6.0, 1, volume=0.3, fade_in=0.2, fade_out=0.4, duration=1.6)
    put(cloth, "whoosh.cloth", 7.45, 2, volume=0.75)                # sweep past the ring
    put(cloth, "whoosh.cloth", 9.15, 3, volume=0.6)
    put(cloth, "whoosh.cloth", 14.8, 5, volume=0.8)                 # swipe across the door
    put(cloth, "whoosh.cloth", 15.75, 4, volume=0.6)
    put(cloth, "whoosh.cloth", 16.45, 0, volume=0.45, fade_out=0.3)  # arm withdraws
    cloth.effect(fx.eq(("highpass", 150, 0, 0.7)))

    # --- the door: palms, the push, the timber groaning ----------------------------------------
    wood = s.track("wood", volume=0.9, pan=0.1, reverb=0.12)
    put(wood, "impact.wood-light", 2.0, 1, volume=0.8)              # palm lands
    put(wood, "impact.slap", 2.02, 0, volume=0.25)
    wood.sample(**lib.take("tech.creaking-door"), at=2.7, pitch=-5, volume=0.35, fade_in=0.4, fade_out=0.6)
    put(wood, "impact.wood-heavy", 5.6, 2, volume=0.9, pitch=-3)   # the hard push: the door flexes
    wood.sample(**lib.take("tech.creaking-door"), at=5.1, pitch=-2, volume=0.5, fade_in=0.2, fade_out=0.5)
    put(wood, "impact.slap", 9.35, 0, volume=0.8)                  # palm slap beside the ring
    put(wood, "impact.wood-medium", 9.35, 1, volume=0.7)
    put(wood, "impact.wood-light", 10.1, 3, volume=0.6)            # second palm
    wood.sample(**lib.take("tech.creaking-door"), at=11.8, pitch=-7, volume=0.4, fade_in=0.5, fade_out=0.8, duration=2.2)
    put(wood, "impact.scrape", 14.969, 1, volume=0.45)             # palm swipe (onset measured +31 ms late at 15.0)
    wood.effect(fx.eq(("peak", 300, -2, 1.0), ("peak", 2500, 2, 1.0)))

    # --- the iron ring and the brass padlock --------------------------------------------------
    metal = s.track("metal", volume=0.8, pan=0.15, reverb=0.25)
    put(metal, "impact.metal-light", 1.05, 0, volume=0.7)          # hand takes the ring
    metal.sample(**lib.take("impact.clamour", 3), at=1.2, volume=0.55, duration=0.75, fade_out=0.2)  # yanked, rattling
    for i, t in enumerate((1.35, 1.55, 1.78)):
        put(metal, "impact.tin-medium", t, i, volume=0.45 - 0.08 * i)
    put(metal, "impact.metal-light", 4.6, 3, volume=0.55)          # the ring swings as the hand leaves
    metal.sample(**lib.take("impact.clamour", 4), at=7.556, volume=0.5, duration=0.5, fade_out=0.15)  # brushed (onset measured +44 ms late at 7.6)
    put(metal, "impact.scrape", 8.35, 2, volume=0.4)               # ring scraped against the plate
    put(metal, "impact.metal-light", 9.45, 4, volume=0.5)
    put(metal, "impact.tin-medium", 10.8, 3, volume=0.5)           # padlock swings out
    put(metal, "impact.tin-medium", 11.15, 4, volume=0.3)
    for i, t in enumerate((12.3, 13.1)):
        put(metal, "impact.metal-light", t, i + 1, volume=0.22)
    put(metal, "impact.metal-heavy", 16.0, 1, volume=0.95)         # the clank
    put(metal, "impact.plate-heavy", 16.0, 0, volume=0.5, pitch=-4)
    for i, t in enumerate((16.45, 16.75, 17.1, 17.5)):
        put(metal, "impact.tin-medium", t, i, volume=0.35 * 0.75 ** i)  # swinging, settling
    put(metal, "impact.metal-light", 18.3, 2, volume=0.12)         # last creaks of the ring
    put(metal, "impact.metal-light", 19.5, 4, volume=0.08)
    metal.effect(fx.eq(("highpass", 200, 0, 0.7)))

    # --- weight: low hits only under the moments that matter, a held tone in the empty frame --------
    low = s.track("low", volume=0.38, reverb=0.2)
    low.sample(FS / "408141.ogg", at=5.58, volume=0.25, duration=2.0, fade_out=1.2)  # under the push
    low.sample(FS / "408141.ogg", at=9.33, volume=0.3, duration=2.0, fade_out=1.2)   # under the slap
    low.sample(FS / "430977.ogg", at=15.98, volume=0.5, fade_out=2.5)                # under the clank
    low.sample(FS / "203119.ogg", at=16.4, volume=0.35, duration=4.0, fade_in=1.2, fade_out=1.0)  # held in the empty frame
    low.effect(fx.eq(("lowpass", 2500, 0, 0.7)))

    s.master(lufs=-20, true_peak=-1.0, glue=0.1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--stems")
    a = ap.parse_args()
    s = Session(bpm=60, seconds=SECONDS, sample_rate=48000, cache_dir=SCRATCH / "pcm-cache", reverb_space="room")
    build(s, Library())
    st = s.render(a.out)
    print(json.dumps({"lufs": st["lufs"], "truePeak": st["truePeak"], "lra": st["lra"], "events": EVENTS,
                      "tracks": {t["name"]: t["lufs"] for t in st["tracks"]}}))
    if a.stems:
        s.render_stems(a.stems)


if __name__ == "__main__":
    main()
