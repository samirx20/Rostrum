"""Automation lanes on the Timeline (no Qt): which lanes a track offers, what a lane shows, and the point edits.

Every edit is the document's `automation.set` with the whole new point list. Points keep the form their time was
written in (beats stay beats, `"#drop+0.5"` stays on its marker); a new point is written in seconds, or in beats
when the lane's points are. A moved point never passes its neighbours (the list stays in time order), snaps to a
quarter beat unless free, and stays inside the lane's range.
"""
from __future__ import annotations

from rostrum_sound.doc import lanes as LN

from . import timing

LABELS = {"volume": "Volume", "pan": "Pan", "dynamics": "Dynamics", "vibrato": "Vibrato", "level": "Send level"}
MELODIC_ONLY = ("dynamics", "vibrato")      # expression lanes: for a track that plays notes
BAND_WORDS = {"freq": "frequency", "gain": "gain", "q": "width (Q)"}
GAIN_LANES = ("volume", "level")            # 0 … 4, drawn 0 … 2 unless a point is higher
EFFECT_NAMES = {"eq": "EQ", "deess": "De-ess", "dehum": "De-hum"}
BUS_HUE, MASTER_HUE = "#9aa1aa", "#d9dde2"  # bus and master rows: greys, apart from the tracks' hues


def label(lane: str) -> str:
    if LN.band_lane(lane):
        i, key = LN.band_lane(lane)
        return f"Band {i + 1} {BAND_WORDS[key]}"
    lane = lane[len(LN.PARAM):] if lane.startswith(LN.PARAM) else lane
    return LABELS.get(lane, lane[:1].upper() + lane[1:])


def raw_points(owner: dict, lane: str) -> list[list]:
    """The lane's points as stored ([time, value], times in whatever form they were written)."""
    return LN.points(owner, lane)


def owner_of(track: dict, target: str) -> dict:
    """The row's item itself (a track, a bus or the master), one of its sends, or one of its effects, by id."""
    return next((s for s in [*track.get("sends", []), *track.get("effects", [])] if s["id"] == target), track)


def applicable(track: dict, root: dict) -> list[tuple[str, str]]:
    """(item id, lane) a row offers (a track, a bus or the master: the catalogue's mix lanes for its type):
    volume and pan, expression only for a track that plays notes (or that already has the lane), the level of
    each of its sends, and every envelope setting of its effects (an EQ: each band's settings; a plug-in: the
    parameters it has changed)."""
    notes = track.get("type") == "track" and track.get("instrument") not in (None, "none", "kit", "kitSfz")
    out = [(track["id"], ln) for ln in LN.offered(track)
           if ln in LN.MIX_RANGE and (ln not in MELODIC_ONLY or notes or raw_points(track, ln))]
    out += [(s["id"], "level") for s in track.get("sends", [])]
    return out + [(fx["id"], ln) for fx in track.get("effects", []) for ln in LN.offered(fx)]


def choice_label(track: dict, root: dict, target: str, lane: str) -> str:
    if target == track["id"]:
        return label(lane)
    owner = owner_of(track, target)
    if owner.get("type") == "effect":
        name = (owner.get("plugin") or {}).get("name") or EFFECT_NAMES.get(owner["effect"], owner["effect"].capitalize())
        return f"{name}: {label(lane)}"
    bus = owner.get("bus", "")
    name = next((b.get("name") for b in root.get("buses", []) if b["id"] == bus), None) or bus
    return f"Send: {name}"


def display_range(owner: dict, lane: str, pts: list) -> tuple[float, float]:
    rng = LN.range_of(owner, lane)
    if rng is None:     # a plug-in parameter: the plug-in's own range is in the scan; show what the points span
        vals = [float(p[1]) for p in pts] + [v for v in [LN.base(owner, lane)] if v is not None]
        return float(min(0.0, *vals)), float(max(1.0, *vals))
    lo, hi = rng
    if lane in GAIN_LANES:
        hi = min(hi, max(2.0, *(float(p[1]) for p in pts))) if pts else 2.0
    return float(lo), float(hi)


