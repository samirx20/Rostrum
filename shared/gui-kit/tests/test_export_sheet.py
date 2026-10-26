"""The Export sheet never replaces a file without asking: Keep both writes "name 2", Cancel writes nothing, and the
export is marked as a version (rostrum_gui/export_sheet.py)."""
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject
from rostrum_gui.export_sheet import ExportSheet

APP = QCoreApplication.instance() or QCoreApplication([])


class Doc:
    def __init__(self):
        self.marked = {}

    def mark_version(self, name):
        self.marked[name] = len(self.marked)

    def versions(self):
        return dict(self.marked)


class Bridge(QObject):
    def __init__(self):
        super().__init__()
        self.doc, self.said = Doc(), []

    def _set_status(self, text, failed=None):
        self.said.append(text)

    def _fail(self, line):
        self.said.append(line)


class Sheet(ExportSheet):
    def choices_list(self):
        return [{"value": "txt", "label": "Words", "type": ".txt"}]

    def default_folder(self):
        return "nowhere"

    def file_name(self):
        return "Main.txt"

    def begin(self, out, overwrite):
        return {"out": out}

    def work(self, plan, progress):
        Path(plan["out"]).write_text("new", encoding="utf-8")
        return {"files": [str(plan["out"])], "file": str(plan["out"])}


def export(sheet, answer=None):
    sheet.request()
    if answer is not None:
        assert sheet.asking()
        sheet.answer(answer)
    assert sheet.wait(10)


def test_a_file_there_is_never_replaced_without_asking(tmp_path):
    old = tmp_path / "Main.txt"
    old.write_text("old", encoding="utf-8")
    b = Bridge()
    sheet = Sheet(b)
    sheet.setFolder(str(tmp_path))

    export(sheet, "cancel")                              # Cancel: nothing written
    assert old.read_text(encoding="utf-8") == "old" and sorted(p.name for p in tmp_path.iterdir()) == ["Main.txt"]

    export(sheet, "both")                                # Keep both: a new name, the old file untouched
    assert old.read_text(encoding="utf-8") == "old"
    assert (tmp_path / "Main 2.txt").read_text(encoding="utf-8") == "new"
    assert sheet.state == "done" and b.said[-1] == "Exported Main 2.txt" and "Exported v001" in b.doc.marked

    export(sheet, "replace")                             # Replace: only once asked
    assert old.read_text(encoding="utf-8") == "new" and "Exported v002" in b.doc.marked


class Named(Sheet):
    NAMEABLE = True
    file_name = ExportSheet.file_name

    def default_stem(self):
        return "Main"

    def file_ext(self):
        return ".txt"


def test_the_name_typed_in_the_sheet_is_the_file_written(tmp_path):
    sheet = Named(Bridge())
    sheet.setFolder(str(tmp_path))
    sheet.setNameStem('my: film/v2')                      # what a file name can't hold is dropped
    assert sheet.fileName == "my film v2.txt"
    export(sheet)
    assert (tmp_path / "my film v2.txt").is_file()
    sheet.setNameStem("")                                 # empty = the app's own name again
    assert sheet.fileName == "Main.txt"
