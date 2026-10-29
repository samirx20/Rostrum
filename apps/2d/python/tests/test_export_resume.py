"""A long export whose engine dies is restarted and goes on from the part it was on (engine_export.py): the parts
already drawn are not drawn again, the progress is the whole export's with a time left, and the parts are joined.
Undertow, 2026-10-29: an engine that ended at frame 600 of 900 lost the whole export."""
import json
import subprocess
import sys

from rostrum2d import engine as engine_mod, engine_export
from rostrum2d.engine import Engine

FAKE = r"""
import json, os, sys
log, dies = sys.argv[1], sys.argv[2]
for line in sys.stdin:
    req = json.loads(line)
    if "export" in req:
        r = req["export"]
        open(log, "a").write(json.dumps([r["start"], r["end"], r["file"]]) + "\n")
        n = round((r["end"] - r["start"]) * 10)
        for i in range(1, n + 1):
            if r["start"] > 0 and not os.path.exists(dies):     # the second part: the engine dies once, mid-part
                open(dies, "w").close()
                os._exit(3)
            print(json.dumps({"progress": i, "of": n, "elapsedS": 0.1 * i, "leftS": 1.0}), flush=True)
        open(r["file"], "w").write(f"{r['start']}-{r['end']}")
        print(json.dumps({"ok": True, "frames": n, "timing": {"paintS": 1.0, "maxMs": 5.0}}), flush=True)
    else:
        print(json.dumps({"ok": True}), flush=True)
"""


def test_a_dead_engine_is_restarted_and_the_export_goes_on_from_its_part(tmp_path, monkeypatch):
    fake, log, dies = tmp_path / "fake_engine.py", tmp_path / "log.txt", tmp_path / "died"
    fake.write_text(FAKE)
    real = subprocess.Popen
    monkeypatch.setattr(engine_mod.subprocess, "Popen", lambda args, **kw: real([sys.executable, str(fake), str(log), str(dies)], **kw))
    monkeypatch.setattr(engine_export, "PART_FRAMES", 4)
    joined = []
    monkeypatch.setattr(engine_export, "_join", lambda parts, file: joined.append([open(p).read() for p in parts]))
    eng = Engine(exe=fake)
    try:
        eng.scene = {"comp": {"props": {"fps": 10, "duration": 1.0, "width": 64, "height": 64}}}
        seen = []
        out = tmp_path / "a.partial.mp4"
        reply = eng.export({"start": 0.0, "end": 1.0, "file": str(out), "encode": {"program": "x", "args": ["encode-mp4", str(out)]}},
                           lambda done, of, note: seen.append((done, of, note)))
    finally:
        eng.close()
    asked = [json.loads(x) for x in log.read_text().splitlines()]
    assert [(round(a * 10), round(b * 10)) for a, b, _ in asked] == [(0, 4), (4, 8), (4, 8), (8, 10)], "only the part it died in is drawn again"
    assert asked[1][2] != asked[2][2], "the retry writes its own file"
    assert reply["frames"] == 10 and reply["restarts"] == 1 and "restarted" in reply["warning"]
    assert reply["timing"]["paintS"] == 3.0
    assert len(joined) == 1 and len(joined[0]) == 3
    assert seen[-1][:2] == (10, 10) and all(of == 10 for _, of, _ in seen)
    assert "left" in seen[0][2]
    assert not list(tmp_path.glob("*.part*")), "no part left behind"


FAKE_SAVES = r"""
import json, os, sys
log, dies = sys.argv[1], sys.argv[2]
for line in sys.stdin:
    req = json.loads(line)
    if "export" in req:
        r = req["export"]
        open(log, "a").write(json.dumps([r["start"], [s["end"] for s in r["saves"]]]) + "\n")
        n = round((r["end"] - r["start"]) * 10)
        saves = {s["end"]: s["file"] for s in r["saves"]}
        for i in range(1, n + 1):
            if i == 5 and not os.path.exists(dies):              # dies once in the third file, two saved
                open(dies, "w").close()
                os._exit(3)
            print(json.dumps({"progress": i, "of": n, "elapsedS": 0.1 * i, "leftS": 1.0}), flush=True)
            if i in saves:
                open(saves[i], "w").write("whole")
        print(json.dumps({"ok": True, "frames": n, "timing": {"paintS": 1.0}}), flush=True)
    else:
        print(json.dumps({"ok": True}), flush=True)
"""


def test_a_dead_engine_goes_on_from_the_first_segment_not_saved(tmp_path, monkeypatch):
    """A request that saves a file at each cut (export_cache.py) is one request; after a restart it goes on from the first
    file not there, the files saved before the engine died kept."""
    fake, log, dies = tmp_path / "fake_engine.py", tmp_path / "log.txt", tmp_path / "died"
    fake.write_text(FAKE_SAVES)
    real = subprocess.Popen
    monkeypatch.setattr(engine_mod.subprocess, "Popen", lambda args, **kw: real([sys.executable, str(fake), str(log), str(dies)], **kw))
    monkeypatch.setattr(engine_export, "PART_FRAMES", 4)              # never cuts a request with saves into parts
    eng = Engine(exe=fake)
    files = [tmp_path / f"seg{k}.mp4" for k in range(5)]
    try:
        eng.scene = {"comp": {"props": {"fps": 10, "duration": 1.0, "width": 64, "height": 64}}}
        reply = eng.export({"start": 0.0, "end": 1.0, "file": str(files[-1]), "encode": {"program": "x", "args": ["encode-mp4", str(files[-1])]},
                            "saves": [{"end": 2 * (k + 1), "file": str(f)} for k, f in enumerate(files)]})
    finally:
        eng.close()
    asked = [json.loads(x) for x in log.read_text().splitlines()]
    assert asked == [[0.0, [2, 4, 6, 8, 10]], [0.4, [2, 4, 6]]], "on from frame 4, the two files saved kept"
    assert reply["frames"] == 10 and reply["restarts"] == 1
    assert all(f.read_text() == "whole" for f in files)
