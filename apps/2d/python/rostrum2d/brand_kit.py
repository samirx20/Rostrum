"""The project's brand kit (UX_SPEC 3.27 › The library drawer): its colours, text styles and logos, in one place every
document of the project sees: `<project>/brand.json`. This module is the only reader and writer, so when the project
service takes the file over (a request to Team Sam: rostrum_core, for Sound and the Editor too) only this file changes.

    {"colors": [{"name", "value"}], "textStyles": [{"name", font, size, weight, color, …}], "logos": [{"name", "file"}]}

A logo's file is copied into `<project>/media/brand/` so the project carries it; `file` is relative to the project.
Using an entry on a document is ordinary operations (`use_calls`), so it is one change with undo and agents call the
same: a colour sets the layers' colour field, a text style becomes (or refreshes) the document's style of that name and
the texts follow it, a logo is imported (rostrum2d.io.importing). Fails loudly: a bad value or a missing file is refused.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.storage import write_atomic

from . import fields as F
from .io.importing import kind_of
from .ops_look import COLOUR

FILE = "brand.json"
SECTIONS = ("colors", "textStyles", "logos")
LOGO_DIR = Path("media") / "brand"


def _fail(subject: str, problem: str, accepted=()):
    raise RostrumError(codes.BAD_ARGUMENT, "brand kit", subject, problem, list(accepted))


def read(folder) -> dict:
    """The kit, every section present (empty lists when the project has none yet)."""
    path = Path(folder) / FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError) as e:
        raise RostrumError(codes.CHECK_FAILED, "brand kit", str(path), f"can't be read: {e}") from e
    return {s: list(data.get(s, [])) for s in SECTIONS}


def _check(folder, section: str, entry: dict) -> dict:
    """The entry as it is stored: values checked against the fields table, a logo copied into the project."""
    if section not in SECTIONS:
        _fail(f'section "{section}"', "is not a brand kit section", SECTIONS)
    name = str(entry.get("name", "")).strip()
    if not name:
        _fail("name", "is empty")
    if section == "colors":
        return {"name": name, "value": F.param("text", "color").check(entry.get("value"), "brand kit")}
    if section == "textStyles":
        extra = set(entry) - {"name", *F.STYLED}
        if extra:
            _fail(f"{sorted(extra)}", "are not text style fields", F.STYLED)
        return {"name": name, **{k: F.param("textstyle", k).check(v, "brand kit") for k, v in entry.items() if k != "name"}}
    src = Path(folder) / entry.get("file", "")
    if not src.is_file():
        _fail(f'file "{entry.get("file")}"', "doesn't exist")
    kind_of(str(src))                                    # refused (ValueError) when the importer can't read it
    dest = Path(folder) / LOGO_DIR / src.name
    if src.resolve() != dest.resolve():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    return {"name": name, "file": dest.relative_to(folder).as_posix()}


def add(folder, section: str, entry: dict) -> dict:
    """Add an entry, or replace the one of the same name (so "add" also updates). → the kit."""
    kit, row = read(folder), _check(folder, section, entry)
    kit[section] = [e for e in kit[section] if e["name"] != row["name"]] + [row]
    write_atomic(Path(folder) / FILE, json.dumps(kit, indent=1, ensure_ascii=False))
    return kit


def remove(folder, section: str, name: str) -> dict:
    kit = read(folder)
    if section not in SECTIONS or not any(e["name"] == name for e in kit[section]):
        _fail(f'"{name}"', f"is not in the brand kit's {section}", [e["name"] for e in kit.get(section, [])])
    kit[section] = [e for e in kit[section] if e["name"] != name]
    write_atomic(Path(folder) / FILE, json.dumps(kit, indent=1, ensure_ascii=False))
    return kit


def entry(folder, section: str, name: str) -> dict:
    kit = read(folder)
    found = next((e for e in kit.get(section, []) if e["name"] == name), None)
    if found is None:
        _fail(f'"{name}"', f"is not in the brand kit's {section}", [e["name"] for e in kit.get(section, [])])
    return found


def use_calls(doc, section: str, row: dict, ids: list[str]) -> list[dict]:
    """The operation calls that put a kit colour or text style on the layers `ids` (one change)."""
    if not ids:
        _fail("layers", "none given: select the layers first")
    if section == "colors":
        return colour_calls(doc, row["value"], ids)
    if section == "textStyles":
        return style_calls(doc, row, ids)
    _fail(f'section "{section}"', "is used by importing its file (a logo: rostrum2d.io.importing)")


def colour_calls(doc, value: str, ids: list[str]) -> list[dict]:
    """The colour on each layer that has one of its own (`fill` on shapes and paths, `color` on text)."""
    calls = [{"op": f'{it["type"]}.set', "target": [it["id"]], "args": {f: value}}
             for it in (doc.item(i) for i in ids) for f in COLOUR if F.param(it["type"], f)]
    if not calls:
        _fail("layers", "have no colour of their own (a shape, path or text has one)")
    return calls


def style_calls(doc, row: dict, ids: list[str]) -> list[dict]:
    """A kit text style on texts: the document's style of that name takes the kit's values (made from the first
    text when there is none: style.define), then every text follows it (style.use)."""
    from rostrum_core.ids import counted
    from rostrum_core.tree import index
    texts = [i for i in ids if doc.item(i)["type"] == "text"]
    if not texts:
        _fail("layers", "are not texts")
    style = next((s for s in doc.data.get("textStyles", []) if s["name"] == row["name"]), None)
    sid = style["id"] if style else counted(index(doc.data, doc.kind.lists), "textstyle")
    made = [] if style else [{"op": "style.define", "target": [texts[0]], "args": {"name": row["name"], "id": sid}}]
    return made + [{"op": "textstyle.set", "target": [sid], "args": {k: v for k, v in row.items() if k != "name"}},
                   {"op": "style.use", "target": texts, "args": {"style": sid}}]
