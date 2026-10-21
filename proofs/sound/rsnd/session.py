"""A mix: tracks, master settings, and the render through the engine (one process per render).

Python writes a JSON schedule next to the output, runs `rostrum-sound render <schedule> <wav>`,
and reads the engine's stats JSON back from stdout. Any failure raises with the engine's message.
"""
import json
import os
import subprocess
from pathlib import Path

from .effects import space
from .track import Track

SCHEDULE_VERSION = 9
DEFAULT_EXE = r"C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\native\target\release\rostrum-sound.exe"
DEFAULT_CACHE = Path.home() / ".rostrum" / "cache" / "rsnd-pcm"


class RenderError(RuntimeError):
    pass


class Session:
    def __init__(self, bpm=120, seconds=30.0, sample_rate=48000, exe=None, cache_dir=None,
                 reverb_space="hall", master_reverb="dry", volume=1.0, fade_in=0.0, fade_out=0.0):
        self.bpm, self.seconds, self.sample_rate = float(bpm), float(seconds), int(sample_rate)
        self.exe = Path(exe or os.environ.get("RSND_ENGINE") or DEFAULT_EXE)
        self.cache_dir = Path(cache_dir or os.environ.get("RSND_CACHE") or DEFAULT_CACHE)
        self.reverb_space, self.master_reverb = space(reverb_space), space(master_reverb)
        self.volume, self.fade_in, self.fade_out = float(volume), float(fade_in), float(fade_out)
        self.tracks, self.effects, self._master = [], [], None

    # --- time --------------------------------------------------------------------------------
    def beat(self, n) -> float:
        """Seconds at beat `n` (0-based, constant tempo)."""
        return float(n) * 60.0 / self.bpm

    def bar(self, n, beats_per_bar=4) -> float:
        return self.beat(n * beats_per_bar)

    def idx(self, at) -> int:
        if at < 0 or at >= self.seconds:
            raise ValueError(f"time {at} s is outside the mix (0 … {self.seconds} s)")
        return int(round(float(at) * self.sample_rate))

    def clip(self, content, at, dur, tail, volume=1.0, fade_in=0.0, fade_out=0.0, reverb=0.0):
        """A clip with every field the engine reads filled in (schedule/mod.rs Clip)."""
        return {"startSample": self.idx(at), "samples": max(16, int((dur + tail) * self.sample_rate)), "duration": float(dur),
                "content": content, "rate": None, "reverse": None, "glitch": None, "filterSweep": None, "tone": "neutral",
                "fadeIn": float(fade_in), "fadeOut": float(fade_out), "volume": float(volume), "pan": 0.0, "reverb": float(reverb),
                "repair": [], "effects": [], "matchEq": None}

    # --- building ----------------------------------------------------------------------------
    def track(self, name, **kw) -> Track:
        if any(t.name == name for t in self.tracks):
            raise ValueError(f'a track named "{name}" already exists')
        t = Track(self, name, **kw)
        self.tracks.append(t)
        return t

    def effect(self, fx):
        """A master-bus insert (after the master reverb, before mastering)."""
        self.effects.append(fx)
        return self

    def master(self, lufs=None, true_peak=-1.0, glue=0.0):
        """Mastering: loudness target (LUFS, None: as mixed), true-peak ceiling (dBTP), glue 0 … 1."""
        self._master = {"loudness": None if lufs is None else float(lufs), "truePeak": float(true_peak), "glue": float(glue)}
        return self

    def schedule(self, solo=None, master=True) -> dict:
        """The JSON job. `solo`: a track name heard alone (the others still render, unheard)."""
        if solo is not None and not any(t.name == solo for t in self.tracks):
            raise ValueError(f'no track named "{solo}"')
        sr = self.sample_rate
        return {"version": SCHEDULE_VERSION, "sampleRate": sr, "totalSamples": int(round(self.seconds * sr)), "tailSamples": 0,
                "fadeInSamples": int(self.fade_in * sr), "fadeOutSamples": int(self.fade_out * sr), "masterVolume": self.volume,
                "masterReverb": self.master_reverb, "trackReverbSpace": self.reverb_space, "timeWarps": [],
                "effects": self.effects, "master": self._master if master else None,
                "tracks": [t.to_json(mix=solo is None or t.name == solo) for t in self.tracks]}

    # --- rendering ---------------------------------------------------------------------------
    def render(self, out_wav, solo=None, master=True, timeout=600) -> dict:
        """Renders to `out_wav` (32-bit float); writes the schedule beside it; returns the engine's stats."""
        if not self.tracks:
            raise ValueError("nothing to render: the session has no tracks")
        if not self.exe.is_file():
            raise RenderError(f"sound engine not found: {self.exe}")
        out = Path(out_wav).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        job = out.with_suffix(".schedule.json")
        job.write_text(json.dumps(self.schedule(solo, master), indent=1), encoding="utf-8")
        if out.exists():
            out.unlink()
        try:
            p = subprocess.run([str(self.exe), "render", str(job), str(out)], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as e:
            raise RenderError(f"engine timed out after {timeout} s rendering {job}") from e
        if p.returncode != 0:
            raise RenderError(f"engine failed (exit {p.returncode}) on {job}:\n{p.stderr.strip() or p.stdout.strip()}")
        if not out.is_file():
            raise RenderError(f"engine exited 0 but wrote no file: {out}")
        try:
            return json.loads(p.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError) as e:
            raise RenderError(f"engine stats are not JSON:\n{p.stdout[-2000:]}") from e

    def render_stems(self, out_dir, master=False) -> dict:
        """One WAV per track, heard alone; mastering off by default so stem levels compare as mixed."""
        d = Path(out_dir)
        return {t.name: self.render(d / f"{t.name}.wav", solo=t.name, master=master) for t in self.tracks}
