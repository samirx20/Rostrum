"""What an exported file is called: the project's name and the composition's, in plain words ("Title walk - Main.mp4"), for the
screen's Export button and `render_export` alike. Letters of any language and spaces are kept; only what Windows and macOS
don't allow in a file name is dropped."""
from __future__ import annotations

import re
from pathlib import Path

_BAD = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_PLAIN = {"main", "default", "composition", "comp"}   # a composition name that says nothing the project's name doesn't


def clean(text: str) -> str:
    """`text` as one file-name part: no path or reserved characters, no doubled, leading or trailing spaces or dots."""
    return re.sub(r"\s+", " ", _BAD.sub(" ", str(text))).strip(" .")


def file_stem(project: str, comps: list[dict], comp_id: str, item: str = "") -> str:
    """The project's name; with the composition's name after it ("Title walk - Credits") when the project has more than one
    composition or this one is named something of its own. A project with one composition called Main is just its name."""
    comp = next((c for c in comps if c.get("id") == comp_id), {})
    cname = clean(comp.get("name") or comp_id)
    pname = clean(project) or clean(item) or "Untitled"
    same = {pname.lower(), comp_id.lower(), item.lower(), *_PLAIN}
    if not cname or (len(comps) <= 1 and cname.lower() in same):
        return pname
    return pname if cname.lower() == pname.lower() else f"{pname} - {cname}"


def project_name(folder) -> str:
    return Path(folder).name if folder else ""


def stem_of(doc, comp_id: str) -> str:
    """The file stem for a composition of an open document (project folder name + composition name)."""
    return file_stem(project_name(doc.folder), doc.data.get("comps", []), comp_id, doc.item_id or "")


def free_path(path: Path) -> Path:
    """`path`, or "name 2.ext", "name 3.ext" … the first that doesn't exist (Keep both)."""
    path, n, found = Path(path), 2, Path(path)
    while found.exists():
        found = path.with_name(f"{path.stem} {n}{path.suffix}")
        n += 1
    return found
