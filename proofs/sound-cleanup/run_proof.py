"""P9 cleanup proof: a noisy, roomy voice take cleaned; a voice-over pulled out of its music; the P4 expressive cue
split into stems and checked against the real instrument groups. Everything goes through the app's own path: a Sound
document, clip fields, rostrum_sound.clean_clips.make_clips (cache), compile, and the look_cleanup measurements.

    <venv>\\Scripts\\python.exe run_proof.py <results folder>      (the lead runs it under heavy.ps1 gpu)
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import fftconvolve, lfilter

from rostrum_core import Document, Who
from rostrum_sound import KIND, clean_clips, compile as compile_doc
from rostrum_sound.cleanup import audio
from rostrum_sound.engine import Engine
from rostrum_sound.listen import cleanup as look

OUT = Path(sys.argv[1])
STAGE2 = Path(r"C:\Users\Sam\.rostrum\waves\results\stage2")
VO = STAGE2 / "sound-voice" / "voice-over-on-cue.stems" / "vo.wav"
VO_ON_CUE = STAGE2 / "sound-voice" / "voice-over-on-cue.wav"
CUE_SCRIPT = Path(__file__).resolve().parents[1] / "sound" / "cue" / "cue_expressive.py"
RATE = 48000
rng = np.random.default_rng(9)
facts = {}


def made(doc, ids, label):
    t = time.perf_counter()
    r = clean_clips.make_clips(doc, ids, progress=lambda n: print("  ", n, flush=True))
    facts[label] = {"seconds": round(time.perf_counter() - t, 1),        # cold numbers: measure.py
                    "steps": [s["step"] for s in r[0]["steps"]] if r else []}
    print(label, facts[label], flush=True)
    return r


def room(dry, rt60=0.8, wet=0.7):
    """A room of our own: exponentially decaying noise (RT60), early reflections, mixed under the dry voice."""
    n = int(rt60 * 1.5 * RATE)
    t = np.arange(n) / RATE
    ir = rng.standard_normal(n) * np.exp(-6.91 * t / rt60)
    ir[: int(0.004 * RATE)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    return dry + wet * fftconvolve(dry, ir)[: len(dry)]


def room_noise(n, level):
    """Pink-ish noise (air, traffic), 50 Hz hum with harmonics, a low fan: steady, as a real room's."""
    pink = lfilter([0.049922, -0.095993, 0.050612, -0.004408], [1, -2.494956, 2.017265, -0.522189], rng.standard_normal(n))
    t = np.arange(n) / RATE
    hum = sum(np.sin(2 * np.pi * 50 * k * t) / k for k in (1, 2, 3, 5))
    fan = lfilter([1], [1, -0.995], rng.standard_normal(n)) * 0.02
    x = pink / pink.std() + 0.3 * hum + fan / fan.std() * 0.5
    return x / x.std() * level


def one_clip_doc(media, **fields):
    doc = Document.new(KIND)
    doc.apply([{"op": "track.add", "args": {"id": "dlg"}},
               {"op": "clip.add", "target": ["dlg"], "args": {"id": "dlg.take", "media": str(media), "at": 0}},
               {"op": "clip.set", "target": ["dlg.take"], "args": fields}], Who.agent("proof"))
    return doc


def voice_take():
    x, _ = audio.read(VO, RATE)
    v = x[0, : 25 * RATE].astype(np.float64)
    speech_rms = np.sqrt(np.mean(v[np.abs(v) > 0.01 * np.abs(v).max()] ** 2))
    noisy = room(v) + room_noise(len(v), speech_rms / 10 ** (12 / 20))      # noise 12 dB under the speech
    noisy *= 0.5 / np.abs(noisy).max()
    sf.write(OUT / "voice-original.wav", v, RATE, subtype="FLOAT")
    sf.write(OUT / "voice-noisy-roomy.wav", noisy, RATE, subtype="FLOAT")
    doc = one_clip_doc(OUT / "voice-noisy-roomy.wav", denoise=1.0, dereverb=0.7)
    takes = made(doc, ["dlg.take"], "voice: denoise + dereverb")
    clean_file = takes[0]["file"]
    assert compile_doc(doc)["tracks"][0]["clips"][0]["media"] == clean_file      # the document plays the take
    shutil.copyfile(takes[0]["steps"][0]["file"], OUT / "voice-denoised-only.wav")
    shutil.copyfile(clean_file, OUT / "voice-cleaned.wav")
    facts["voice check"] = look.clean_compare(OUT / "voice-noisy-roomy.wav", OUT / "voice-cleaned.wav",
                                              OUT / "voice-before-after.png")
    facts["voice check, original"] = look.measure(OUT / "voice-original.wav")


def dialogue():
    doc = one_clip_doc(VO_ON_CUE, isolate=True)
    takes = made(doc, ["dlg.take"], "voice-over on music: isolate")
    shutil.copyfile(VO_ON_CUE, OUT / "voice-over-on-music.wav")
    shutil.copyfile(takes[0]["file"], OUT / "voice-over-isolated.wav")
    facts["dialogue check"] = look.clean_compare(OUT / "voice-over-on-music.wav", OUT / "voice-over-isolated.wav",
                                                 OUT / "voice-over-isolated-before-after.png")
    facts["dialogue sdr_db vs the real voice"] = look.sdr(audio.read(OUT / "voice-over-isolated.wav", RATE)[0][0],
                                                          audio.read(VO, RATE)[0][0])


GROUPS = {"drums": ("drums", "timpani", "hits"), "bass": ("contrabass", "tuba")}     # the rest is "other"


def cue_stems():
    from rostrum_sound import run_source
    cue = Document.new(KIND)
    cue.run_script(CUE_SCRIPT.name, run_source(CUE_SCRIPT.read_text(encoding="utf-8"), CUE_SCRIPT.name),
                   Who.script(CUE_SCRIPT.name))
    sched = compile_doc(cue)
    with Engine() as eng:
        r = eng.request("render", schedule=sched, out=str(OUT / "cue-mix.wav"), stems="all", master=False)
    group = {t: next((g for g, members in GROUPS.items() if t in members), "other") for t in r["stems"]}
    ref = {}
    for name in ("drums", "bass", "other"):
        y = sum(audio.read(r["stems"][t], 44100)[0] for t in r["stems"] if group[t] == name)
        audio.write(OUT / f"cue-true-{name}.wav", y, 44100)
        ref[name] = OUT / f"cue-true-{name}.wav"
    shutil.rmtree(Path(r["stems"][next(iter(r["stems"]))]).parent, ignore_errors=True)
    doc = one_clip_doc(OUT / "cue-mix.wav")
    doc.apply([{"op": "clip.split_stems", "target": ["dlg.take"]}], Who.agent("proof"))
    takes = made(doc, None, "cue: four stems")
    stems = {}
    for t in takes:
        name = Path(t["file"]).stem
        shutil.copyfile(t["file"], OUT / f"cue-stem-{name}.wav")
        stems[name] = OUT / f"cue-stem-{name}.wav"
    facts["stems check"] = look.stems_check(stems, OUT / "cue-stems-levels.png", reference=ref)


OUT.mkdir(parents=True, exist_ok=True)
for part in (voice_take, dialogue, cue_stems):
    part()
(OUT / "measurements.json").write_text(json.dumps(facts, indent=1, default=str), encoding="utf-8")
print(json.dumps(facts, indent=1, default=str))
