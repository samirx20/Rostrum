"""What would break silently in the one file model (FILES.md): a project opened from ≡ › Open is live, so an agent's
change made through its own copy of the document (as the MCP server does) shows in the window after a catch-up, and
the person's own change is on disk with nothing saved by hand. No window: the host only records what it is shown."""
from pathlib import Path

from rostrum_core import Document, Who, live, toy
from rostrum_gui.docfiles import AppFiles
from rostrum_gui.project_files import ProjectFiles

KIND = toy.KIND


class Host:
    bridge = None

    def show(self, doc):
        self.shown = doc


def files_in(root: Path) -> ProjectFiles:
    def blank(folder):
        doc = toy.sample(folder, "main") if folder else Document.new(KIND)
        if folder:
            doc.save()
        return doc
    kind = AppFiles(app="test", title="Test", noun="project", ext=KIND.ext, untitled="Untitled", folder=lambda: root,
                    blank=blank, open=lambda f, i: Document.open(f, i, KIND), resolve=lambda p: (Path(p), "main"))
    return ProjectFiles(kind, Host())


def test_a_project_opened_from_open_is_live(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_PROJECTS_DIR", str(tmp_path))
    files = files_in(tmp_path)
    made = files_in(tmp_path).kind.blank(tmp_path / "Promo")
    assert files.openPath(str(made.folder))
    window = files.host.shown
    assert window.live is not None                                      # opened live, not "saved by hand"

    agent = Document.open(window.folder, "main", KIND)                   # the MCP server's own copy
    live.keep(agent)
    agent.apply({"op": "layer.move", "target": ["card"], "args": {"x": 70}}, Who.agent("claude-code"))
    assert window.item("card")["x"] == 0
    window.live.catch_up()                                               # the window's LiveLink tick
    assert window.item("card")["x"] == 70

    window.apply({"op": "layer.rename", "target": ["title"], "args": {"name": "Hello"}}, Who.person("sam"))
    on_disk = Document.open(window.folder, "main", KIND)                 # nobody pressed Save
    assert on_disk.item("card")["x"] == 70 and on_disk.item("title")["name"] == "Hello"


def test_rename_keeps_the_work_and_refuses_a_taken_name(tmp_path, monkeypatch):
    """Clicking the name to rename: the window reopens the renamed folder live with every step; a taken name is
    refused and nothing moves."""
    monkeypatch.setenv("ROSTRUM_PROJECTS_DIR", str(tmp_path))
    files = files_in(tmp_path)
    for name in ("Promo", "Taken"):
        files.kind.blank(tmp_path / name)
    assert files.openPath(str(tmp_path / "Promo"))
    files.host.shown.apply({"op": "layer.move", "target": ["card"], "args": {"x": 40}}, Who.person("sam"))
    import pytest
    from rostrum_core import RostrumError
    with pytest.raises(RostrumError):                    # no window to say it in: the refusal is raised
        files.rename("Taken")
    assert (tmp_path / "Promo").is_dir()
    assert files.rename("Promo final")
    window = files.host.shown
    assert Path(window.folder).name == "Promo final" and not (tmp_path / "Promo").exists()
    assert window.live is not None and window.item("card")["x"] == 40 and window.history.changes
