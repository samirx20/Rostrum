"""fit_peaks: the third way to the loudness target (fit_loudness.py): tame the peaky track(s) with a gentle compressor,
the balance kept as written.

Only what stands above the average decides how much limiting the target needs. A compressor on the track whose peaks
set the limiter (first in its chain, fast enough for the peaks, gentle ratio) takes those peaks off; its makeup gives
the track back exactly the loudness it lost, so it sits against the rest as written. Both numbers are measured, never
guessed: the threshold is searched (how far under the track's own peak) by rendering the compiled song, and each
try's makeup is set from what that render measured (the track's loudness against the mix, before and after).
When one track is not enough (the peaks come from several), the next most peaked track is tamed with it, up to three."""
from __future__ import annotations

import copy
import math

from .compile import compile as compile_doc
from .doc import effects as FX
from .doc import ids

RATIO, ATTACK, RELEASE, KNEE = 4.0, 0.005, 0.12, 6.0   # peak control: catches a hit's front, lets go before the next beat
MAX_DEPTH_DB = 18.0       # the threshold at most this far under the track's own peak
MAX_MAKEUP_DB = 9.0       # more than this given back means the track is squashed, not tamed: not an answer
MAX_TRACKS = 3
STEP_DB = 1.0             # the threshold to the dB: finer moves the loudness less than the engine settles
BALANCE_OK = 0.3          # a tamed track's loudness against the mix stays within this of as written


def db(x: float) -> float:
    return 20 * math.log10(max(x, 1e-9))


def peaked(r: dict) -> list[str]:
    """Track ids, most peaked first (peak / rms: the track a limiter works on)."""
    ts = sorted(r.get("tracks") or [], key=lambda t: (t.get("peak") or 0) / max(t.get("rms") or 0, 1e-9), reverse=True)
    return [t["id"] for t in ts if (t.get("peak") or 0) > 0]


def _ids(node, out: set) -> set:
    if isinstance(node, dict):
        if isinstance(node.get("id"), str):
            out.add(node["id"])
        for v in node.values():
            _ids(v, out)
    elif isinstance(node, list):
        for v in node:
            _ids(v, out)
    return out


def _existing(track: dict) -> dict | None:
    """The track's own compressor, if it has one: that one is set, never a second added."""
    return next((fx for fx in track.get("effects", []) if fx.get("effect") == "compressor" and not fx.get("bypass")), None)


class Tamer:
    """Tries and measures compressor settings on copies of the document data (the document is never touched)."""

    def __init__(self, root: dict, engine, scratch, r: dict):
        self.root, self.engine, self.out, self.r = root, engine, str(scratch / "tame.wav"), r
        self.tracks = {t["id"]: t for t in root.get("tracks", [])}
        self.rel0 = {t["id"]: t["lufs"] - r["lufs"] for t in r.get("tracks") or []}   # each track against the mix, as written
        self.renders, self.makeup, self.seen = 0, {}, {}
        dry = self._render(compile_doc(root, master=False))         # the tracks' own peaks, before the master's gain
        self.peak = {t["id"]: db(t["peak"]) - db(self.tracks[t["id"]].get("volume", 0.85)) for t in dry["tracks"] if t["id"] in self.tracks}
        self.ids = _ids(root, set())

    def _render(self, schedule):
        self.renders += 1
        return self.engine.request("render", schedule=schedule, out=self.out, stems=[])

    def settings(self, who: str, depth: float) -> dict:
        have = _existing(self.tracks[who])
        base = {"ratio": RATIO, "attack": ATTACK, "release": RELEASE, "knee": KNEE} if not have else {}
        return {**base, "threshold": round(self.peak[who] - depth, 1), "makeup": round(self.makeup.get(who, have.get("makeup", 0) if have else 0), 1)}

    def data(self, whos, depth: float) -> dict:
        data = copy.deepcopy(self.root)
        for t in data["tracks"]:
            if t["id"] in whos:
                have = _existing(t)
                if have:
                    have.update(self.settings(t["id"], depth))
                else:
                    t["effects"] = [{"id": "~tame", "type": "effect", "bypass": False, **FX.defaults("compressor"), "effect": "compressor",
                                     **self.settings(t["id"], depth)}, *t.get("effects", [])]
        return data

    def measure(self, whos, depth: float, goal: float) -> float:
        """How far under `goal` the song lands with `whos` tamed at `depth` dB under their peaks, the makeup set so each keeps
        its place against the mix (one render to see what the compressor took, one with that given back)."""
        for n in range(3):
            used = {w: self.settings(w, depth)["makeup"] for w in whos}
            got = self._render(compile_doc(self.data(whos, depth)))
            rel = {t["id"]: t["lufs"] - got["lufs"] for t in got["tracks"]}
            drift = {w: round(self.rel0[w] - rel[w], 2) for w in whos}
            if n == 2 or all(abs(d) < BALANCE_OK / 2 for d in drift.values()):
                break
            for w in whos:
                self.makeup[w] = used[w] + drift[w]
        self.seen[(tuple(whos), depth)] = {"got": got, "drift": drift, "makeup": used}
        if any(m > MAX_MAKEUP_DB for m in used.values()):
            return math.inf                                          # squashed: never the answer
        return goal - got["lufs"]

    def ops(self, whos, depth: float) -> list[dict]:
        """The edits for a measured try: its threshold and the makeup that try measured."""
        out = []
        for w in whos:
            have = _existing(self.tracks[w])
            args = {**self.settings(w, depth), "makeup": round(self.seen[(tuple(whos), depth)]["makeup"][w], 1)}
            if have:
                out.append({"op": "effect.set", "target": [have["id"]], "args": {k: args[k] for k in ("threshold", "makeup")}})
                continue
            fid = ids.effect(w, "compressor", self.ids)
            self.ids.add(fid)
            out.append({"op": "effect.add", "target": [w], "args": {"effect": "compressor", "id": fid, **args}})
            if self.tracks[w].get("effects"):
                out.append({"op": "effect.move", "target": [fid], "args": {"to": 0}})
        return out

