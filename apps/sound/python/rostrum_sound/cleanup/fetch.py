"""Download a cleanup model the first time a clean-up needs it (Sam: models ship with the app but are not fetched at install).
Streams to `<file>.partial`, checks size and sha256, then renames: the real file name never holds a half download.
Any failure or a cancel removes the partial and raises a plain RostrumError.

    python -m rostrum_sound.cleanup.fetch --list | <model id> [<model id> …]
"""
from __future__ import annotations

import hashlib
import sys
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from rostrum_core import RostrumError, codes

from . import models
from .models import Model

CHUNK = 1 << 20
TIMEOUT_S = 30                      # no bytes for this long = failed (a stalled download must not hang forever)
ALL = (models.DFN3, models.UMXHQ)
# Which models each clean-up step needs (chain.py's recipe fields: stem, isolate, denoise, dereverb).
NEEDS = {"stem": (models.UMXHQ,), "isolate": (models.UMXHQ, models.DFN3), "denoise": (models.DFN3,), "dereverb": ()}


def target(m: Model) -> Path:
    return models.models_dir() / m.id / m.file


def missing(m: Model) -> bool:
    f = target(m)
    return not f.is_file() or f.stat().st_size != m.size


def needed(what) -> list[Model]:
    """The models still to download for a step name ("stem", "isolate", "denoise", "dereverb") or a recipe
    (`chain.recipe_of(clip)`, a dict of steps). Models already installed are left out."""
    steps = [what] if isinstance(what, str) else [k for k in NEEDS if what.get(k)]
    out: list[Model] = []
    for step in steps:
        if step not in NEEDS:
            raise RostrumError(codes.BAD_ARGUMENT, "cleanup", f'"{step}"', "is not a cleanup step", accepted=list(NEEDS))
        out += [m for m in NEEDS[step] if m not in out and missing(m)]
    return out


def command_for(m: Model) -> str:
    return f"python -m rostrum_sound.cleanup.fetch {m.id}"


def install_hint(m: Model) -> str:
    return f"Download it with: {command_for(m)} (about {m.size / 1e6:.0f} MB)."


def _fail(m: Model, problem: str, code=codes.MODEL_MISSING) -> RostrumError:
    return RostrumError(code, "download", m.id, f"could not be downloaded from {m.url}: {problem}")


def install(m: Model, progress: Callable[[int, int], None] | None = None,
            cancel: threading.Event | None = None) -> Path:
    """Download and verify the model; returns its path. Raises RostrumError (never leaves a partial file)."""
    final = target(m)
    partial = final.with_name(final.name + ".partial")
    if not m.url:
        raise _fail(m, "no download address is set for it")
    final.parent.mkdir(parents=True, exist_ok=True)
    try:
        _stream(m, partial, progress, cancel)
        if partial.stat().st_size != m.size:
            raise _fail(m, f"got {partial.stat().st_size} bytes, expected {m.size}")
        got = _hash(partial)
        if got != m.sha256:
            raise _fail(m, f"the file's fingerprint (sha256) is {got[:12]}…, expected {m.sha256[:12]}…; it was refused")
        partial.replace(final)                       # atomic: the real name is either whole or absent
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return final


def _hash(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        while chunk := fh.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def _stream(m: Model, partial: Path, progress, cancel) -> None:
    try:
        resp = urllib.request.urlopen(urllib.request.Request(m.url, headers={"User-Agent": "RostrumSound"}), timeout=TIMEOUT_S)
    except urllib.error.HTTPError as e:
        raise _fail(m, "not available for download yet (the server answered 404)" if e.code == 404
                    else f"the server answered {e.code} {e.reason}") from e
    except (urllib.error.URLError, OSError) as e:
        raise _fail(m, f"no connection ({getattr(e, 'reason', e)})") from e
    total = int(resp.headers.get("Content-Length") or m.size)
    done = 0
    with resp, open(partial, "wb") as out:
        while True:
            if cancel is not None and cancel.is_set():
                raise _fail(m, "cancelled")
            try:
                chunk = resp.read(CHUNK)
            except OSError as e:
                raise _fail(m, f"the connection broke after {done} bytes ({e})") from e
            if not chunk:
                break
            out.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--list":
        for m in ALL:
            print(f"{m.id}: {m.size / 1e6:.0f} MB, {'installed' if not missing(m) else 'not installed'}, {m.licence}")
        return 0
    by_id = {m.id: m for m in ALL}
    for mid in argv:
        if mid not in by_id:
            print(f"Error: download: {mid!r} is not a model. Accepted: {', '.join(by_id)}.", file=sys.stderr)
            return 2
        m = by_id[mid]
        if not missing(m):
            print(f"{m.id}: already installed at {target(m)}")
            continue
        last = [-1]

        def show(done, total):
            pct = int(100 * done / max(total, 1))
            if pct != last[0] and pct % 5 == 0:
                last[0] = pct
                print(f"{m.id}: {pct}% ({done / 1e6:.0f} of {total / 1e6:.0f} MB)", flush=True)
        try:
            print(f"{m.id}: installed at {install(m, show)} (hash checked)")
        except RostrumError as e:
            print(e.line(), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
