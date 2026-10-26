"""A 2D file holding a plugin's layer opens (not "damaged"), keeps it on save, and the engine's scene leaves it out."""
import json

from rostrum_core import Document, Who
from rostrum_core.storage import canonical, paths

from rostrum2d import KIND, run_source, scene

PART = {"id": "wig1", "type": "wiggle:generator", "wiggle:amount": 3}


def test_a_plugin_layer_opens_is_kept_and_never_drawn(tmp_path):
    d = Document.new(KIND)
    d.run_script("a.py", run_source('comp("film", duration=2)\ntext("hi", body="Hi")\n', "a.py"))
    d.folder, d.item_id = tmp_path, "film"
    d.save()
    p = paths(tmp_path, "film", KIND.ext)
    f = json.loads(p["doc"].read_text(encoding="utf-8"))
    f["doc"]["comps"][0]["layers"] += [PART]
    p["doc"].write_text(json.dumps(f), encoding="utf-8")
    d = Document.open(tmp_path, "film", KIND)
    d.apply([{"op": "text.set", "target": "hi", "args": {"body": "Bye"}}], Who.person("sam"))
    d.save()
    assert canonical(json.loads(p["doc"].read_text(encoding="utf-8"))["doc"]["comps"][0]["layers"][-1]) == canonical(PART)
    assert "wiggle" not in json.dumps(scene.describe(d.data))
