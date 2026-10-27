"""Trial mixes for the searches that render a song many times over (fit_loudness.py, fit_peaks.py): each trial is a
compiled schedule and its answer the numbers a render gives (lufs, truePeak, master, tracks). With an engine that
answers `measure` (ENGINE_CONTRACT.md) no file is written, several trials are mixed side by side, and the instruments
and untouched tracks are not worked out again between trials; an older engine renders each one to a scratch file."""
from __future__ import annotations

from pathlib import Path


class Trials:
    def __init__(self, engine, scratch: Path, span: tuple[float, float] | None = None):
        """`span`: (from, to) seconds: the trials measure that stretch alone, as a file of it is mastered (rendered to a
        scratch file: `measure` takes the whole song)."""
        self.engine, self.out, self.renders, self.span = engine, str(Path(scratch) / "trial.wav"), 0, span

    def many(self, schedules: list[dict]) -> list[dict]:
        """Each schedule's numbers, in order."""
        self.renders += len(schedules)
        if self.span:
            return [self.engine.request("render", schedule=s, out=self.out, stems=[], **{"from": self.span[0], "to": self.span[1]})
                    for s in schedules]
        if self.engine.can("measure"):
            return self.engine.request("measure", schedules=schedules)["results"]
        return [self.engine.request("render", schedule=s, out=self.out, stems=[]) for s in schedules]

    def one(self, schedule: dict) -> dict:
        return self.many([schedule])[0]
