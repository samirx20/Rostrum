"""A track: an instrument (SFZ file, built-in instrument or drum kit), its notes, samples, fader and effects.

Times are seconds from the start of the mix (use `session.beat(n)` for beats). Notes collect into one
score clip spanning the mix; each recorded sample is its own clip.
"""
from pathlib import Path

from . import pitch
from .pcm import decode

# Built-in instruments (instruments/voices/tones.rs).
BUILT_IN = ("feltPiano", "grandPiano", "warmPad", "analogStrings", "spiccatoStrings", "choirPad",
            "cinematicBrass", "subBass", "shepardRiser", "glassMarimba")
TONES = ("neutral", "muffled", "warm", "sub-boost", "bright", "voice-clarity", "radio")


def _tone(name):
    if name not in TONES:
        raise ValueError(f'tone "{name}" is not one of {TONES}')
    return name


def _points(points, what):
    out = [[float(t), float(v)] for t, v in points]
    if any(b[0] < a[0] for a, b in zip(out, out[1:])):
        raise ValueError(f"{what}: points must be in time order")
    return out


class Track:
    def __init__(self, session, name, sfz=None, instrument=None, kit=None, volume=0.85, pan=0.0,
                 reverb=0.0, tone="neutral", legato=False, swell=False):
        if sum(x is not None for x in (sfz, instrument, kit)) > 1:
            raise ValueError(f'track "{name}": give one of sfz=, instrument=, kit=')
        if sfz is not None and not Path(sfz).is_file():
            raise FileNotFoundError(f'track "{name}": SFZ file not found: {sfz}')
        if instrument is not None and instrument not in BUILT_IN:
            raise ValueError(f'track "{name}": instrument "{instrument}" is not one of {BUILT_IN}')
        if kit not in (None, "synth") and not Path(kit).is_file():
            raise FileNotFoundError(f'track "{name}": kit must be "synth" or an SFZ file on GM keys; not found: {kit}')
        self.s, self.name = session, name
        self.sfz = {"file": str(Path(sfz).resolve()), "legato": legato, "swell": swell} if sfz else None
        self.instrument = instrument or "grandPiano"
        self.kit = kit
        self.volume, self.pan, self.reverb, self.tone = float(volume), float(pan), float(reverb), _tone(tone)
        self.voices, self.clips, self.effects, self.automation = [], [], [], {}

    # --- notes -------------------------------------------------------------------------------
    def _note_voice(self, freqs, at, dur, vel, pan):
        v = {"kind": "note", "instrument": "sampled" if self.sfz else self.instrument, "freqs": freqs,
             "startIdx": self.s.idx(at), "duration": max(0.05, float(dur)), "velocity": float(vel), "pan": float(pan)}
        if self.sfz:
            v["sfz"] = self.sfz
        self.voices.append(v)
        return self

    def note(self, name, at, dur, vel=0.8, pan=0.0):
        """One note: a name ("D3", "F#4") or MIDI number."""
        return self.chord([name], at, dur, vel, pan)

    def chord(self, names, at, dur, vel=0.8, pan=0.0):
        if self.kit:
            raise ValueError(f'track "{self.name}" is a drum kit: use .drum()')
        return self._note_voice([pitch.freq(n) for n in names], at, dur, vel, pan)

    def drum(self, voice, at, vel=0.85, pan=0.0, tune=1.0, decay=1.0):
        """A hit. kit="synth": the engine's own kit (kick, snare, clap, hat, openHat, cymbal, tom, rim);
        an SFZ kit: a GM drum name (kick, snare, hat, openHat, crash, ride, tom …) or GM key number."""
        if self.kit == "synth":
            if voice not in pitch.SYNTH_DRUMS:
                raise ValueError(f'drum "{voice}" is not one of {pitch.SYNTH_DRUMS}')
            self.voices.append({"kind": "drum", "voice": voice, "startIdx": self.s.idx(at), "velocity": float(vel),
                                "pan": float(pan), "tune": float(tune), "decay": float(decay)})
            return self
        if not self.kit:
            raise ValueError(f'track "{self.name}" has no kit (kit="synth" or kit=<SFZ on GM keys>)')
        self.voices.append({"kind": "note", "instrument": "sampled", "sfz": {"file": str(Path(self.kit).resolve()), "legato": False, "swell": False},
                            "freqs": [pitch.gm_drum(voice)], "startIdx": self.s.idx(at), "duration": 0.2 * decay,
                            "velocity": float(vel), "pan": float(pan)})
        return self

    # --- recorded audio ----------------------------------------------------------------------
    def sample(self, path, at, volume=1.0, pitch=0.0, pan=0.0, pan_to=None, fade_in=0.0, fade_out=0.0,
               duration=None, reverb=0.0, offset=0.0, length=None):
        """A recorded take played like tape (pitch in semitones changes speed), cut at `duration` s.
        `offset` / `length`: the take's in-point and length inside a longer recording (library takes)."""
        pcm = decode(path, self.s.sample_rate, self.s.cache_dir, offset, length)
        length = pcm.frames / self.s.sample_rate / (2.0 ** (pitch / 12.0))
        dur = min(length, float(duration)) if duration else length
        self.clips.append(self.s.clip({"kind": "sample", "pcm": pcm.to_json(), "duration": dur, "volume": 1.0,
                                       "pitch": float(pitch), "panFrom": float(pan), "panTo": float(pan if pan_to is None else pan_to)},
                                      at=at, dur=dur, tail=0.0, volume=volume, fade_in=fade_in, fade_out=fade_out, reverb=reverb))
        return self

    # --- mix ---------------------------------------------------------------------------------
    def effect(self, fx):
        """An insert from rsnd.effects (eq, compressor, reverb, delay, …), after the tone, before the fader."""
        self.effects.append(fx)
        return self

    def volume_automation(self, points):
        """The fader over time: [(seconds, gain), …]; replaces `volume` where it is set."""
        self.automation["volume"] = _points(points, f'track "{self.name}" volume')
        return self

    def pan_automation(self, points):
        self.automation["pan"] = _points(points, f'track "{self.name}" pan')
        return self

    def to_json(self, mix=True):
        clips = list(self.clips)
        if self.voices:
            clips.insert(0, self.s.clip({"kind": "score", "voices": self.voices}, at=0.0, dur=self.s.seconds, tail=0.0))
        return {"name": self.name, "tone": self.tone, "volume": self.volume, "pan": self.pan, "reverb": self.reverb,
                "mix": mix, "ducks": [], "effects": self.effects, "automation": self.automation, "clips": clips}
