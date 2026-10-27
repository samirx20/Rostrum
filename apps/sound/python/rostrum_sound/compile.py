"""Sound document -> the engine's schedule (`rostrum-sound-schedule/1`, apps/sound/ENGINE_CONTRACT.md).

Marker references ("#drop", "#drop+0.5") are resolved here to seconds (a missing marker is a loud error naming
it); seconds and beats are passed as written, with the tempo map (doc tempo + tempo changes: doc/tempo.py) as the
engine's tempo segments. Key changes and sections are not sent (data for agents and the screen). Engine defaults
are not written out: only what the document holds. Options:
  solo=[ids]   these tracks (plus any whose `solo` is on) are heard; every other track gets mute: true
  mute=[ids]   these tracks get mute: true
  master=False the mix as it reaches the master bus: no master inserts, reverb, glue, fades or loudness target
  matched=False no level matching (doc/preset_level.py): the tracks at the volumes the document holds; only the
                devtools that measure the instruments ask for it
"""
from __future__ import annotations

from rostrum_core import RostrumError, plugin_parts

from . import clean_clips, names, voice_lines
from .doc import effects as FX
from .doc import playing as PL
from .doc import preset_level
from .doc import plugins
from .doc import markers, meter, tempo, times
from .doc.registry import LISTS

NOTE_KEYS = ("pitch", "at", "dur", "vel", "pan", *PL.NOTE_KEYS)
HIT_KEYS = ("drum", "at", "vel", "pan", "tune", "decay")
CLIP_KEYS = ("media", "in", "length", "at", "volume", "pitch", "shift", "stretch", "pan", "panTo", "fadeIn", "fadeOut", "reverb")
TRACK_KEYS = ("volume", "pan", "reverb", "tone")
DUCK_KEYS = ("under", "depth", "attack", "release", "lookahead", "hold", "voice")
BUS_KEYS = ("volume", "pan", "mute")
MASTER_MIX = ("volume", "trackReverbSpace")
MASTERING = ("reverb", "fadeIn", "fadeOut", "truePeak", "glue", "safetyClip")
END_FADE = 0.1          # seconds: the soft end (doc field endFade): agent piece B ended at 0.28 in its last 5 ms; with it, 0.000


class _Compiler:
    def __init__(self, root: dict, matched: bool = True):
        self.root = root
        self.matched = matched

    def time(self, value, where):
        return markers.resolve(self.root, value, where)

    def tie(self, note, where):
        """A note's length as the engine takes it: a tied one (`{"to": …}`, `"next"`) as
        seconds, else as written."""
        d = note["dur"]
        if d != times.NEXT and not (isinstance(d, dict) and "to" in d):
            return d
        start = times.seconds(note["at"], self.root, where)
        return round(times.length_seconds(d, self.root, start, note, where), 6)

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
            out.append({"type": fx["effect"], **vals, **self.plugin(fx, w)})
        return out

    def plugin(self, holder, where):
        """A plug-in effect's fields, or `{"plugin": …}` for a plug-in instrument: the contract's plug-in object."""
        spec = holder.get("plugin")
        if not spec:
            return {}
        form = plugins.engine_form(spec, self.env, where)
        return form if holder.get("effect") == "plugin" else {"plugin": form}

    def lanes(self, holder, where):
        """`automation` (volume, pan) and `expression` (dynamics, vibrato, sustain, bend lanes + the vibrato's rate /
        depth and the bend's range)."""
        lanes = {a["lane"]: self.env(a["points"], f"{where}.automation.{a['lane']}")
                 for a in holder.get("automation", [])}
        expr = {k: lanes.pop(k) for k in names.EXPRESSION_LANES if k in lanes}
        expr |= {k: holder[k] for k in ("vibratoRate", "vibratoDepth", "bendRange") if k in holder}
        return {**_nonempty("automation", lanes), **_nonempty("expression", expr)}

    def instrument(self, track):
        kind = track.get("instrument", "none")
        if kind in ("none", "voice") or not track.get(kind):   # a sampled kind whose file isn't picked yet plays nothing
            return {}
        inst = self.plugin(track, f"tracks[{track['id']}]") if kind == "plugin" else {kind: track[kind]}
        if kind == "sfz":
            inst.update(legato=bool(track.get("legato")), swell=bool(track.get("swell")),
                        **_nonempty("articulations", track.get("articulations")))
        if kind == "kit" and track.get("evenKit"):       # transients in reach, pieces at their levels (new tracks)
            inst["even"] = True
        settings = {"model": PL.TOUCH_KEYS, "synth": PL.SYNTH_KEYS}.get(kind, ())
        inst.update({k: track[k] for k in settings if k in track})
        return {"instrument": inst}

    def track(self, track, muted):
        w = f"tracks[{track['id']}]"
        out = {"id": track["id"], **self.instrument(track), **{k: track[k] for k in TRACK_KEYS if k in track}}
        if muted:
            out["mute"] = True
        if "perform" in track:                      # the engine plays the family's defaults when the document holds none
            out["perform"] = track["perform"]
        for key, keys in (("notes", NOTE_KEYS), ("hits", HIT_KEYS)):
            if track.get(key):
                out[key] = [self.pick(n, keys, f"{w}.{key}[{n['id']}]") for n in track[key]]
        for n, sent in zip(track.get("notes", ()), out.get("notes", ())):
            if "dur" in n:
                sent["dur"] = self.tie(n, f"{w}.notes[{n['id']}].dur")
        clips = []
        for c in track.get("clips", []):
            cw = f"{w}.clips[{c['id']}]"
            clip = {**self.pick(c, CLIP_KEYS, cw), **_nonempty("effects", self.effects(c, cw))}
            clip["media"] = clean_clips.media_of(c, cw)   # its cleaned take while it has one (none made yet: loud error)
            clips.append(clip)
        for ln in track.get("lines", []):   # a voice line plays its cached take as a clip (none made yet: loud error)
            clips.append(voice_lines.clip_of(track, ln, self.time(ln["at"], f"{w}.lines[{ln['id']}].at")))
        if clips:
            out["clips"] = clips
        out.update(_nonempty("effects", self.effects(track, w)), **self.lanes(track, w))
        self.match_level(track, out)
        if track.get("output", names.MASTER_OUT) != names.MASTER_OUT:
            out["output"] = track["output"]
        out.update(_nonempty("sends", [self.send(s, w) for s in track.get("sends", [])]),
                   **_nonempty("ducks", [{k: d[k] for k in DUCK_KEYS if k in d} for d in track.get("ducks", [])]))
        return out

    def match_level(self, track, out):
        """The instrument's measured gain under the track's own volume (and its volume lane): equal volumes sound
        balanced. The engine's fader stops at 4."""
        g = preset_level.gain(track) if self.matched else 1.0
        if g == 1.0:
            return
        out["volume"] = min(4.0, round(track.get("volume", 0.85) * g, 6))
        lane = out.get("automation", {}).get("volume")
        if lane:
            out["automation"]["volume"] = preset_level.scaled(lane, g, cap=4.0)

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
            if m.get("gentle"):
                out["maxLimit"] = m.get("maxLimit", 2)
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


