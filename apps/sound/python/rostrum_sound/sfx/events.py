"""The event sheet: what the picture shows happening, one line per sound-making event.

A plain schema the lead stores as markers; cues point to an event by its id."""
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .force import FORCES


@dataclass
class Event:
    time: float                  # seconds on the video's timeline
    object: str                  # "padlock", "jacket sleeve"
    material: str                # "iron on brass"
    action: str                  # "knocks", "brushes"
    force: str                   # one of force.FORCES
    distance: str = "close"      # "close", "mid", "far"
    confidence: float = 1.0      # 0-1: how sure the looker is
    note: str = ""

    def __post_init__(self):
        if self.force not in FORCES:
            raise ValueError(f"event at {self.time}s: force '{self.force}' not in {FORCES}")
        if self.time < 0:
            raise ValueError(f"event '{self.object}': time {self.time} is negative")
        if not 0 <= self.confidence <= 1:
            raise ValueError(f"event at {self.time}s: confidence {self.confidence} not between 0 and 1")


def from_dict(d):
    names = {f.name for f in fields(Event)}
    extra = set(d) - names
    if extra:
        raise ValueError(f"event {d}: unknown fields {sorted(extra)}")
    return Event(**d)


def save_events(events, path):
    """Write events (Event or dict) as {"events": [...]} sorted by time."""
    evs = sorted((e if isinstance(e, Event) else from_dict(e) for e in events), key=lambda e: e.time)
    Path(path).write_text(json.dumps({"events": [asdict(e) for e in evs]}, indent=1), encoding="utf-8")
    return str(path)


def load_events(path):
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"{path}: event sheet not found")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))["events"]
    except (ValueError, KeyError) as e:
        raise ValueError(f"{path}: not an event sheet ({e})") from e
    return [from_dict(d) for d in raw]
