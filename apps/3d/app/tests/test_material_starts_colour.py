"""Every material starting point offers its Base colour in the item's inline material rows (CL7's eye: a Glossy
material has to be made black). A start that switched Base colour off (an image in its values, a when-rule) would
leave a person no way to colour it."""
from rostrum_core import Document, Who
from rostrum_gui import rows, sections

from rostrum3d import KIND, run_source
from rostrum3d.material_starts import STARTS

SAM = Who.person()


def test_every_start_shows_base_colour():
    d = Document.new(KIND)
    d.run_script("s.py", run_source('mesh("e", shape="sphere", radius=0.01)\n', "s.py"))
    static = sections.layout(d.kind.registry.field_op("material"), "material")
    missing = []
    for key in STARTS:
        d.apply({"op": "material.from", "args": {"start": key, "to": ["e"]}}, SAM)
        mat = d.item(d.item("e")["material"])
        shown = {r["id"] for r in rows.evaluate(static, mat, {}, False) if r.get("row") == "param" and r.get("holds")}
        if "baseColor" not in shown:
            missing.append(key)
    assert missing == []
