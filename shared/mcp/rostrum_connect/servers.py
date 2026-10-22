"""The ONE place that knows how to start each Rostrum MCP server (stdio)."""
from __future__ import annotations

import functools
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MARKER = {"ROSTRUM_ADDED_BY": "rostrum-connect"}     # how we recognise the entries we added
ROOT = Path(__file__).resolve().parents[3]           # install root, or the repo checkout
APPS = {
    "2d": ("rostrum-2d", "rostrum2d.mcp", "rostrum2d", ("shared/core", "apps/2d/python", "shared/mcp")),
    "sound": ("rostrum-sound", "rostrum_sound.mcp.server", "rostrum_sound",
              ("shared/core", "apps/sound/python", "shared/mcp")),
}


@dataclass(frozen=True)
class Server:
    name: str
    command: str
    args: tuple
    env: dict


def _installed_python() -> Path | None:
    exe = ROOT / "runtime" / "python" / "python.exe"
    return exe if exe.is_file() else None


def _console_python() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":            # stdio needs a console Python
        exe = exe.with_name("python.exe")
    return str(exe)


@functools.lru_cache(maxsize=None)
def _imports_from_here(python: str, package: str) -> bool:
    """Would `python` import `package` (and rostrum_core) from THIS checkout?"""
    code = ("import importlib.util as u\n"
            f"for n in ('rostrum_core', {package!r}):\n"
            "    s = u.find_spec(n)\n    print(s.origin if s and s.origin else '')")
    try:
        out = subprocess.run([python, "-I", "-c", code], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    origins = out.split("\n")[:2]
    return len(origins) == 2 and all(o and Path(o).resolve().is_relative_to(ROOT) for o in origins)


GENERIC_ROOT = r"C:\Users\<you>\AppData\Local\Programs\Rostrum"     # the shipped guides: any person's install


def entry(app: str, project: str | None = None, generic: bool = False) -> Server:
    """How to start `app`'s server on this computer; `generic`: in a standard install (for the shipped guides)."""
    if app not in APPS:
        raise ValueError(f"No Rostrum app called “{app}”. Choose 2d or sound.")
    name, module, package, folders = APPS[app]
    env = dict(MARKER)
    installed = GENERIC_ROOT + r"\runtime\python\python.exe" if generic else _installed_python()
    command = str(installed) if installed else _console_python()
    if not installed and not _imports_from_here(command, package):
        env["PYTHONPATH"] = os.pathsep.join(str(ROOT / f) for f in folders)
    args = ["-m", module] + (["--project", str(project)] if project else [])
    return Server(name, command, tuple(args), env)


def launcher_cmd(app: str) -> str:
    """The line to start the server by hand in a terminal."""
    name = APPS[app][0]
    launcher = ROOT / f"{name}-mcp.cmd"
    if _installed_python() and launcher.is_file():
        return str(launcher)
    s = entry(app)
    return subprocess.list2cmdline([s.command, *s.args])
