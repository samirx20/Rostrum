"""The sample projects a person can open (File › Open sample, the Start menu's Samples): the one place that knows
where they come from and where a person's own copy lives.

A sample is copied once to Documents\\Rostrum\\Samples\\<Name> and opened there, so it can be changed and saved
without touching the original. The originals: ROSTRUM_SAMPLES (the installed launcher sets it to
<install>\\runtime\\samples), else the developer copy at ~/.rostrum/samples.

    folder, item = samples.open_copy("lull", "sound")     # -> (Documents\\Rostrum\\Samples\\Lull, "score")
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from .errors import RostrumError, codes

# sample -> (its folder name in Documents, {app: the item that app opens})
SAMPLES = {"lull": ("Lull", {"2d": "film", "sound": "score"})}


def originals() -> Path:
    return Path(os.environ.get("ROSTRUM_SAMPLES") or Path.home() / ".rostrum" / "samples")


def copies() -> Path:
    return Path.home() / "Documents" / "Rostrum" / "Samples"


def open_copy(name: str, app: str) -> tuple[Path, str]:
    """(project folder, item) of the person's copy of sample `name` for `app`, copied from the original once."""
    if name not in SAMPLES or app not in SAMPLES[name][1]:
        raise RostrumError(codes.BAD_ARGUMENT, "samples", f"{name} for {app}", "is not a sample",
                           [f"{n} for {a}" for n, (_, apps) in SAMPLES.items() for a in apps])
    folder_name, items = SAMPLES[name]
    mine = copies() / folder_name
    if not mine.is_dir():
        src = originals() / name
        if not src.is_dir():
            raise RostrumError(codes.NOT_FOUND, "samples", str(src), "is missing, so the sample can't be opened",
                               hint="Reinstall Rostrum (the samples come with it).")
        tmp = mine.with_name(mine.name + ".copying")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.copytree(src, tmp, ignore=shutil.ignore_patterns(".rostrum", "__pycache__"))
        tmp.rename(mine)                          # whole or not at all: a half copy is never opened
    return mine, items[app]
