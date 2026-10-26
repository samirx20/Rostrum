"""A song holding a plugin's parts opens, keeps them on save, and the engine's schedule leaves them out."""
import json

from rostrum_core import Document, Who
from rostrum_core.storage import canonical, paths

from rostrum_sound.compile import compile
from rostrum_sound.doc.kind import KIND

PART = {"id": "wig1", "type": "wiggle:arp", "wiggle:rate": 3}


def test_plugin_parts_open_are_kept_and_never_played(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="song")
    d.apply([{"op": "track.add", "args": {"name": "Keys"}}], Who.person("sam"))
    d.save()
    p = paths(tmp_path, "song", KIND.ext)
    f = json.loads(p["doc"].read_text(encoding="utf-8"))
    f["doc"]["tracks"][0]["effects"] = f["doc"]["tracks"][0].get("effects", []) + [PART]
    f["doc"]["tracks"].append({"id": "pt", "type": "wiggle:track"})
    p["doc"].write_text(json.dumps(f), encoding="utf-8")
    d = Document.open(tmp_path, "song", KIND)
    d.save()
    kept = json.loads(p["doc"].read_text(encoding="utf-8"))["doc"]["tracks"]
    assert canonical(kept[0]["effects"][-1]) == canonical(PART) and kept[1]["type"] == "wiggle:track"
    assert "wiggle" not in json.dumps(compile(d))
