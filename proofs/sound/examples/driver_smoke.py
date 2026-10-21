"""Smoke test for the rsnd driver: strings chord, piano line, a recorded hit, drums -> one WAV + stats.

Run: .venv\\Scripts\\python.exe proofs\\sound\\examples\\driver_smoke.py [out.wav]
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rsnd import Session, effects  # noqa: E402

LIB = Path(r"C:\Users\Sam\.rostrum\assets\sounds")
SCRATCH = Path(r"C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\driver")
out = Path(sys.argv[1]) if len(sys.argv) > 1 else SCRATCH / "smoke.wav"

s = Session(bpm=84, seconds=10, sample_rate=48000, cache_dir=SCRATCH / "pcm-cache", reverb_space="hall")

strings = s.track("strings", sfz=LIB / "vsco2-strings" / "ViolinEnsSusVib.sfz", volume=0.8, pan=-0.2, reverb=0.35)
strings.chord(["D4", "A4", "F5"], at=0.0, dur=s.beat(8), vel=0.6)
strings.chord(["Bb3", "F4", "D5"], at=s.beat(8), dur=s.beat(6), vel=0.7)
strings.volume_automation([(0, 0.4), (4, 1.0), (9, 0.8)])

piano = s.track("piano", sfz=LIB / "salamander-piano" / "SalamanderGrandPianoV3_44.1khz16bit" / "SalamanderGrandPianoV3.sfz",
                volume=0.9, pan=0.15, reverb=0.2)
for i, n in enumerate(["D5", "E5", "F5", "A5", "G5", "F5", "E5", "D5", "C5", "D5"]):
    piano.note(n, at=s.beat(i * 1.5), dur=s.beat(1.4), vel=0.55 + 0.03 * (i % 3))
piano.effect(effects.eq(("highpass", 80, 0, 0.7), ("peak", 2500, 1.5, 1.0)))

fx = s.track("fx", volume=0.7, reverb=0.3)
fx.sample(LIB / "kenney-impact" / "Audio" / "impactBell_heavy_000.ogg", at=s.beat(8), volume=0.8, fade_out=0.05)

kit = LIB / "muldjord-kit" / "MuldjordKit SFZ+FLAC-20201018" / "rostrum-gm.sfz"
drums = s.track("drums", kit=kit, volume=0.8)
for b in range(0, 13, 2):
    drums.drum("kick", at=s.beat(b), vel=0.9)
for b in range(1, 13, 2):
    drums.drum("snare", at=s.beat(b), vel=0.7)
drums.effect(effects.compressor(threshold=-20, ratio=3))

synth_kit = s.track("synthkit", kit="synth", volume=0.5)
synth_kit.drum("hat", at=s.beat(0.5), vel=0.6).drum("openHat", at=s.beat(4.5), vel=0.5)

s.master(lufs=-16, true_peak=-1.0, glue=0.2)
stats = s.render(out)

print(f"wrote {out}")
print(f"LUFS {stats['lufs']:.2f}   true peak {stats['truePeak']:.2f} dBTP   render {stats['renderSeconds']:.2f} s")
for t in stats["tracks"]:
    print(f"  {t['name']:<9} peak {t['peak']:.3f}  rms {t['rms']:.4f}  lufs {t['lufs']}")

audio, sr = sf.read(str(out), dtype="float32", always_2d=True)
peak = float(np.max(np.abs(audio)))
names = {t["name"] for t in stats["tracks"]}
missing = {t.name for t in s.tracks} - names
silent = [t["name"] for t in stats["tracks"] if not t["peak"] or t["peak"] <= 1e-4]
print(f"file: {audio.shape[0] / sr:.2f} s, {audio.shape[1]} ch, {sr} Hz, numpy peak {peak:.3f}")
if peak <= 1e-3 or missing or silent:
    sys.exit(f"FAILED: peak {peak}, tracks missing from stats {missing}, silent tracks {silent}")
print("OK: non-silent, every track in the stats and audible")
