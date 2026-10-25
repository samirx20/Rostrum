"""What a person can do when a file is wrong, for ProjectFiles (a slot mix-in; INTERACTION.md 1.19):

- "Open the last version that works": a damaged or newer file is refused in plain words; when its history can rebuild
  it (rostrum_core.rescue) the refusal offers it (`rescue`: the start screen's banner, and a ≡ row). Opening it replays
  the history up to the last clean step and says which; the damaged files are kept beside, never overwritten.
- Find… for missing files: the project opens with its missing items marked "missing". ≡ › Find missing files… (there
  only while something is missing) asks for a folder and links every file found in it again, in ONE change (find_files.py).
  `missingRows()` gives the app's Problems list its rows.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Slot
from rostrum_core import RostrumError, Who, codes, rescue

from . import docfiles as F
from . import find_files


class RepairSlots:
    _rescue: dict | None = None

    # ---- Open the last version that works ---------------------------------------------------------------------------
    def offer_rescue(self, folder, item, error) -> None:
        """A refusal just happened: remember what can be offered (nothing when the history can't rebuild it)."""
        self._rescue = None
        if not self.kind.doc_kind or not isinstance(error, RostrumError) or error.code != codes.CHECK_FAILED \
                and not isinstance(error, OSError):
            return
        try:
            r = rescue.plan(self.kind.doc_kind, folder, item)
        except RostrumError:
            return
        name = F.name_of(folder, item)
        self._rescue = {"folder": str(folder), "item": item, "name": name, "step": r.step, "steps": r.steps,
                        "said": F.said(error), "words": (f'Its history can rebuild "{name}" up to step {r.step} of '
                                                         f'{r.steps}.' if r.lost else f'Its history can rebuild "{name}" whole.')}
        self._start = True                                  # the banner is on the start screen
        self.changed.emit()

    def rescue_row(self) -> dict:
        return self._rescue or {}

    @Slot()
    def dismissRescue(self):
        self._rescue = None
        self.changed.emit()

    def openRescued(self):
        if not self._rescue:
            return False
        r = self._rescue

        def go():
            doc, done = rescue.rebuild(self.kind.doc_kind, Path(r["folder"]), r["item"])
            self._rescue = None
            self._open(r["folder"], r["item"], quiet=False)
            self._say(f'{done.words()} The damaged file is kept beside it as "{r["item"]}{self.kind.ext}.damaged{done.stamp}".')
        return self._try(go)

    # ---- Find… -----------------------------------------------------------------------------------------------------
    def _missing(self) -> list:
        if not (self.has_project() and self.kind.refs):
            return []
        return find_files.missing(self.kind.refs(self.doc))

    def missingRows(self) -> list[dict]:
        """Rows for the Problems list: one per missing file, in words, with what to do."""
        return [{"label": "Missing file", "message": f'"{Path(p).name}" is not at {p}.', "fix": "≡ › Find missing files…",
                 "item": item, "find": True} for item, _field, p in self._missing()]

    @Slot(str, result=bool)
    def findMissing(self, folder_url):
        """Link again every missing file found in the chosen folder: one change, one undo step."""
        def go():
            refs = self.kind.refs(self.doc)
            made = find_files.relink(refs, self._local(folder_url), lambda i: self.kind.ref_op(self.doc, i))
            if made.calls:
                bridge = self.host.bridge
                self.doc.apply(made.calls, bridge.who if bridge is not None else Who.person("sam"),
                               label=f"Find {len(made.found)} missing file{'s' if len(made.found) != 1 else ''}")
            self._say(made.words())
            self.changed.emit()
        return bool(self.kind.refs) and self._try(go)

    def _local(self, url) -> Path:
        from .project_files import local
        return local(url)
