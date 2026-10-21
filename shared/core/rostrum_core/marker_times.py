"""Cheap reads of the project's shared markers (markers.py): {name: seconds}, re-read only when the file changed,
plus the helpers apps use around it: lookup by name, a change stamp, refusing local/shared name clashes, the
used-markers subset for render cache keys, and the one reader of a time written on a marker (`"#drop"`,
`"#drop+0.2"`, `"#hush-0.5"`: seconds after / before it; a trailing "-<number>" is always an offset, so
"#big-hit-1" is one second before "big-hit"). Every app reads marker times through `REF` / `split` / `seconds`."""
from __future__ import annotations

import re
from pathlib import Path

from .errors import RostrumError, codes

ITEM, EXT = "markers", ".mkr"
REF = re.compile(r"^#(\S(?:.*?\S)?)\s*(?:([+-])\s*(\d+(?:\.\d+)?))?$")
FORMS = ['"#drop"', '"#drop+0.2"', '"#hush-0.5"']


def _key(name: str) -> str:
    return " ".join(str(name).split()).lower()


def _file(folder) -> Path:
    return Path(folder) / "docs" / f"{ITEM}{EXT}"


_TIMES: dict = {}       # path -> (file time, {name: seconds}); a frame-by-frame reader re-reads only on change


def times(folder) -> dict[str, float]:
    """{name: seconds} for every marker, by time; what expressions, flags and snapping read. Cheap to call often:
    the file is read again only when it changed. No project folder or no markers yet = {}."""
    if folder is None:
        return {}
    path = _file(folder)
    try:
        stamp = path.stat().st_mtime_ns
    except OSError:
        return {}
    if _TIMES.get(path, (None,))[0] != stamp:
        from .markers import open_markers
        data = open_markers(folder).data
        rows = sorted(data.get("markers", []), key=lambda m: m["at"])
        _TIMES[path] = (stamp, {m["name"]: float(m["at"]) for m in rows})
    return dict(_TIMES[path][1])


def lookup(times_: dict[str, float], name: str) -> float | None:
    """A name's seconds in a times() dict, case and outer spaces ignored; None when there is none."""
    want = _key(name)
    return next((t for n, t in times_.items() if _key(n) == want), None)


def version(folder) -> int:
    """A number that changes whenever the project's markers change (the file's write time); 0 = no markers yet.
    For screens and renders that ask "did markers change?" without a Qt signal (MarkerWatch has one)."""
    try:
        return _file(folder).stat().st_mtime_ns if folder is not None else 0
    except OSError:
        return 0


def refuse_clashes(times_: dict[str, float], local_names, where: str):
    """An app's own (local) markers may not share a name with a project marker (manager, S11): a loud error."""
    shared = {_key(n): n for n in times_}
    clash = sorted(n for n in local_names if _key(n) in shared)
    if clash:
        raise RostrumError(codes.CHECK_FAILED, where, f'marker "{clash[0]}"', "is both a project marker and this "
                           "document's own marker", clash, hint="Rename or delete one of them.")


def used(times_: dict[str, float], names) -> dict[str, float]:
    """{name: seconds} of only the markers a document uses, for its render cache key: moving a marker it doesn't
    use must not re-render it. A used name that isn't there is a loud error."""
    out = {}
    for n in sorted(set(names)):
        at_ = lookup(times_, n)
        if at_ is None:
            raise RostrumError.not_found("markers", "marker", n, list(times_), "the project's markers")
        out[n] = at_
    return out


def split(value) -> tuple[str, float] | None:
    """("drop", 0.2) for "#drop+0.2"; None when the value is not a marker reference."""
    m = REF.match(value) if isinstance(value, str) else None
    if not m:
        return None
    return m.group(1), float(m.group(3) or 0) * (-1 if m.group(2) == "-" else 1)


def ref(value) -> str | None:
    """The marker a time names ("#drop+0.5" -> "drop"), or None."""
    parts = split(value)
    return parts[0] if parts else None


def write(name: str, offset: float = 0.0) -> str:
    """The reference for `offset` seconds from marker `name`: "#drop", "#drop+0.2", "#hush-0.5"."""
    return f"#{name}" if abs(offset) < 1e-6 else f"#{name}{round(offset, 6):+g}"


def seconds(value, times_: dict[str, float], where: str) -> float:
    """A time as seconds: a number as written; a marker reference through `times_` (times()). A marker that isn't
    there is a loud error naming `where` (the key or field that names it) and the markers that exist."""
    parts = split(value)
    if parts is None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RostrumError(codes.BAD_ARGUMENT, where, f"time {value!r}", "is not seconds or a marker", FORMS)
        return float(value)
    at_ = lookup(times_, parts[0])
    if at_ is None:
        raise RostrumError.not_found(where, "marker", parts[0], list(times_), "the project's markers")
    return round(at_ + parts[1], 6)
