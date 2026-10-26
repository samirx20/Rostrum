"""What the plain instrument names must never get wrong silently: an old song's kit still opens, the perform field reaches the
engine only when the document holds it, and a sample pack that fails its fingerprint is never installed."""
import copy
import json
import zipfile

import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND, compile, packs, packs_catalog as cat, packs_fetch as fetch, run_source

OLD = {"id": "root", "type": "doc", "tempo": 120, "tracks": [
    {"id": "d", "type": "track", "instrument": "kit", "kit": "synth", "volume": 0.8,
     "hits": [{"id": "h1", "type": "hit", "drum": "cymbal", "at": 0, "vel": 0.8}]}], "master": []}


def test_an_old_songs_kit_synth_opens_as_drums():
    data, _ = KIND.migrate(copy.deepcopy(OLD), 1)
    assert data["tracks"][0]["kit"] == "drums"


def test_an_old_songs_bass_moves_down_an_octave_so_it_sounds_as_before():
    old = copy.deepcopy(OLD)
    old["tracks"] = [{"id": "b", "type": "track", "instrument": "builtIn", "builtIn": "electricBass", "notes": [
                         {"id": "n1", "type": "note", "pitch": "Bb2", "at": 0, "dur": 1},
                         {"id": "n2", "type": "note", "pitch": ["E2", 47], "at": 1, "dur": 1}]},
                     {"id": "u", "type": "track", "instrument": "builtIn", "builtIn": "uprightBass", "notes": [
                         {"id": "n3", "type": "note", "pitch": "E2", "at": 0, "dur": 1}]}]
    data, _ = KIND.migrate(old, 6)
    assert [n["pitch"] for n in data["tracks"][0]["notes"]] == ["Bb1", ["E1", 35]]
    assert data["tracks"][1]["notes"][0]["pitch"] == "E2"


def _sent(source):
    doc = Document.new(KIND)
    doc.run_script("t.py", run_source(source, "t.py"), Who.script("t.py"))
    return {t["id"]: t for t in compile(doc.data)["tracks"]}


def test_perform_reaches_the_engine_only_when_the_document_holds_it():
    sent = _sent("a = track('a', builtIn='piano'); b = track('b', builtIn='piano', perform=False)\n"
                 "c = track('c', builtIn='piano', perform={'timing': 4}); [t.note('C4', at=0, dur=1) for t in (a, b, c)]")
    assert "perform" not in sent["a"] and sent["b"]["perform"] is False and sent["c"]["perform"] == {"timing": 4}


@pytest.fixture
def toy(tmp_path, monkeypatch):
    """A one-file pack served from a local zip: no network."""
    monkeypatch.setenv("ROSTRUM_ASSETS_DIR", str(tmp_path / "assets"))
    zpath = tmp_path / "toy.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("Audio/click.ogg", b"not really audio")
        z.writestr("readme.txt", b"left out")
    spec = {"id": "toy", "title": "Toy", "author": "me", "group": "sfx", "license": "CC0", "page": "x",
            "zip": {"url": "file://toy", "sha256": fetch.sha256_of(zpath), "bytes": zpath.stat().st_size}}
    monkeypatch.setattr(cat, "catalog", lambda: {"toy": spec})
    monkeypatch.setattr(fetch, "download", lambda url, to, what, note=None: to.write_bytes(zpath.read_bytes()))
    return spec


def test_a_pack_installs_its_files_records_them_and_verifies(toy, tmp_path):
    assert packs.install("toy")["installed"] and packs.state("toy")[0] == "installed"
    rec = json.loads((tmp_path / "assets" / "assets.json").read_text())["sounds:toy"]
    assert [f["path"] for f in rec["files"]] == ["Audio/click.ogg"] and len(rec["files"][0]["sha256"]) == 64
    assert packs.verify("toy")["ok"]
    (tmp_path / "assets" / "sounds" / "toy" / "Audio" / "click.ogg").write_bytes(b"changed")
    assert not packs.verify("toy")["ok"]


def test_a_download_that_fails_its_fingerprint_is_deleted_and_nothing_is_installed(toy, tmp_path):
    toy["zip"]["sha256"] = "0" * 64
    with pytest.raises(RostrumError, match="fingerprint"):
        packs.install("toy")
    assert packs.state("toy")[0] == "missing" and not (tmp_path / "assets" / ".install-toy").exists()
    assert not list((tmp_path / "assets" / "sounds").rglob("*.ogg"))


def test_every_listed_instruments_preview_lies_in_its_range():
    """The Library's preview of a recorded instrument plays only notes it has (critic r11: the clarinet, vibraphone and
    flute previews were refused for C3, so they seemed missing)."""
    from rostrum_sound import audition, names, roles
    from rostrum_sound.doc import keys
    for name in (n for g in names.BUILT_IN_GROUPS.values() for n in g):
        role = roles.ROLES[f"builtIn:{name}"]
        if not role.low:
            continue
        song = audition._song({"instrument": "builtIn", "builtIn": name}, "instrument", [], None).tree()
        heard = [m for n in song["tracks"][0]["notes"] for m in keys.midis(n["pitch"])]
        assert keys.midi(role.low) <= min(heard) and max(heard) <= keys.midi(role.high), name
