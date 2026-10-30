"""The shared cache never shows a half-made entry and stays under its cap; a child's valid_when can ask its parent."""
import pytest

from rostrum_core import DocKind, Document, Param, Registry, RostrumError, Who
from rostrum_core.cache import Cache, cache_key


def test_cache_key_carries_engine_version():
    a = cache_key("track", "rostrum-track@3", ["abc"], {"from": 1})
    assert a != cache_key("track", "rostrum-track@4", ["abc"], {"from": 1})
    with pytest.raises(ValueError):
        cache_key("track", "rostrum-track", ["abc"])


def test_failed_job_leaves_nothing_and_cap_trims_oldest(tmp_path):
    now = [1000.0]
    c = Cache(tmp_path, cap=250, clock=lambda: now[0])

    def boom(tmp):
        (tmp / "half.bin").write_bytes(b"x" * 10)
        raise RuntimeError("engine crashed")
    with pytest.raises(RuntimeError):
        c.put("k", "bad", boom)
    assert c.get("k", "bad") is None and not list((tmp_path / "k").iterdir())

    for n in range(3):                       # 100 bytes each, an hour apart: the oldest goes past the cap
        now[0] += 3600
        c.put("k", f"e{n}", lambda tmp: (tmp / "f.bin").write_bytes(b"x" * 100))
    c.settle()                               # the trim runs aside, off the caller's thread
    assert c.get("k", "e0") is None and c.get("k", "e1") and c.get("k", "e2")


def test_child_valid_when_sees_parent():
    reg = Registry()

    @reg.operation("note.set", "Set a note.", target="note", params=[
        Param.number("bend", valid_when={"fact": "bendable"}, default=0)])
    def _set(ctx, target, args):
        for t in target:
            ctx.set(t, "bend", args["bend"])

    def facts(item, doc):
        parent = doc.parent(item) if doc else None
        return {"bendable": bool(parent and parent.get("instrument") == "synth")}
    kind = DocKind("t", ".t", reg, lists={"doc": ["tracks"], "track": ["notes"]}, facts=facts)
    data = {"id": "root", "type": "doc", "tracks": [
        {"id": "t1", "type": "track", "instrument": "synth", "notes": [{"id": "n1", "type": "note"}]},
        {"id": "t2", "type": "track", "instrument": "drums", "notes": [{"id": "n2", "type": "note"}]}]}
    doc = Document(kind, data)
    who = Who.person("sam")
    doc.apply({"op": "note.set", "target": "n1", "args": {"bend": 2}}, who)
    assert doc.item("n1")["bend"] == 2
    with pytest.raises(RostrumError):
        doc.apply({"op": "note.set", "target": "n2", "args": {"bend": 2}}, who)


def test_entry_missing_a_file_is_made_again(tmp_path):
    """A clean-up from outside (a person's disk sweep) can delete an entry's files but leave entry.json: that is a miss,
    and put makes it again, never an error later when the file is read."""
    c = Cache(tmp_path)
    folder = c.put("k", "e", lambda tmp: (tmp / "picture.npy").write_bytes(b"x" * 10))
    (folder / "picture.npy").unlink()
    assert c.get("k", "e") is None
    again = c.put("k", "e", lambda tmp: (tmp / "picture.npy").write_bytes(b"y" * 10))
    assert (again / "picture.npy").read_bytes() == b"y" * 10
