"""contrib.find lists built-in, then the person's, then each plugin's files; a missing folder is empty."""
from rostrum_core import contrib


def test_find_orders_builtin_user_then_plugins(tmp_path, monkeypatch):
    home, built = tmp_path / "home", tmp_path / "built"
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(home))
    for rel in ("built/b.json", "home/brushes/u.json", "home/plugins/zed/brushes/z.json",
                "home/plugins/abc/brushes/a.json", "home/plugins/abc/packs/other.json"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{}")
    got = [(e.path.name, e.origin) for e in contrib.find("brushes", builtin=built)]
    assert got == [("b.json", "builtin"), ("u.json", "user"), ("a.json", "plugin:abc"), ("z.json", "plugin:zed")]
    assert contrib.find("materials") == [] and contrib.find("brushes", builtin=tmp_path / "nope")[0].origin == "user"
