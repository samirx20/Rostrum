"""Reverb reduction: the sound engine's late-reverb suppression (no model: statistical, deterministic;
engine/src/dialogue/dereverb.rs), run once on the take through the engine contract and stored, like the other steps.
No learned de-reverb passed the licence check (MODELS.md). `amount` 0..1; the room's decay is measured from the take."""
from __future__ import annotations

import soundfile as sf

from .. import names
from ..engine import Engine

STEP = "dereverb"
ENGINE = f"rostrum-sound-dereverb@{names.CONTRACT}-1"     # bump when dereverb.rs changes what it does
REDUCTION_DB = 18


def output(**_):
    return "dry.wav"


def run(src, folder, amount=0.5, **_):
    info = sf.info(str(src))
    schedule = {"contract": names.CONTRACT, "sampleRate": info.samplerate, "length": info.duration,
                "tracks": [{"id": "take", "clips": [{"media": str(src), "at": 0, "effects": [
                    {"type": "dereverb", "amount": float(amount), "reduction": REDUCTION_DB}]}]}]}
    with Engine() as eng:                           # one engine process for the job, ended after it
        eng.request("render", schedule=schedule, out=str(folder / output()), master=False)
