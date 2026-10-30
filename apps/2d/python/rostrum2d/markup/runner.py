"""Running an agent's film script: the code is saved as <project>/films/<name>.py and run with the markup helpers
in scope; it must leave a `film` (a Film). Errors come back with the script's own line number and the line itself."""
from __future__ import annotations

import traceback
from pathlib import Path

from . import film as film_mod
from .film import Film

PRELUDE = "from rostrum2d.markup import *\nimport math, random\n"


class ScriptError(ValueError):
    pass


def films_dir(folder: Path) -> Path:
    d = Path(folder) / "films"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save(folder: Path, name: str, code: str) -> Path:
    if not name or any(c in name for c in '\\/:*?"<>|') or name.startswith("."):
        raise ScriptError(f'name "{name}" can\'t be a file name; use letters, digits, - or _')
    p = films_dir(folder) / f"{name}.py"
    p.write_text(code, encoding="utf-8")
    return p


def load(path: Path, folder: Path) -> Film:
    code = path.read_text(encoding="utf-8")
    ns: dict = {"__name__": "film_script", "__file__": str(path)}
    exec(compile(PRELUDE, "<prelude>", "exec"), ns)
    film_mod.CURRENT_FOLDER = str(folder)
    try:
        exec(compile(code, str(path), "exec"), ns)
    except SyntaxError as e:
        raise ScriptError(f"{path.name} line {e.lineno}: {e.msg}: {(e.text or '').strip()}") from None
    except Exception as e:
        raise ScriptError(_where(e, path, code)) from None
    f = ns.get("film")
    if not isinstance(f, Film):
        raise ScriptError(f"{path.name} ran but made no `film`: end with film = Film(...) set up (inspect_guide 'markup')")
    f.folder = str(folder)
    return f


def _where(e: Exception, path: Path, code: str) -> str:
    lines = code.splitlines()
    rows = [fr for fr in traceback.extract_tb(e.__traceback__) if fr.filename == str(path)]
    if rows:
        n = rows[-1].lineno
        return f"{path.name} line {n}: {type(e).__name__}: {e}  →  {lines[n - 1].strip() if 0 < n <= len(lines) else ''}"
    return f"{path.name}: {type(e).__name__}: {e}"


def script_error(e: Exception, t: float | None) -> str:
    """An error raised while a film's scene ran (at time t): the script's line, else Rostrum's own words."""
    rows = [fr for fr in traceback.extract_tb(e.__traceback__) if Path(fr.filename).parent.name == "films"]
    at = f" at {t:.3f} s" if t is not None else ""
    if rows:
        fr = rows[-1]
        return f"{Path(fr.filename).name} line {fr.lineno}{at}: {type(e).__name__}: {e}  →  {(fr.line or '').strip()}"
    return f"the film's script failed{at}: {type(e).__name__}: {e}"
