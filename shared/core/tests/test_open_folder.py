"""run_open_project's one shared path (rostrum_core/mcp/open_folder.py), which every app's tool uses: a folder that
isn't there yet is made, and a refused call makes nothing."""
from types import SimpleNamespace

import pytest

from rostrum_core.errors import RostrumError
from rostrum_core.mcp.open_folder import open_folder


def call(tmp_path, args):
    opened = []
    app = SimpleNamespace(folder=None, documents={})

    def open_project(app, folder, items):
        app.folder, app.documents = folder, {i: None for i in items}
        opened.append(folder)
    reply = open_folder(SimpleNamespace(app=app), args, docs_in=lambda f: [], word="song",
                        default_item=lambda f, explicit: "song", open_project=open_project)
    return reply, opened


def test_a_new_folder_is_made_and_a_refused_call_makes_nothing(tmp_path):
    with pytest.raises(RostrumError):
        call(tmp_path, {"folder": str(tmp_path / "x" / "bad"), "item": "a b"})
    assert not (tmp_path / "x").exists()
    reply, opened = call(tmp_path, {"folder": str(tmp_path / "new" / "piece")})
    assert (tmp_path / "new" / "piece").is_dir() and opened and "Made the folder" in reply.summary
