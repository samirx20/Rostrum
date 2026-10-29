"""Automatic masks (paint_masks.py): worked out from a surface's own shape on its unfolded picture (Edges bright along a
box's edges and dark mid-face, Facing up on its top only, Cavities in an inside corner, Thin parts on a plate), and a
filled layer with a mask paints only where the mask is. Shapes are unit cubes put together, each triangle its own
square of the picture (any unfolding will do)."""
import numpy as np
from rostrum_core import Document, Who

from rostrum3d import KIND, paint_masks, paint_scene, run_source, unfold
from rostrum3d.uv_raster import Geo

SIZE = 256


def _cubes(cells, scale=(1.0, 1.0, 1.0)):
    """The outside faces of unit cubes at `cells` (scaled), as {points, faceCounts, faceIndices} and uvs: each face's
    two triangles in a square of a grid over the picture, a little apart."""
    cells, sx = set(cells), np.asarray(scale)
    quads = []
    for c in cells:
        for ax in range(3):
            for sgn in (1, -1):
                n = [0, 0, 0]
                n[ax] = sgn
                if tuple(np.add(c, n)) in cells:
                    continue
                u, v = (ax + 1) % 3, (ax + 2) % 3                     # u × v = +ax
                if sgn < 0:
                    u, v = v, u                                     # outward winding
                base = np.add(c, [0.5 + 0.5 * sgn if a == ax else 0 for a in range(3)])
                corner = lambda du, dv: (base + np.eye(3)[u] * du + np.eye(3)[v] * dv) * sx  # noqa: E731
                quads.append([corner(0, 0), corner(1, 0), corner(1, 1), corner(0, 1)])
    n = int(np.ceil(np.sqrt(len(quads))))
    pts, idx, uvs = [], [], []
    for k, q in enumerate(quads):
        cx, cy = k % n, k // n
        for (a, b) in ((0, 0), (1, 0), (1, 1), (0, 1)):
            uvs += [(cx + 0.1 + 0.8 * a) / n, (cy + 0.1 + 0.8 * b) / n]
        idx += list(range(len(pts), len(pts) + 4))
        pts += [list(p) for p in q]
    return {"points": sum(pts, []), "faceCounts": [4] * len(quads), "faceIndices": idx}, uvs, n


def _at(n, k, a, b, shape):
    """The texel at (a, b) (0..1 across) of face k's square."""
    x = ((k % n) + 0.1 + 0.8 * a) / n * SIZE
    y = (1 - ((k // n) + 0.1 + 0.8 * b) / n) * SIZE
    return shape[min(SIZE - 1, int(y)), min(SIZE - 1, int(x))]


def test_box_edges_and_facing_up():
    geo, uvs, n = _cubes([(0, 0, 0)])
    m = paint_masks.compute(Geo.of_mesh(geo, uvs), SIZE)
    order = [(ax, sgn) for ax in range(3) for sgn in (1, -1)]              # faces as _cubes made them
    for k, face in enumerate(order):
        assert _at(n, k, 0.5, 0.5, m["edges"]) < 20                        # mid-face: flat
        assert _at(n, k, 0.02, 0.5, m["edges"]) > 100                      # along an edge
        top = face == (1, 1)
        assert (_at(n, k, 0.5, 0.5, m["up"]) > 250) == top
    assert m["cavities"].max() < 20 and m["thin"].max() < 20             # a box has no hollows and is thick


def test_cavity_in_an_inside_corner_and_thin_plate():
    geo, uvs, n = _cubes([(0, 0, 0), (1, 0, 0), (0, 1, 0)])                # an L: an inside corner at x = y = 1
    m = paint_masks.compute(Geo.of_mesh(geo, uvs), SIZE)
    assert m["cavities"].max() > 150 and m["edges"].max() > 150
    pts = np.asarray(geo["points"]).reshape(-1, 3)[np.asarray(geo["faceIndices"])].reshape(-1, 4, 3).mean(1)
    k = int(np.argmin(np.linalg.norm(pts - [1.5, 1.0, 0.5], axis=1)))      # the face lying in the inside corner
    assert _at(n, k, 0.5, 0.02, m["cavities"]) > 100 and _at(n, k, 0.5, 0.5, m["cavities"]) < 20   # at x = 1
    plate, puv, _ = _cubes([(x, 0, z) for x in range(3) for z in range(3)], (1, 0.03, 1))
    assert np.median(paint_masks.compute(Geo.of_mesh(plate, puv), SIZE)["thin"][
        paint_masks.compute(Geo.of_mesh(plate, puv), SIZE)["up"] > 250]) > 150


def test_a_filled_layer_with_a_mask_paints_only_there(tmp_path):
    geo, uvs, n = _cubes([(0, 0, 0)])
    unfold.use_unfold(lambda doc, id_, size: {"uvs": uvs, "geometry": geo})
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("s.py", run_source('mesh("box", shape="box")\n', "s.py"))
    d.apply({"op": "mesh.unfold", "target": ["box"]}, Who.person())
    d.apply({"op": "paint.add", "target": ["box"], "args": {"id": "dust", "channel": "colour", "fill": True,
                                                            "fillColor": "#d0d0d0", "shapeMask": "up"}}, Who.person())
    d.apply({"op": "paint.set", "target": ["dust"], "args": {"maskSpread": 0.6}}, Who.person())
    item = {**d.item("box"), "paintSize": SIZE}
    masked, keys = paint_scene._masked(item, None, SIZE)
    a = paint_scene._paint_rgba(paint_scene._filled(item), SIZE, {}, masked)[..., 3]
    top = [(ax, sgn) for ax in range(3) for sgn in (1, -1)].index((1, 1))
    assert _at(n, top, 0.5, 0.5, a) > 250                                  # dust on top
    assert all(_at(n, k, 0.5, 0.5, a) < 5 for k in range(6) if k != top)  # none on the sides or underneath
    from rostrum3d.mcp import paint_canvas                              # the agents' flat look matches the render
    look = paint_canvas.picture({**paint_scene._filled(item), "splats": {}, "kept": item, "surface": None}, SIZE)
    assert (look[..., 3] == a).all()
    assert paint_masks.shape_known(item) and paint_masks.unpainted(item)   # filled, no strokes: nothing to move
    assert not paint_masks.shape_known({**item, "uvs": [0.5, 0.5] * 24})   # unfolded before masks: not kept
    d.undo(Who.person())
    assert d.item("dust")["maskSpread"] == 0.5                             # each change one undo step
