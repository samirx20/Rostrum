"""A scripted run (a picture, steps, the layout check: rostrum_core.userhome.scripted) never writes into a real project.

`--doc <folder> <item>` on a scripted run opens a scratch copy of the project (its document, history and script record;
never its renders), or a new project in scratch when the folder has none; the copy lives in the scratch home and goes
away with it. A person's own launch opens the folder itself. ROSTRUM_REAL_HOME=1 turns the isolation off, as it does for settings.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from rostrum_core import userhome
from rostrum_core.storage import paths

SKIP = shutil.ignore_patterns("renders", "*.partial", "*.lock", "__pycache__")


def isolated(folder, item: str, ext: str) -> Path:
    """The folder to open for `--doc folder item`: the same one for a person, a scratch copy for a scripted run."""
    reason = userhome.scripted()
    if reason is None:
        return Path(folder)
    root = userhome.home() / "projects"
    root.mkdir(parents=True, exist_ok=True)
    mine = Path(tempfile.mkdtemp(dir=root, prefix="scratch-")) / Path(folder).name     # the project's own name on screen
    if paths(folder, item, ext)["doc"].is_file():
        shutil.copytree(folder, mine, ignore=SKIP)
    return mine
