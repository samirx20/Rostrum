"""Routing checks for the whole document: ids and where outputs, sends and ducks point (loud, never a silent mute)."""
from __future__ import annotations

import re

from rostrum_core import did_you_mean

from .. import names

ID = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")


def _point(what, target, known, hint_words):
    if target in known:
        return []
    hint = did_you_mean(str(target), known)
    return [f"{what} is {target!r}, which is not {hint_words} (accepted: {', '.join(known) or 'none'})"
            + (f". {hint}" if hint else "")]


def _loops(buses) -> list[str]:
    out, to = [], {b["id"]: b.get("output", names.MASTER_OUT) for b in buses}
    for start in to:
        seen, at = [start], to[start]
        while at in to:
            if at in seen:
                out.append(f"buses {' → '.join([*seen, at])} feed each other in a loop")
                break
            seen.append(at)
            at = to[at]
    return list(dict.fromkeys(out))


def problems(data: dict) -> list[str]:
    buses, tracks = data.get("buses", []), data.get("tracks", [])
    bus_ids, track_ids = [b["id"] for b in buses], [t["id"] for t in tracks]
    out = [f"bus id {b!r} must be 1–64 letters, digits, _ . -" for b in bus_ids if not ID.match(b)]
    out += [f"bus id {b!r} is also a track id" for b in bus_ids if b in track_ids]
    out += [f"bus id {names.MASTER_OUT!r} is reserved for the master" for b in bus_ids if b == names.MASTER_OUT]
    for b in buses:
        to = b.get("output", names.MASTER_OUT)
        if to == b["id"]:
            out.append(f"bus {b['id']} plays to itself")
        elif to != names.MASTER_OUT:
            out += _point(f"bus {b['id']} output", to, bus_ids, "master or a bus")
    out += _loops(buses)
    for t in tracks:
        to = t.get("output", names.MASTER_OUT)
        if to != names.MASTER_OUT:
            out += _point(f"track {t['id']} output", to, bus_ids, "master or a bus")
        sent = [s.get("bus") for s in t.get("sends", [])]
        out += [f"track {t['id']} has two sends to bus {b!r}" for b in dict.fromkeys(sent) if sent.count(b) > 1]
        for s in t.get("sends", []):
            out += _point(f"send {s['id']} bus", s.get("bus"), bus_ids, "a bus")
        for d in t.get("ducks", []):
            for u in d.get("under", []):
                out += _point(f"duck {d['id']} under", u, track_ids, "a track")
                out += [f"duck {d['id']} ducks track {t['id']} under itself"] if u == t["id"] else []
    return out
