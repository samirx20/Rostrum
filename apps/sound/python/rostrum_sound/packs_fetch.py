"""Download one thing, check its fingerprint BEFORE anything is extracted or kept, and put its files in place.

A mismatch deletes the download and raises a plain RostrumError saying so; nothing half-installed is left (the caller
removes the work folder). Archives: zip (zipfile), tar.xz (tarfile), 7z (the system's tar, libarchive: Windows 10+, macOS).
"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from rostrum_core import RostrumError, codes

CHUNK = 1 << 20
TIMEOUT_S = 30
AUDIO = r"\.(ogg|wav|flac|mp3)$"
Note = Callable[[str], None]


def fail(what: str, problem: str, hint: str | None = None) -> RostrumError:
    return RostrumError(codes.MODEL_MISSING, "pack install", what, problem, hint=hint)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def git_sha1_of(path: Path) -> str:
    h = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    return h.hexdigest()


def check(path: Path, want: dict, what: str) -> None:
    """Delete `path` and raise when its fingerprint (want: sha256 or gitSha1) is not the pinned one."""
    if "gitSha1" in want:
        got, pinned, kind = git_sha1_of(path), want["gitSha1"], "git sha1"
    else:
        got, pinned, kind = sha256_of(path), want["sha256"], "sha256"
    if got != pinned:
        path.unlink(missing_ok=True)
        raise fail(what, f"was downloaded but its fingerprint ({kind}) is {got[:12]}…, not the pinned {pinned[:12]}…; "
                   "the download was deleted and nothing was installed",
                   "Try again; if it keeps failing the source has changed: tell the maker of the app.")


def download(url: str, to: Path, what: str, note: Note | None = None) -> None:
    try:
        resp = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "RostrumSound"}), timeout=TIMEOUT_S)
    except urllib.error.HTTPError as e:
        raise fail(what, f"could not be downloaded from {url}: the server answered {e.code} {e.reason}") from e
    except (urllib.error.URLError, OSError) as e:
        raise fail(what, f"could not be downloaded from {url}: no internet connection ({getattr(e, 'reason', e)})",
                   "Connect, then run the install again; files already installed are kept.") from e
    to.parent.mkdir(parents=True, exist_ok=True)
    total, done, said = int(resp.headers.get("Content-Length") or 0), 0, -1
    try:
        with resp, open(to, "wb") as out:
            while chunk := resp.read(CHUNK):
                out.write(chunk)
                done += len(chunk)
                if note and total and done * 10 // total != said:
                    said = done * 10 // total
                    note(f"{what}: {done / 1e6:.0f} of {total / 1e6:.0f} MB")
    except OSError as e:
        to.unlink(missing_ok=True)
        raise fail(what, f"the connection broke after {done} bytes ({e})") from e


def _dest(root: Path, name: str) -> Path:
    dest = (root / name).resolve()
    if root.resolve() not in dest.parents:
        raise fail(name, "is an archive entry outside the pack folder; the install was refused")
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def extract(archive: Path, kind: str, pattern: str, into: Path) -> list[str]:
    """Extract only the members whose name matches `pattern` (regex, case-insensitive); returns their paths."""
    want, got = re.compile(pattern, re.I), []
    if kind == "7z":
        scratch = archive.parent / "unpacked"
        scratch.mkdir()
        run = subprocess.run(["tar", "-xf", str(archive), "-C", str(scratch)], capture_output=True, text=True)
        if run.returncode:
            raise fail(archive.name, f"could not be unpacked by the system's tar: {run.stderr.strip()[:200]}")
        for p in sorted(scratch.rglob("*")):
            rel = p.relative_to(scratch).as_posix()
            if p.is_file() and want.search(rel):
                shutil.move(str(p), _dest(into, rel))
                got.append(rel)
    elif kind == "zip":
        with zipfile.ZipFile(archive) as z:
            for m in z.infolist():
                if not m.is_dir() and want.search(m.filename):
                    with z.open(m) as src, open(_dest(into, m.filename), "wb") as out:
                        shutil.copyfileobj(src, out)
                    got.append(m.filename)
    else:
        with tarfile.open(archive, "r:*") as t:
            for m in t:
                if m.isfile() and want.search(m.name):
                    with t.extractfile(m) as src, open(_dest(into, m.name), "wb") as out:
                        shutil.copyfileobj(src, out)
                    got.append(m.name)
    return got
