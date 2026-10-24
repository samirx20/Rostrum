// The `poly` mesh shape (ENGINE_CONTRACT.md § 2): an editable mesh given as points, faceCounts and
// faceIndices (counter-clockwise seen from outside, like USD), in the item's own space.
#pragma once
#include "json_read.h"
#include "primitives.h"

namespace r3d {

// One vertex per face corner (hard edges come from separate vertices, primitives.h). smooth: each corner
// takes the area-weighted average normal of the faces at its point within 30° of its own face; otherwise
// the face's own normal. Faces with more than 4 corners stay n-gons (Hydra triangulates them).
// `subdivide` 1..3 smooths it first (subdivide.h), `creases` staying sharp; the result's base_face maps each
// drawn face to its original one (for `faceMaterials`).
MeshData make_poly(Reader& p, bool smooth);

}  // namespace r3d
