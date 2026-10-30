"""run_script's scripts are files in the project folder (<project>/scripts/<name>.py), so an agent edits them with its own
tools (Read / Edit / Write, a shell one-liner) and runs them again without sending the text.

- `source` (inline text) still works, and is saved as scripts/<name> before it runs: the next run can be {"name": "x.py"}.
- `path` may be relative: to the project folder, else to its scripts/ folder.
- Only `name`: runs scripts/<name> when that file is there.
"""
from __future__ import annotations

from pathlib import Path

SCRIPTS = "scripts"
_BAD = set('\\/:*?"<>|')


def scripts_dir(folder) -> Path:
    return Path(folder) / SCRIPTS


def file_name(name: str) -> str | None:
    """`name` as a file name in scripts/ (".py" added), or None when it can't be one (a path, odd characters)."""
    if not name or name.startswith(".") or _BAD & set(name):
        return None
    return name if name.endswith(".py") else name + ".py"


def resolve(ctx, args: dict) -> dict:
    """run_script's arguments with `path` made absolute (relative, or only a `name` whose file is in scripts/)."""
    folder = getattr(ctx.app, "folder", None)
    if not folder or "source" in args:
        return args
    if "path" in args and not Path(args["path"]).is_absolute():
        tries = [Path(folder) / args["path"], scripts_dir(folder) / args["path"]]
        return {**args, "path": str(next((p for p in tries if p.is_file()), tries[0]))}
    if "path" not in args and (f := file_name(args.get("name", ""))) and (scripts_dir(folder) / f).is_file():
        return {**args, "path": str(scripts_dir(folder) / f)}
    return args


def save(ctx, args: dict, name: str) -> str | None:
    """Inline `source` saved as scripts/<name> (it runs as written either way). The reply line when the file is new."""
    folder = getattr(ctx.app, "folder", None)
    f = file_name(name)
    if not folder or "source" not in args or f is None:
        return None
    p = scripts_dir(folder) / f
    new = not p.is_file()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        if new or p.read_text(encoding="utf-8") != args["source"]:
            p.write_text(args["source"], encoding="utf-8")
    except OSError:
        return None                                   # a read-only project still runs the script; it just isn't kept
    return (f'script saved as {p}: edit that file with your own tools and run it again with {{"name": "{name}"}}, '
            "no need to send the text") if new else None
