"""The Library drawer's Brand kit (UX_SPEC 3.27): the project's colours, text styles and logos (rostrum2d/brand_kit.py,
the same as the MCP tools inspect_brand_kit / run_brand_kit / run_brand_use), plus this document's own text styles.
Offered to QML as `backend.library`. Open / closed is screen state (Ctrl+L, the tool strip's Library button).

Click a colour: the selected layers take it. Click a text style: the selected texts follow it (one change each, the
same operations an agent's run_brand_use makes). Click a logo: it is imported onto the canvas (the importer's drop).
"+ From selection" adds the selected text's style or the selected layer's colour to the kit; "+ Logo…" a file.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d import brand_kit as B
from rostrum2d import fields as F, text_styles
from rostrum2d.ops_look import COLOUR

from . import library_search as S
from .painting_library import PaintingLibrary


class LibraryView(QObject):
    changed = Signal()
    queryChanged = Signal()         # the typed words, or anything they are matched against, changed

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self._open, self._kit = bridge, False, {s: [] for s in B.SECTIONS}
        self._logos, self._told, self._query = [], None, ""
        self._paintings = PaintingLibrary(bridge, self)      # its Paintings section (painting_library.py)
        self._paintings.changed.connect(self.changed)
        self.changed.connect(self.queryChanged)
        bridge.docChanged.connect(self._check)
        bridge.panelShown.connect(self._check)               # what the selection can take: not the pick's own frame

    def _check(self):
        """An edit or a selection: announced only when this document's styles or what the selection can take changed
        (sent on every edit, the drawer's lists were redone even while it was closed)."""
        told = (self._doc_styles(), self.picked)
        if told != self._told:
            self._told = told
            self.changed.emit()

    def _folder(self) -> str:
        return str(self.b.doc.folder or "")

    def _reload(self):
        try:
            self._kit = B.read(self._folder()) if self._folder() else {s: [] for s in B.SECTIONS}
        except Exception as e:  # noqa: BLE001  a broken brand.json: said, and the kit shows empty
            self.b._fail(f"Error: brand kit: {e}")
            self._kit = {s: [] for s in B.SECTIONS}
        folder = Path(self._folder())                   # each logo's picture, looked for once per read of the kit
        self._logos = [{**logo, "found": (folder / logo["file"]).is_file(),
                        "thumb": QUrl.fromLocalFile(str(folder / logo["file"])).toString()
                        if (folder / logo["file"]).is_file() else ""} for logo in self._kit["logos"]]
        self.changed.emit()

    # ---- what QML shows ------------------------------------------------------------------------------------------
    open = Property(bool, lambda self: self._open, notify=changed)
    paintings = Property(QObject, lambda self: self._paintings, constant=True)
    hasProject = Property(bool, lambda self: bool(self._folder()), notify=changed)

    # The lists are every entry and change only when the kit does; what the typed words leave is `shown` (keys of the
    # rows to show) and `counts`, so a keystroke flips rows on or off and rebuilds nothing (library_search.py).
    colors = Property("QVariantList", lambda self: self._kit["colors"], notify=changed)
    textStyles = Property("QVariantList", lambda self: self._kit["textStyles"], notify=changed)
    # Each logo with `thumb` (the url of its file in the project) and `found` (it can be read: otherwise QML shows the
    # "missing" mark, never a blank).
    logos = Property("QVariantList", lambda self: self._logos, notify=changed)
    paintingRows = Property("QVariantList", lambda self: self._paintings.rows, notify=changed)
    docStyles = Property("QVariantList", lambda self: self._doc_styles(), notify=changed)

    def _doc_styles(self):
        """This document's own text styles: {id, name, size, weight, color, font}. One the brand kit already lists (the
        same look) is not shown twice."""
        kept = {(k.get("font"), k.get("size"), k.get("weight"), str(k.get("color", "")).lower()) for k in self._kit["textStyles"]}
        mine = [{"id": s["id"], "name": s["name"], **text_styles.values(s)} for s in text_styles.styles(self.b.doc.data)]
        return [m for m in mine if (m.get("font"), m.get("size"), m.get("weight"), str(m.get("color", "")).lower()) not in kept]

    def _all(self) -> dict:
        return {"colors": self._kit["colors"], "textStyles": self._kit["textStyles"], "logos": self._logos,
                "paintings": self._paintings.rows, "docStyles": self._doc_styles()}

    def _found(self) -> dict:
        return S.narrow(self._query, self._all())

    searching = Property(bool, lambda self: bool(self._query.strip()), notify=queryChanged)
    query = Property(str, lambda self: self._query, notify=queryChanged)
    shown = Property("QVariantList", lambda self: [S.key(sec, e) for sec, es in self._found().items() for e in es], notify=queryChanged)
    counts = Property("QVariantMap", lambda self: {sec: len(es) for sec, es in self._found().items()}, notify=queryChanged)
    nothing = Property(bool, lambda self: self.searching and S.top(self._found()) is None, notify=queryChanged)    # "Nothing called …"
    searchShown = Property(bool, lambda self: self.searching or S.count(self._all()) > S.MORE_THAN, notify=queryChanged)

    @Slot(str)
    def setQuery(self, text):
        if text != self._query:
            self._query = text
            self.queryChanged.emit()

    @Slot()
    def useTop(self):
        """Enter in the search box: the first thing shown, as a click on it."""
        hit = S.top(self._found())
        if hit is None:
            return
        section, e = hit
        if section in ("colors", "textStyles"):
            self.use(section, e["name"])
        elif section == "logos":
            self.placeLogo(e["name"])
        elif section == "paintings":
            self._paintings.use(e["id"])
        elif self.picked == "texts":
            self.useDocStyle(e["id"])
        else:
            self.b.select(e["id"])

    @Property(str, notify=changed)
    def picked(self):
        """What the selection can take: "texts", "colour" (shapes, paths, texts mixed), or "" (nothing to colour)."""
        items = [self.b.doc.item(i) for i in self.b.selected_layers()]
        if items and all(it["type"] == "text" for it in items):
            return "texts"
        return "colour" if items and any(F.param(it["type"], f) for it in items for f in COLOUR) else ""

    # ---- what a person does --------------------------------------------------------------------------------------
    @Slot(bool)
    def setOpen(self, on):
        self._open, self._query = bool(on), ""               # each opening starts with nothing typed
        self._paintings.setOpen(self._open)
        if self._open:
            self._reload()
        self.changed.emit()

    @Slot(str, str)
    def use(self, section, name):
        """A kit colour or text style on the selection: one change."""
        ids = self.b.selected_layers()
        takes = self.picked == "texts" if section == "textStyles" else bool(self.picked)     # what the pick can take
        if not takes:
            return self.b._set_status(f"Pick a {'text' if section == 'textStyles' else 'shape, path or text'} first, "
                                      f"then use {name} on it")
        self.b.guard(lambda: self.b._apply(B.use_calls(self.b.doc, section, B.entry(self._folder(), section, name), ids),
                                           f"Use {name}"))

    @Slot(str)
    def useDocStyle(self, style_id):
        ids = [i for i in self.b.selected_layers() if self.b.doc.item(i)["type"] == "text"]
        if not ids:
            return self.b._set_status("Pick a text first, then use the style on it")
        self.b.guard(lambda: self.b._apply([{"op": "style.use", "target": ids, "args": {"style": style_id}}], "Use style"))

    @Slot(str)
    def placeLogo(self, name):
        """The logo onto the canvas, centred: the importer's drop (one change, its report if something didn't come)."""
        f = Path(self._folder()) / B.entry(self._folder(), "logos", name)["file"]
        self.b.importer.dropFiles([str(f)], float("nan"), float("nan"))

    @Slot()
    def addFromSelection(self):
        """The selected text's style (its document style when it follows one, named after it) or the selected layer's
        colour, into the kit."""
        items = [self.b.doc.item(i) for i in self.b.selected_layers()]
        if not items:
            return self.b._set_status("Select a text or a coloured layer first")
        it = items[0]
        if it["type"] == "text":
            style = next((s for s in text_styles.styles(self.b.doc.data) if s["id"] == it.get("textStyle")), None)
            name = style["name"] if style else self.b.label_of(it)
            return self._add("textStyles", {"name": name, **text_styles.values(style or it)})
        field = next((f for f in COLOUR if F.param(it["type"], f)), None)
        if field is None:
            return self.b._set_status("That layer has no colour of its own")
        value = it.get(field, F.param(it["type"], field).default)
        return self._add("colors", {"name": value.upper(), "value": value})

    @Slot(str)
    def addLogo(self, url):
        path = QUrl(url).toLocalFile() if url.startswith("file:") else url
        self._add("logos", {"name": Path(path).stem, "file": path})

    @Slot(str, str)
    def remove(self, section, name):
        if self.b.guard(lambda: B.remove(self._folder(), section, name)):
            self._reload()

    def _add(self, section, entry):
        if not self._folder():
            return self.b._set_status("The brand kit is the project's: save the scene in a project first")
        if self.b.guard(lambda: B.add(self._folder(), section, entry)):
            self.b._set_status(f'Added {entry["name"]} to the brand kit')
            self._reload()
