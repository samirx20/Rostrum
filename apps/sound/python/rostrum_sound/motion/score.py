"""Motion events (read.py) -> musical answers a person or agent may choose (PURPOSE.md: music first, no automatic
sound on every move, no whooshes). Nothing is added unless asked: `suggest` lists, per event that can earn a sound,
the answers it could take; `script` writes only the ones chosen, as instrument parts (or, for "library", a real
recording from the person's own sound folders, score_library.py). Every value is a field the person edits after.

  land   a move arriving on its place, hard enough to feel (`lands`): a note or a hit on the landing, or a rise
         into it built from an instrument: a string swell, a cymbal roll swelling, a piano run up the key
  snap   a title snapping in: a note or a hit on its most sudden moment
  press  a button tapped: a real click from the library (a recording of the real thing)
  step   a counter's digit / a cut-in: a struck note, or a real tick from the library
A drift, or a move that doesn't land, gets no suggestion: silence is an answer.
"""
from __future__ import annotations

BUS = "ui"
ANSWERS = {"land": ("note", "hit", "strings", "cymbal", "piano", "library"), "snap": ("note", "hit", "library"),
           "press": ("library",), "step": ("note", "library")}
SAYS = {"note": "a struck bell note on the moment", "hit": "a kick and cymbal hit on the moment",
        "strings": "a string swell rising into the moment", "cymbal": "a cymbal roll swelling into the moment",
        "piano": "a piano run up the key, landing on the moment", "library": "a real recording from your sound library"}
# answer -> (track id, how the track plays)
TRACKS = {"note": ("motion_bell", {"model": "tubularBell"}), "hit": ("motion_hits", {"kit": "synth"}),
          "strings": ("motion_strings", {"builtIn": "analogStrings"}), "cymbal": ("motion_hits", {"kit": "synth"}),
          "piano": ("motion_piano", {"builtIn": "grandPiano"})}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SCALES = {"major": (0, 2, 4, 5, 7, 9, 11), "minor": (0, 2, 3, 5, 7, 8, 10)}
RISE_S = (0.4, 2.0)       # a rise lasts the move, kept inside these (s)


def suggest(events: list[dict]) -> list[dict]:
    """One row per event that can earn a sound: id, kind, at (s), the answers it could take. Adds nothing."""
    out = []
    for e in events:
        kind, at = e["kind"], e["at"]
        if kind == "move":
            land = e.get("lands")
            if not land or land["hardness"] < 0.15:
                continue
            kind, at = "land", land["at"]
        hard = (e.get("lands") or {}).get("hardness", 0.8 if kind == "snap" else 0.5)
        out.append({"id": f"{kind}{len(out) + 1}", "kind": kind, "at": round(at, 4), "hardness": round(hard, 3),
                    "rise_s": round(min(RISE_S[1], max(RISE_S[0], at - e.get("start", e["at"]))), 3),
                    "answers": list(ANSWERS[kind]), "event": e})
    return out


def pitches(key: str) -> list[str]:
    """The key's scale from its root, three octaves from octave 3: "D minor" -> D3, E3, F3 …"""
    root, _, mode = key.strip().partition(" ")
    steps = SCALES.get(mode.strip().lower() or "major")
    name = root[:1].upper() + root[1:]
    flat = name.endswith("b") and len(name) == 2
    if steps is None or name.rstrip("b") not in NAMES:
        raise ValueError(f"key {key!r}: use a note and major / minor, like \"D minor\"")
    pc = (NAMES.index(name.rstrip("b")) - flat) % 12
    return [f"{NAMES[(pc + s) % 12]}{3 + o + (pc + s) // 12}" for o in (0, 1, 2) for s in steps]