def compile(doc, solo=None, mute=None, master=True, matched=True, memo: dict | None = None) -> dict:
    """The schedule for a Document (or its data dict). Pure: the document is not touched. A Document in a project
    folder reads that project's shared markers (doc/markers.py). `memo` (a dict the caller keeps, a screen's): each
    track's part is made again only when it changed (`_kept`), so a note drawn compiles one track, not the song (a
    3-minute song: ~16 ms each edit). The parts it returns are shared with later schedules: never change them."""
    folder = getattr(doc, "folder", None)
    if folder is not None:
        with markers.project(folder):
            return compile(doc.data, solo, mute, master, matched, memo)
    root = plugin_parts.engine_tree(getattr(doc, "data", doc), LISTS)   # a plugin's items: kept in the file, never played
    tracks = root.get("tracks", [])
    heard = _ids(solo, tracks, "solo") | {t["id"] for t in tracks if t.get("solo")}
    silent = _ids(mute, tracks, "mute")
    c = _Compiler(root, matched)
    out = {"contract": names.CONTRACT, "sampleRate": root.get("sampleRate", 48000), "tempo": tempo.contract(root)}
    bars = [{"at": g.start, "bar": g.bar, "beat": meter.main_beats(g)[1]} for g in meter.segments(root)]
    if bars != [{"at": 0.0, "bar": 4.0, "beat": 1.0}]:
        out["meter"] = bars                            # the performance accents each bar's downbeat and main beats
    if root.get("length") is not None:
        out["length"] = c.time(root["length"], "length")
    out["master"] = c.master(root["master"][0], master) if root.get("master") else {}
    if root.get("length") is None or root.get("ringOut"):   # what rings at the Length (or after the last note, with no
        out["ringOut"] = True                                # Length set) dies away (engine: ending.rs); the soft end's fade
                                                             # cut a ringing ride and chord at -17 dBFS (production round)
    elif root.get("endFade", True):      # the song's soft end (doc field endFade): notes ringing at its Length stop softly
        out["master"]["fadeOut"] = max(out["master"].get("fadeOut", 0), END_FADE)
    around = (matched, markers.project_rows() or None, *(v for k, v in root.items() if k != "tracks"))
    out["tracks"] = [_kept(memo, c, t, bool(t.get("mute") or t["id"] in silent or bool(heard) and t["id"] not in heard),
                           around) for t in tracks]
    if memo is not None:
        for gone in set(memo) - {t["id"] for t in tracks}:
            del memo[gone]
    if root.get("buses"):
        out["buses"] = [c.bus(b) for b in root["buses"]]
    return out


def _kept(memo, c, track, muted, around):
    """A track's part as made last time when it is the very same track (the document is never changed in place: an
    edit makes new objects only along its path) with the same song around it (every top-level value but the tracks,
    the project's markers: compared by identity). A track with clips or voice lines reads takes on disk (a cleaned or
    spoken take can land with the track unchanged): always made again."""
    if memo is None or track.get("clips") or track.get("lines"):
        return c.track(track, muted)
    was = memo.get(track["id"])
    if (was is not None and was[0] is track and was[1] == muted and len(was[2]) == len(around)
            and all(a is b for a, b in zip(was[2], around))):
        return was[3]
    part = c.track(track, muted)
    memo[track["id"]] = (track, muted, around, part)
    return part
