"""A project's renders: the finished version folders, the next one's place, writing one, copying a project beside a
render (see project.py)."""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from .errors import RostrumError, codes
from .project_files import _SAFE_ID, _read_kept

_VERSION = re.compile(r"^v(\d{3,})$")


def renders(folder, item_id: str) -> list[dict]:
    """Finished renders of one item, newest first: {version, kind, path, files, manifest}."""
    base = Path(folder) / "renders" / item_id
    out = []
    for d in base.iterdir() if base.is_dir() else ():
        m = _VERSION.match(d.name)
        if not m or not d.is_dir() or not (d / "manifest.json").is_file():
            continue
        manifest = _read_kept(d / "manifest.json", f"render {item_id}/{d.name}")
        out.append({"version": int(m.group(1)), "kind": manifest.get("kind", ""), "path": str(d),
                    "files": sorted(p.name for p in d.iterdir() if p.name != "manifest.json"), "manifest": manifest})
    return sorted(out, key=lambda r: -r["version"])


def latest_render(folder, item_id: str, kind: str | None = None) -> dict | None:
    """The newest finished render of an item ("pictures" / "sound" to pick one kind), or None."""
    return next((r for r in renders(folder, item_id) if kind is None or r["kind"] == kind), None)


def next_render(folder, item_id: str) -> Path:
    """The `renders/<item>/vNNN/` folder the next render of `item_id` will finish in (nothing is made): the one rule a
    screen shows the place with and `begin_render` writes by."""
    if not _SAFE_ID.match(item_id):
        raise RostrumError(codes.BAD_ARGUMENT, "render", f'item "{item_id}"', "may use only letters, digits, _ and -")
    base = Path(folder) / "renders" / item_id
    names = [d.name for d in base.iterdir()] if base.is_dir() else []
    taken = [int(m.group(1)) for n in names if (m := re.match(r"^v(\d{3,})(\.partial)?$", n))]
    return base / f"v{max(taken, default=0) + 1:03d}"


def begin_render(folder, item_id: str) -> Path:
    """A new, empty `renders/<item>/vNNN.partial/` (the next version number, `next_render`) for a render to write into."""
    done = next_render(folder, item_id)
    done.parent.mkdir(parents=True, exist_ok=True)
    part = done.with_name(done.name + ".partial")
    part.mkdir()
    return part


def finish_render(partial: Path, manifest: dict) -> Path:
    """Write the manifest and rename `vNNN.partial/` to `vNNN/`. A render with no files is refused (loud)."""
    partial = Path(partial)
    if not partial.name.endswith(".partial") or not partial.is_dir():
        raise RostrumError(codes.BAD_ARGUMENT, "render", str(partial), "is not a vNNN.partial folder")
    if not any(p.name != "manifest.json" for p in partial.iterdir()):
        raise RostrumError(codes.JOB_FAILED, "render", str(partial), "has no files: nothing was rendered")
    (partial / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    done = partial.with_name(partial.name[:-len(".partial")])
    partial.rename(done)
    return done


def save_beside(folder, item_id: str, render_dir, dest) -> Path:
    """Copy the project a render came from to `dest` (next to a render copied out of the project), so another app
    can open the film as a project: project.json, docs/, data/, media/, colour/, .rostrum/ and this render's
    version folder only (other items' renders and exports stay behind). Written whole: `dest.partial`, then
    renamed; an older copy at `dest` is replaced."""
    folder, render_dir, dest = Path(folder), Path(render_dir), Path(dest)
    if not (folder / "docs").is_dir():
        raise RostrumError(codes.NOT_FOUND, "render", str(folder), "is not a project folder (no docs/)")
    part = dest.with_name(dest.name + ".partial")
    shutil.rmtree(part, ignore_errors=True)
    for name in ("docs", "data", "media", "colour", ".rostrum"):
        if (folder / name).is_dir():
            shutil.copytree(folder / name, part / name, ignore=shutil.ignore_patterns("*.partial", "*.lock"))
    for name in ("project.json",):
        if (folder / name).is_file():
            shutil.copy2(folder / name, part / name)
    shutil.copytree(render_dir, part / "renders" / item_id / render_dir.name)
    if dest.exists():
        shutil.rmtree(dest)
    part.rename(dest)
    return dest
