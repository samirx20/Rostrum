"""Trial mixes for the searches that render a song many times over (fit_loudness.py, fit_peaks.py): each trial is a
compiled schedule and its answer the numbers a render gives (lufs, truePeak, master, tracks). With an engine that
answers `measure` (ENGINE_CONTRACT.md) no file is written, several trials are mixed side by side, and the instruments
and untouched tracks are not worked out again between trials; an older engine renders each one to a scratch file."""
from __future__ import annotations

from pathlib import Path


class Trials:
    def __init__(self, engine, scratch: Path):
        self.engine, self.out, self.renders = engine, str(Path(scratch) / "trial.wav"), 0

    def many(self, schedules: list[dict]) -> list[dict]:
        """Each schedule's numbers, in order."""
        self.renders += len(schedules)
        if self.engine.can("measure"):
            return self.engine.request("measure", schedules=schedules)["results"]
        return [self.engine.request("render", schedule=s, out=self.out, stems=[]) for s in schedules]

    def one(self, schedule: dict) -> dict:
        return self.many([schedule])[0]
