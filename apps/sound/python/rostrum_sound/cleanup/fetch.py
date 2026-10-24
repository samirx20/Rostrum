"""Download a cleanup model the first time a clean-up needs it (Sam: models ship with the app but are not fetched at install).
Streams to `<file>.partial`, checks size and sha256, then renames: the real file name never holds a half download.
Any failure or a cancel removes the partial and raises a plain RostrumError.

    python -m rostrum_sound.cleanup.fetch --list | <model> [<model> …]

A model is installed by one name (`BUNDLES`: deepfilternet3, umxhq, voice = the voice model's three files, speech = the
word-timing model's four), the same for the run_model_install tool, the command line and every "not installed" error
(`next_step`), so an agent or a person always knows the exact next step.
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
from .. import speech_models, voice_models
from .models import Model

CHUNK = 1 << 20
TIMEOUT_S = 30                      # no bytes for this long = failed (a stalled download must not hang forever)
ALL = (models.DFN3, models.UMXHQ)
# Which models each clean-up step needs (chain.py's recipe fields: stem, isolate, denoise, dereverb).
NEEDS = {"stem": (models.UMXHQ,), "isolate": (models.UMXHQ, models.DFN3), "denoise": (models.DFN3,), "dereverb": (),
         "voice": voice_models.FILES}          # the voice model: a line that is to be spoken (voice_models.py)
# Every model by the one name it is installed by: what each is for, and its files.
BUNDLES = {"deepfilternet3": ("noise removal", (models.DFN3,)),
           "umxhq": ("splitting music into stems and pulling a voice out of music", (models.UMXHQ,)),
           "voice": ("spoken lines on a voice track", voice_models.FILES),
           "speech": ("each spoken word's start and end (render_voice_words)", speech_models.FILES)}


def bundle_of(m: Model) -> str:
    return next(name for name, (_, files) in BUNDLES.items() if m in files)


def size_said(name: str) -> str:
    mb = sum(m.size for m in BUNDLES[name][1]) / 1e6
    return f"{mb / 1000:.1f} GB" if mb >= 1000 else f"{mb:.0f} MB"


def next_step(name: str) -> str:
    """The exact next step for a missing model, the same words everywhere."""
    return (f'Install it with the run_model_install tool, model "{name}" (about {size_said(name)}); in a terminal: '
            f"python -m rostrum_sound.cleanup.fetch {name}.")


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


def _fail(m: Model, problem: str, code=codes.MODEL_MISSING) -> RostrumError:
    return RostrumError(code, "download", m.id, f"could not be downloaded from {m.url}: {problem}")


def to_install(name: str) -> list[Model]:
    """The files of model `name` still missing, checked to be downloadable before any is fetched (a model with a file
    that has no address yet fails at once, naming the folder to copy it into, instead of after a long download)."""
    todo = [m for m in BUNDLES[name][1] if missing(m)]
    stuck = [m for m in todo if not m.url]
    if stuck:
        raise RostrumError(codes.MODEL_MISSING, "download", f'model "{name}"', "is not available for download yet "
                           f"({', '.join(m.file for m in stuck)} have no download address)",
                           hint=f"Copy those files into {target(stuck[0]).parent} by hand; the download comes when they are published.")
    return todo


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
        raise _fail(m, f"no internet connection; connect, then press Download again ({getattr(e, 'reason', e)})") from e
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
        for name, (what, files) in BUNDLES.items():
            state = "not installed" if any(missing(m) for m in files) else "installed"
            print(f"{name}: {what}; {size_said(name)}, {state}, {files[0].licence}")
        return 0
    for mid in argv:
        if mid not in BUNDLES:
            print(f"Error: download: {mid!r} is not a model. Accepted: {', '.join(BUNDLES)}.", file=sys.stderr)
            return 2
        try:
            todo = to_install(mid)
        except RostrumError as e:
            print(e.line(), file=sys.stderr)
            return 1
        if not todo:
            print(f"{mid}: already installed at {target(BUNDLES[mid][1][0]).parent}")
        for m in todo:
            code = _one(m)
            if code:
                return code
    return 0


def _one(m: Model) -> int:
    if not missing(m):
        print(f"{m.id}: already installed at {target(m)}")
        return 0
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
