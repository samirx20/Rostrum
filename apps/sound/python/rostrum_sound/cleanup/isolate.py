"""Dialogue isolation: the voice taken out of music and effects. No vetted model does this alone (MODELS.md), so it
chains two vetted ones: Open-Unmix UMX-HQ's vocals stem (the voice away from the music) and DeepFilterNet 3 at full
strength (what is left that is not speech: effects, noise). Each model is loaded in turn and released."""
from __future__ import annotations

from . import audio, models, noise, stems

STEP = "isolate"
ENGINE = f"{models.UMXHQ.engine}+{models.DFN3.engine}"


def output(**_):
    return "dialogue.wav"


def run(src, folder, **_):
    x, _ = audio.read(src, stems.RATE)
    voice = stems.separate(x)["vocals"]
    tmp = folder / "vocals.wav"
    audio.write(tmp, voice, stems.RATE)            # through a file: one resampler (audio.read) for every step
    v48, _ = audio.read(tmp, noise.RATE)
    tmp.unlink()
    audio.write(folder / output(), noise.clean(v48, 1.0), noise.RATE)
