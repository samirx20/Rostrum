"""Layering test: the ACE-Step bed under the sampled cue. The bed came out at 96 bpm (bars every 2.5 s, as asked)
but in A minor (not the D minor asked), so it is pitch-shifted +5 semitones with the engine's tempo-keeping
shift, high-passed so it doesn't fight the low strings and tuba, and placed on bar 5 (12.5 s) under the build.

Run (from proofs/sound): ..\\..\\.venv\\Scripts\\python.exe cue\\layer_bed.py <bed.wav> <out.wav>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cue import SCRATCH, build  # noqa: E402
from rsnd import Session, effects as fx  # noqa: E402

bed_wav, out = sys.argv[1], sys.argv[2]
s = Session(bpm=96, seconds=60, sample_rate=48000, cache_dir=SCRATCH / "pcm-cache", reverb_space="hall")
build(s)
bed = s.track("acestep-bed", volume=0.45, reverb=0.1)
bed.sample(bed_wav, at=s.bar(5), duration=s.bar(11), fade_in=1.5, fade_out=1.0)
# Tempo-keeping pitch shift (engine Rate: semitones, "music" = the Signalsmith stretcher); rsnd doesn't expose it yet.
bed.clips[-1]["rate"] = {"from": 1.0, "to": None, "preservePitch": True, "semitones": 5.0, "content": "music"}
bed.effect(fx.eq(("highpass", 180, 0, 0.7), ("highshelf", 4000, 3, 0.7)))
st = s.render(out)
print(json.dumps({"lufs": st["lufs"], "truePeak": st["truePeak"], "tracks": {t["name"]: t["lufs"] for t in st["tracks"]}}))