def lane_data(track: dict, root: dict, target: str, lane: str) -> dict:
    """What the lane row draws: its range, points in seconds, the item's own setting as a baseline, and the lanes
    on offer (`used`: holds points)."""
    owner = owner_of(track, target)
    raw = raw_points(owner, lane)
    lo, hi = display_range(owner, lane, raw)
    return {"target": target, "lane": lane, "label": choice_label(track, root, target, lane), "lo": lo, "hi": hi,
            "points": [{"t": timing.sec(t, root), "v": float(v)} for t, v in raw],
            "base": LN.base(owner, lane),
            "choices": [{"target": tg, "lane": ln, "label": choice_label(track, root, tg, ln),
                         "used": bool(raw_points(owner_of(track, tg), ln))} for tg, ln in applicable(track, root)]}


def mix_rows(root: dict, open_lanes: dict) -> list[dict]:
    """Compact rows at the bottom of the arrangement, one per bus and the master: no blocks, only their
    automation lanes (`mix`: true; same keys as a track's row)."""
    out = []
    for item in [*root.get("buses", []), *root.get("master", [])]:
        master = item["type"] == "master"
        out.append({"id": item["id"], "name": "Master" if master else item.get("name") or item["id"], "mix": True,
                    "hue": MASTER_HUE if master else BUS_HUE, "mute": bool(item.get("mute")), "solo": False,
                    "kind": item["type"], "blocks": [], "autoUsed": used(item),
                    "auto": lane_data(item, root, *open_lanes[item["id"]]) if item["id"] in open_lanes else None})
    return out


def used(track: dict) -> bool:
    return any(LN.points(o, ln) for o in [track, *track.get("sends", []), *track.get("effects", [])]
               for ln in LN.offered(o))


class PointEdit:
    """One press-drag-release on a lane: grabs the point under the pointer or adds one, then moves it."""

    def __init__(self, target: str, owner: dict, root: dict, lane: str, grid=None):
        self.target, self.lane, self.root, self.grid = target, lane, root, grid      # grid: the window's (timing.Grid)
        raw = raw_points(owner, lane)
        self.lo, self.hi = display_range(owner, lane, raw)
        self.pts = [[t, float(v), timing.sec(t, root)] for t, v in raw]      # [raw time, value, seconds]
        self.beats = bool(raw) and all(isinstance(t, dict) for t, _ in raw)
        self.index = -1

    def press(self, t: float, v: float, tol_t: float, tol_v: float, free: bool) -> dict:
        """Grab the nearest point within tolerance, else insert one at (t, v). Returns the call (or {} for a plain grab)."""
        near = [(((p[2] - t) / tol_t) ** 2 + ((p[1] - v) / tol_v) ** 2, i) for i, p in enumerate(self.pts)]
        d, i = min(near, default=(2.0, -1))
        if d <= 1.0:
            self.index = i
            return {}
        at = timing.snap(t, self.root, free, self.grid)
        raw = {"beat": round(timing.beat(at, self.root), 4)} if self.beats else round(at, 4)
        i = sum(1 for p in self.pts if p[2] <= at)
        self.pts.insert(i, [raw, self._v(v), at])
        self.index = i
        return self.call()

    def move(self, t: float, v: float, free: bool) -> dict:
        p, i = self.pts[self.index], self.index
        lo_t = self.pts[i - 1][2] if i > 0 else 0.0
        hi_t = self.pts[i + 1][2] if i + 1 < len(self.pts) else float("inf")
        at = min(max(timing.snap(t, self.root, free, self.grid), lo_t), hi_t)
        p[0], p[1], p[2] = timing.write_time(p[0], at, self.root), self._v(v), at
        return self.call()

    def remove(self) -> dict:
        del self.pts[self.index]
        self.index = -1
        return self.call()

    def value(self) -> float:
        return self.pts[self.index][1]

    def call(self) -> dict:
        return {"op": "automation.set", "target": [self.target],
                "args": {"lane": self.lane, "points": [[p[0], round(p[1], 4)] for p in self.pts]}}

    def _v(self, v: float) -> float:
        return min(max(v, self.lo), self.hi)