def parts(chosen: list[tuple[dict, str]], key: str) -> list[tuple[str, str, dict]]:
    """(track id, call, fields) for each (suggestion, answer) chosen, played by an instrument."""
    scale, out = pitches(key), []
    for s, a in chosen:
        t, at, v, lead = TRACKS[a][0], s["at"], round(0.4 + 0.5 * s["hardness"], 3), s["rise_s"]
        if a == "note":
            out.append((t, "note", {"pitch": scale[7], "at": at, "dur": 2.0, "vel": v}))
        elif a == "hit":
            out += [(t, "hit", {"drum": "kick", "at": at, "vel": v}), (t, "hit", {"drum": "cymbal", "at": at, "vel": v})]
        elif a == "strings":
            out.append((t, "chord", {"pitches": [scale[0], scale[4], scale[9]], "at": round(at - lead, 4), "dur": round(lead + 0.6, 4),
                                     "vel": v, "dynamics": [[0, 0.15], [round(lead / (lead + 0.6), 3), 1.0], [1, 0.5]]}))
        elif a == "cymbal":
            k = max(4, int(lead * 16))
            out += [(t, "hit", {"drum": "cymbal", "at": round(at - lead + lead * i / k, 4), "vel": round(0.08 + 0.6 * v * (i / k) ** 2, 3)})
                    for i in range(k)] + [(t, "hit", {"drum": "cymbal", "at": at, "vel": v})]
        elif a == "piano":
            run = scale[7:15]
            out += [(t, "note", {"pitch": p, "at": round(at - lead + lead * i / (len(run) - 1), 4), "dur": 0.4 if i < len(run) - 1 else 1.5,
                                 "vel": round(0.3 + (v - 0.3) * i / (len(run) - 1), 3)}) for i, p in enumerate(run)]
    return out


def script(chosen: list[tuple[dict, str]], key: str, width: float, library: list[dict] | None = None) -> tuple[str, list[str]]:
    """The chosen answers as a Sound script (run with run_script, so a re-run keeps what a person changed) and its
    track ids. 'library' answers are real recordings picked by score_library.py."""
    placed = parts([c for c in chosen if c[1] != "library"], key)
    real = [s["event"] for s, a in chosen if a == "library"]
    if real:
        from .score_library import clips
        placed += [(t, "clip", f) for t, f in clips(real, width, library or [])]
    tracks = list(dict.fromkeys(t for t, _, _ in placed))
    plays = dict(TRACKS.values())
    lines = [f"{t} = track({t!r}{''.join(f', {k}={v!r}' for k, v in plays.get(t, {}).items())})" for t in tracks]
    first = {"note": "pitch", "chord": "pitches", "hit": "drum", "clip": "media"}
    for t, call, f in placed:
        f = dict(f)
        head = f.pop(first[call])
        lines.append(f"{t}.{call}({head!r}, {', '.join(f'{k}={v!r}' for k, v in f.items())})")
    return "\n".join(lines), tracks


def glue_ops(doc: dict, tracks: list[str]) -> list[dict]:
    """The "ui" bus (short shared room, light compressor) for library recordings when the document has none yet, and
    those tracks routed into it. Nothing for what is already there, so running it again changes nothing a person set."""
    tracks = [t for t in tracks if t.startswith("ui_")]
    if not tracks:
        return []
    ops = []
    if not any(b["id"] == BUS for b in doc.get("buses", [])):
        ops = [{"op": "bus.add", "args": {"id": BUS}},
               {"op": "effect.add", "target": [BUS], "args": {"effect": "eq", "bands": [{"shape": "highpass", "freq": 45}]}},
               {"op": "effect.add", "target": [BUS], "args": {"effect": "reverb", "space": "room", "mix": 0.12}},
               {"op": "effect.add", "target": [BUS], "args": {"effect": "compressor", "threshold": -20, "ratio": 2.5,
                                                             "attack": 0.008, "release": 0.12, "makeup": 2}}]
    have = {t["id"]: t.get("output") for t in doc.get("tracks", [])}
    return ops + [{"op": "track.set", "target": [t], "args": {"output": BUS}} for t in tracks if have.get(t) == "master"]
