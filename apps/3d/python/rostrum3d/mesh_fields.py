"""A mesh's fields (fields.py): its shape and sizes, an editable mesh's own data, its material, and the shared
transform. A mesh's Shape group is built once (STILL in fields.py).
"""
from __future__ import annotations

import dataclasses

from rostrum_core import Param

from .field_kit import ANY, CH, D, IS, NOT, N, POLY, S, T, TRANSFORM, X
from .outline_fields import FIELDS as OUTLINE_FIELDS, OUTLINE_SHAPES
from .paint_fields import MESH as PAINT_MESH

SHAPES = ["box", "sphere", "cylinder", "cone", "capsule", "plane", "disc", "torus", *OUTLINE_SHAPES]   # what can be added

MESH = [
    dataclasses.replace(CH("shape", [*SHAPES, "poly"], "Shape", "Shape", "box"), labels={"poly": "Editable mesh"}),
    N("width", "Width", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "plane"), default=1.0,
      help="Along X. A plane lies flat, facing up: width (X) × depth (Z)"),
    N("height", "Height", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "cylinder", "cone", "capsule"), default=1.0,
      help="Cone: base to point. Capsule: end to end (at least twice the radius)"),
    N("depth", "Depth", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "box", "plane", *OUTLINE_SHAPES), default=1.0,
      help="Box: along Z. Plane: its other side, along Z (a plane has no height). Text, svg, path2d: how far "
           "the flat outline is pushed out (try 0.02)"),
    N("radius", "Radius", "Shape", 0, 1e4, 0.001, "m", when=ANY("shape", "sphere", "cylinder", "cone", "capsule", "disc", "torus"),
      default=0.5, help="Torus: from its centre to the middle of the ring"),
    N("tube", "Tube radius", "Shape", 0, 1e4, 0.001, "m", when=IS("shape", "torus"), default=0.15),
    *OUTLINE_FIELDS,
    N("bevel", "Bevel", "Shape", 0, 1e3, 0.0005, "m", S, ANY("shape", "box", "cylinder", *OUTLINE_SHAPES),
      help="Rounded edges this wide; real products almost never have razor edges"),
    N("segments", "Segments", "Shape", 1, 256, 1, "", D, {"all": [NOT("shape", "plane"), NOT("shape", "poly")]}, integer=True, default=24,
      help="Box: steps around each bevel. Round shapes: steps around"),
    T("smooth", "Smooth shading", "Shape", True, S, help="Smooth normals; off = flat facets. An editable mesh keeps "
      "edges sharper than 30° hard either way"),
    # An editable mesh's own data (screens never show it as fields; ops_mesh.py changes it). Like USD's mesh.
    Param.points("points", label="Points", group="Mesh data", importance=D, valid_when=POLY, min=3, max=3, default=None, nullable=True,
                 help="[x, y, z] per point, in the item's own space"),
    Param.list("faceCounts", "number", label="Face corners", group="Mesh data", importance=D, valid_when=POLY,
               min=3, max=1000, integer=True, default=[], help="Corners of each face"),
    Param.list("faceIndices", "number", label="Face points", group="Mesh data", importance=D, valid_when=POLY,
               min=0, max=10**7, integer=True, default=[], help="Each face's points, in turn, anticlockwise seen from outside"),
    Param.list("creases", "number", label="Sharp edges", group="Mesh data", importance=D, valid_when=POLY,
               min=0, max=10**7, integer=True, default=[],
               help="Edges that stay sharp when the surface is smoothed, as point pairs a, b, a, b …"),
    Param.list("faceMaterials", "text", label="Face materials", group="Mesh data", importance=D, valid_when=POLY,
               default=[], help='A material id per face ("" = the item\'s); empty = every face the item\'s'),
    N("subdivide", "Smooth surface", "Shape", 0, 3, 1, "", S, POLY, integer=True, default=0,
      help="Rounds the whole mesh (OpenSubdiv Catmull-Clark), 1 to 3 times; sharp edges stay sharp. 0 = off"),
    T("skinned", "Bend with bones", "Bones", True, S, {"fact": "boned"},
      help="The mesh bends with its bone chain (each point follows the bones nearest it). Off: the bones stay but "
           "the mesh keeps its shape"),
    *PAINT_MESH,                    # a mesh is a paint canvas (paint_fields.py)
    X("material", "Material", "Material", "", help='A material id, or "" for none', refers="material"),
    # A mirrored copy (mirror.py): made by mesh.mirror, everything it shows is its original's, through the clay's mirror;
    # an operation's data, never rows (DATA_GROUPS)
    X("mirror", "Mirrored copy of", "Mirror data", "", D, refers="mesh",
      help="This mesh is the mirrored copy of that mesh: its shape, material, keys and place follow it (mesh.mirror)"),
    X("mirrorOn", "Mirrored across", "Mirror data", "", D, NOT("mirror", ""), refers="clay",
      help="The clay whose mirror (its own X = 0 plane) the copy is reflected through"),
] + TRANSFORM
