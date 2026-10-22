"""The installer must never ship a GPL package: notices.py stops, names it, and LGPL is let through."""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(tmp_path: Path, licence: str):
    info = tmp_path / "site" / "thing-1.0.dist-info"
    info.mkdir(parents=True)
    (info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: thing\nVersion: 1.0\nLicense-Expression: {licence}\n", encoding="utf-8")
    attr = tmp_path / "ATTRIBUTIONS.md"
    attr.write_text("| Name |\n|---|\n", encoding="utf-8")
    return subprocess.run([sys.executable, str(HERE / "notices.py"), "--app", "2d", "--attributions", str(attr),
                           "--site-packages", str(tmp_path / "site"), "--out", str(tmp_path / "n.json")],
                          capture_output=True, text=True)


def test_gpl_package_stops_the_run(tmp_path):
    r = run(tmp_path, "GPL-3.0-or-later")
    assert r.returncode == 1 and "thing" in r.stderr


def test_lgpl_package_passes(tmp_path):
    assert run(tmp_path, "LGPL-3.0-or-later").returncode == 0


def test_a_licence_saying_what_it_is_not_passes(tmp_path):
    assert run(tmp_path, "MIT; none GPL / AGPL").returncode == 0
    assert run(tmp_path / "b", "GPL-2.0, not LGPL").returncode == 1
