"""Sound document -> the engine's schedule (`rostrum-sound-schedule/1`, apps/sound/ENGINE_CONTRACT.md).

Marker references ("#drop", "#drop+0.5") are resolved here to seconds (a missing marker is a loud error naming
it); seconds and beats are passed as written, the engine owns the tempo map. Engine defaults are not written
out: only what the document holds. Options:
  solo=[ids]   these tracks (plus any whose `solo` is on) are heard; every other track gets mute: true
  mute=[ids]   these tracks get mute: true
  master=False the mix as it reaches the master bus: no master inserts, reverb, glue, fades or loudness target
"""
from __future__ import annotations

from rostrum_core import RostrumError

from . import names, voice_lines
from .doc import effects as FX
from .doc import playing as PL
from .doc import times

NOTE_KEYS = ("pitch", "at", "dur", "vel", "pan", *PL.NOTE_KEYS)
HIT_KEYS = ("drum", "at", "vel", "pan", "tune", "decay")
CLIP_KEYS = ("media", "in", "length", "at", "volume", "pitch", "pan", "panTo", "fadeIn", "fadeOut", "reverb")
TRACK_KEYS = ("volume", "pan", "reverb", "tone")
DUCK_KEYS = ("under", "depth", "attack", "release", "lookahead", "hold", "voice")
BUS_KEYS = ("volume", "pan", "mute")
MASTER_MIX = ("volume", "trackReverbSpace")
MASTERING = ("reverb", "fadeIn", "fadeOut", "truePeak", "glue", "safetyClip")


class _Compiler:
    def __init__(self, root: dict):
        self.root = root

    def time(self, value, where):
        return times.resolve(value, self.root, where)

    def env(self, value, where):
        return [[self.time(t, where), v] for t, v in value] if isinstance(value, list) else value

    def pick(self, item, keys, where):
        return {k: self.time(item[k], f"{where}.{k}") if k == "at" else item[k] for k in keys if k in item}

    def effects(self, holder, where):
        out = []
        for fx in holder.get("effects", []):
            if fx.get("bypass"):
                continue
            w = f"{where}.effects[{fx['id']}]"
            vals = {k: self.env(v, f"{w}.{k}") if k != "bands" else
                    [{bk: self.env(bv, f"{w}.bands.{bk}") for bk, bv in b.items()} for b in v]
                    for k, v in FX.active(fx).items()}
            out.append({"type": fx["effect"], **vals})
        return out

    def lanes(self, holder, where):
        """`automation` (volume, pan) and `expression` (dynamics, vibrato lanes + the vibrato's rate / depth)."""
        lanes = {a["lane"]: self.env(a["points"], f"{where}.automation.{a['lane']}")
                 for a in holder.get("automation", [])}
        expr = {k: lanes.pop(k) for k in names.EXPRESSION_LANES if k in lanes}
        expr |= {k: holder[k] for k in ("vibratoRate", "vibratoDepth") if k in holder}
        return {**_nonempty("automation", lanes), **_nonempty("expression", expr)}

    def instrument(self, track):
        kind = track.get("instrument", "none")
        if kind in ("none", "voice") or not track.get(kind):   # a sampled kind whose file isn't picked yet plays nothing
            return {}
        inst = {kind: track[kind]}
        if kind == "sfz":
            inst.update(legato=bool(track.get("legato")), swell=bool(track.get("swell")),
                        **_nonempty("articulations", track.get("articulations")))
        settings = {"model": PL.TOUCH_KEYS, "synth": PL.SYNTH_KEYS}.get(kind, ())
        inst.update({k: track[k] for k in settings if k in track})
        return {"instrument": inst}

    def track(self, track, muted):
        w = f"tracks[{track['id']}]"
        out = {"id": track["id"], **self.instrument(track), **{k: track[k] for k in TRACK_KEYS if k in track}}
        if muted:
            out["mute"] = True
        for key, keys in (("notes", NOTE_KEYS), ("hits", HIT_KEYS)):
            if track.get(key):
                out[key] = [self.pick(n, keys, f"{w}.{key}[{n['id']}]") for n in track[key]]
        clips = []
        for c in track.get("clips", []):
            cw = f"{w}.clips[{c['id']}]"
            clips.append({**self.pick(c, CLIP_KEYS, cw), **_nonempty("effects", self.effects(c, cw))})
        for ln in track.get("lines", []):   # a voice line plays its cached take as a clip (none made yet: loud error)
            clips.append(voice_lines.clip_of(track, ln, self.time(ln["at"], f"{w}.lines[{ln['id']}].at")))
        if clips:
            out["clips"] = clips
        out.update(_nonempty("effects", self.effects(track, w)), **self.lanes(track, w))
        if track.get("output", names.MASTER_OUT) != names.MASTER_OUT:
            out["output"] = track["output"]
        out.update(_nonempty("sends", [self.send(s, w) for s in track.get("sends", [])]),
                   **_nonempty("ducks", [{k: d[k] for k in DUCK_KEYS if k in d} for d in track.get("ducks", [])]))
        return out

    def send(self, s, where):
        """A send: its level is a number, or the points of its `level` lane when it has one."""
        w = f"{where}.sends[{s['id']}]"
        lane = next((a["points"] for a in s.get("automation", []) if a["lane"] == "level"), None)
        level = self.env(lane, f"{w}.level") if lane else s.get("level", 1)
        return {"bus": s["bus"], "level": level, **{k: s[k] for k in ("pre",) if k in s}}

    def bus(self, b):
        w = f"buses[{b['id']}]"
        out = {"id": b["id"], **{k: b[k] for k in BUS_KEYS if k in b}, **_nonempty("effects", self.effects(b, w)),
               **self.lanes(b, w)}
        if b.get("output", names.MASTER_OUT) != names.MASTER_OUT:
            out["output"] = b["output"]
        return out

    def master(self, m, full):
        out = {k: m[k] for k in MASTER_MIX if k in m}
        if full:
            out.update({k: m[k] for k in MASTERING if k in m})
            out["loudness"] = m.get("loudness") if m.get("normalize") else None
            out.update(_nonempty("effects", self.effects(m, "master")))
        return {**out, **self.lanes(m, "master")}


def _nonempty(key, value):
    return {key: value} if value else {}


def _ids(given, tracks, what):
    known = [t["id"] for t in tracks]
    for t in given or ():
        if t not in known:
            raise RostrumError.not_found(f"compile {what}", "track", t, known)
    return set(given or ())


def compile(doc, solo=None, mute=None, master=True) -> dict:
    """The schedule for a Document (or its data dict). Pure: the document is not touched."""
    root = getattr(doc, "data", doc)
    tracks = root.get("tracks", [])
    heard = _ids(solo, tracks, "solo") | {t["id"] for t in tracks if t.get("solo")}
    silent = _ids(mute, tracks, "mute")
    c = _Compiler(root)
    out = {"contract": names.CONTRACT, "sampleRate": root.get("sampleRate", 48000), "tempo": root.get("tempo", 120)}
    if root.get("length") is not None:
        out["length"] = c.time(root["length"], "length")
    out["master"] = c.master(root["master"][0], master) if root.get("master") else {}
    out["tracks"] = [c.track(t, t.get("mute") or t["id"] in silent or bool(heard) and t["id"] not in heard)
                     for t in tracks]
    if root.get("buses"):
        out["buses"] = [c.bus(b) for b in root["buses"]]
    return out
