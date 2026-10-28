"""A material's blocks graph (brief 23): what would break silently. Wire rules (kinds, one wire per input, no loops),
each graph op one undo step (stylized switches with it), the MaterialX document and the Rostrum library agree with
each other and with MaterialX's standard library (names and types, so USD's reader and Storm's generator accept them),
the library file matches its generator, compile writes the document by its content and points the scene at it, and a
stylized block wired into Style switches its setting on."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum3d import KIND, compile as C, graph, graph_mtlx

SAM = Who.person()
APP = Path(__file__).resolve().parents[2]
STDLIB = Path.home() / ".rostrum/libs/3d/5.2.2-cycles-a456b76-r4/runtime/usd/lib/usd/usdMtlx/resources/libraries/stdlib/stdlib_defs.mtlx"


def _doc():
    d = Document.new(KIND)
    d.apply([{"op": "material.add", "args": {"id": "ball"}},
             {"op": "mesh.add", "args": {"id": "a", "shape": "sphere", "material": "ball"}},
             {"op": "camera.add", "args": {"id": "cam", "z": 2}},
             {"op": "shot.add", "args": {"id": "hero", "camera": "cam", "start": 0, "end": 1}}], SAM)
    return d


def _op(d, op, **args):
    return d.apply({"op": op, "target": ["ball"], "args": args}, SAM)


def _big(d):
    for t in ("noise", "mix", "ramp", "curve", "colourAdjust", "image", "bevel", "occlusion", "lines", "halftone"):
        _op(d, "graph.add", type=t)
    for f, t in [("noise_1.colour", "mix_1.b"), ("noise_1.value", "ramp_1.factor"), ("ramp_1.colour", "mix_1.a"),
                 ("mix_1.colour", "colourAdjust_1.colour"), ("colourAdjust_1.colour", "surface.baseColor"),
                 ("curve_1.value", "surface.roughness"), ("image_1.colour", "curve_1.value"),
                 ("occlusion_1.colour", "surface.metallic"), ("noise_1.value", "surface.emissionColor"),
                 ("bevel_1.normal", "surface.normal"), ("halftone_1.style", "lines_1.then"), ("lines_1.style", "surface.style")]:
        _op(d, "graph.connect", **{"from": f, "to": t})


def test_wire_rules():
    d = _doc()
    _op(d, "graph.add", type="noise")
    _op(d, "graph.add", type="colourAdjust")
    _op(d, "graph.add", type="bevel")
    for frm, to, said in [("noise_1.value", "surface.normal", "joins a number"),
                          ("bevel_1.normal", "surface.baseColor", "joins a normal"),
                          ("noise_1.valu", "surface.roughness", "is not an output"),
                          ("noise_1.value", "noise_1.scale", "loop")]:
        with pytest.raises(RostrumError, match=said):
            _op(d, "graph.connect", **{"from": frm, "to": to})
    _op(d, "graph.connect", **{"from": "noise_1.value", "to": "colourAdjust_1.colour"})      # number → colour: grey
    with pytest.raises(RostrumError, match="loop"):
        _op(d, "graph.connect", **{"from": "colourAdjust_1.colour", "to": "noise_1.scale"})  # colour → number, but a loop
    _op(d, "graph.connect", **{"from": "colourAdjust_1.colour", "to": "surface.roughness"})
    _op(d, "graph.connect", **{"from": "noise_1.value", "to": "surface.roughness"})          # replaces the old wire
    assert [w["to"] for w in d.item("ball")["blocks"]["wires"]].count("surface.roughness") == 1
    with pytest.raises(RostrumError, match="taken"):
        _op(d, "graph.add", type="noise", id="noise_1")
    assert graph.problems(d.item("ball")) == []


def test_each_op_is_one_undo_step():
    d = _doc()
    before = dict(d.item("ball"))
    _op(d, "graph.add", type="noise", values={"scale": 8})
    _op(d, "graph.add", type="lines", values={"linesWidth": 3})
    _op(d, "graph.connect", **{"from": "lines_1.style", "to": "surface.style"})
    assert d.item("ball")["lines"] is True and d.item("ball")["linesWidth"] == 3
    _op(d, "graph.remove", blocks=["lines_1"])
    assert d.item("ball")["lines"] is False                    # taken out: switched off, in the same step
    d.undo(SAM)
    assert d.item("ball")["lines"] is True and len(d.item("ball")["blocks"]["blocks"]) == 2
    d.undo(SAM)
    assert d.item("ball")["lines"] is False and d.item("ball")["blocks"]["wires"] == []
    d.undo(SAM)
    d.undo(SAM)
    assert dict(d.item("ball")) == before                      # back to no graph at all


def _defs(path: Path) -> dict:
    """{nodedef name: (node, {input: type}, {output: type})}."""
    out = {}
    for nd in ET.parse(path).getroot().iter("nodedef"):
        out[nd.get("name")] = (nd.get("node"), {i.get("name"): i.get("type") for i in nd.iter("input")},
                               {o.get("name"): o.get("type") for o in nd.iter("output")})
    return out


def _find(defs: dict, node: str, type_: str, inputs: dict):
    """The nodedef a node of this category, output type and inputs resolves to (as MaterialX picks it), else None."""
    for name, (cat, ins, outs) in defs.items():
        if cat == node and (type_ in outs.values() or (type_ == "multioutput" and len(outs) > 1)) and all(ins.get(k) == t for k, t in inputs.items()):
            return name
    return None


def _check_nodes(parent, defs: dict, where: str, interface: dict | None = None):
    for el in parent:
        if el.tag in ("input", "output", "nodedef", "nodegraph", "typedef"):
            continue
        ins = {i.get("name"): i.get("type") for i in el.findall("input")}
        assert _find(defs, el.tag, el.get("type"), ins), f"{where}: <{el.tag} {el.get('name')} type={el.get('type')}> {ins}"
        for i in el.findall("input"):
            if interface is not None and i.get("interfacename"):
                assert i.get("interfacename") in interface, f"{where}.{el.get('name')}: no interface input {i.get('interfacename')}"


@pytest.mark.skipif(not STDLIB.is_file(), reason="the 3D runtime's MaterialX library is not on this machine")
def test_library_and_document_check_against_materialx(tmp_path):
    sys.path.insert(0, str(APP / "tools"))
    import make_blocks_mtlx as M
    lib = APP / "core/mtlx/rostrum_blocks.mtlx"
    sty = APP / "stylized/mtlx/rostrum_stylized.mtlx"
    assert lib.read_text(encoding="utf-8") == M.blocks_library()      # run tools/make_blocks_mtlx.py after a change
    assert sty.read_text(encoding="utf-8") == M.stylized_library()
    std, ours, styl = _defs(STDLIB), _defs(lib), _defs(sty)
    coded = {i.get("nodedef") for i in ET.parse(lib).getroot().iter("implementation") if i.get("target") == "genglsl"}
    assert all((lib.parent / i.get("file")).is_file() for i in ET.parse(lib).getroot().iter("implementation"))
    usable = {**std, **{k: v for k, v in ours.items() if k in coded}}  # stdlib nodes, or ours with Storm's GLSL beside them
    for ng in ET.parse(lib).getroot().iter("nodegraph"):                # our nodegraphs use only nodes Storm can draw
        _, iface, outs = ours[ng.get("nodedef")]
        _check_nodes(ng, usable, ng.get("name"), iface)
        assert {o.get("name") for o in ng.findall("output")} == set(outs)
    d = _doc()
    _big(d)
    root = ET.fromstring(graph_mtlx.document(d.item("ball")))
    assert root.get("version") == "1.39"
    ng = root.find("nodegraph[@name='NG_blocks']")
    _check_nodes(ng, ours, "NG_blocks")
    names = {el.get("name"): el for el in ng if el.tag not in ("input", "output")}
    for el in ng.iter("input"):                                         # every link lands on a real node output
        if el.get("nodename"):
            src = names[el.get("nodename")]
            nd = _find(ours, src.tag, src.get("type"), {})
            assert el.get("output") in ours[nd][2], f'{el.get("nodename")}.{el.get("output")}'
    assert {o.get("name") for o in ng.findall("output")} == {"baseColor", "roughness", "metallic", "emissionColor", "normal"}
    prev = root.find("UsdPreviewSurface")
    assert {i.get("output") for i in prev} == {o.get("name") for o in ng.findall("output")}
    assert root.find("surfacematerial").get("name") == "M_ball"
    for el in root:
        if el.get("type") == "rostrum_style":
            assert _find(styl, el.tag, "rostrum_style", {i.get("name"): i.get("type") for i in el.findall("input")})


def test_compile_writes_the_document_by_content(tmp_path):
    d = _doc()
    scene = C.describe(d.data, "hero", tmp_path)
    assert "blocks" not in next(m for m in scene["materials"] if m["id"] == "ball")["props"]    # no graph, no document
    _op(d, "graph.add", type="noise", values={"scale": 8})
    _op(d, "graph.connect", **{"from": "noise_1.value", "to": "surface.roughness"})
    first = Path(next(m for m in C.describe(d.data, "hero", tmp_path)["materials"] if m["id"] == "ball")["props"]["blocks"])
    assert first.is_file() and first.parent == tmp_path / "blocks" and first.name.startswith("ball-")
    _op(d, "graph.set", block="noise_1", values={"scale": 9})
    second = Path(graph_mtlx.write_document(d.item("ball"), tmp_path))
    assert second != first and second.is_file() and not first.exists()   # a new name per content, the old one gone


def test_a_stylized_block_wired_into_style_is_on(tmp_path):
    d = _doc()
    _op(d, "graph.add", type="noise")
    _op(d, "graph.add", type="lines")
    _op(d, "graph.connect", **{"from": "noise_1.value", "to": "surface.roughness"})
    m = dict(d.item("ball"))
    m["blocks"] = {**m["blocks"], "wires": m["blocks"]["wires"] + [{"from": "lines_1.style", "to": "surface.style"}]}
    m["lines"] = False                                            # a hand-written file: wired, field left off
    data = {**d.data, "materials": [m]}
    props = next(x for x in C.describe(data, "hero", tmp_path)["materials"] if x["id"] == "ball")["props"]
    assert props["lines"] is True and props["halftone"] is False


def test_a_stylized_setting_without_its_block_shows_one():
    d = _doc()
    _op(d, "graph.add", type="halftone")
    _op(d, "graph.connect", **{"from": "halftone_1.style", "to": "surface.style"})
    d.apply({"op": "material.set", "target": ["ball"], "args": {"lines": True}}, SAM)   # as a starting point sets it
    g = graph.graph_of(d.item("ball"))
    assert [b["type"] for b in g["blocks"]] == ["halftone", "lines"]
    assert graph.style_chain(g) == ["halftone_1", "lines_1"] and graph.toggles(g) == {"halftone": True, "lines": True}
    _op(d, "graph.remove", blocks=["lines_1"])                    # taking it out switches Lines off, for good
    assert d.item("ball")["lines"] is False and graph.style_chain(graph.graph_of(d.item("ball"))) == ["halftone_1"]
