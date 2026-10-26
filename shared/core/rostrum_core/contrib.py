"""Where a data table's files can come from: built in, the person's own, or a plugin's.

    from rostrum_core import contrib
    for e in contrib.find("brushes", builtin=BRUSH_DIR):
        print(e.origin, e.path)          # "builtin" | "user" | "plugin:<id>"

`find(kind, builtin)` lists the files of one kind ("brushes", "packs", "delivery", "materials", "keys" ...) in this
order: the built-in folder the caller gives, the person's `<home>/<kind>/`, then each plugin's
`<home>/plugins/<plugin>/<kind>/` (plugins sorted by folder name, which is the plugin id; files sorted inside each
folder). `<home>` is `userhome.home()`, so a scripted run reads its scratch home, never the person's. A folder that
does not exist is empty. This is file level only (what is there); the caller reads and checks the files, and says
loudly which file was wrong and where it came from.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import userhome


@dataclass(frozen=True)
class Entry:
    path: Path
    origin: str                  # "builtin", "user" or "plugin:<id>"


def _files(folder: Path, origin: str) -> list[Entry]:
    if not folder.is_dir():
        return []
    return [Entry(p, origin) for p in sorted(folder.iterdir()) if not p.name.startswith(".")]


def find(kind: str, builtin: Path | str | None = None) -> list[Entry]:
    if not kind or "/" in kind or "\\" in kind or kind.startswith("."):
        raise ValueError(f"contrib: bad kind {kind!r}")
    home = userhome.home()
    out = _files(Path(builtin), "builtin") if builtin else []
    out += _files(home / kind, "user")
    plugins = home / "plugins"
    if plugins.is_dir():
        for plugin in sorted(p for p in plugins.iterdir() if p.is_dir()):
            out += _files(plugin / kind, f"plugin:{plugin.name}")
    return out
