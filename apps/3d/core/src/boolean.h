// Live booleans (ENGINE_CONTRACT.md § 2, `combine`): solids joined, cut or overlapped with Manifold
// (third_party/manifold). Every input must be a closed solid; an empty result is an error, never an
// empty mesh.
#pragma once
#include <string>
#include <vector>

#include <pxr/base/gf/matrix4d.h>

#include "primitives.h"

namespace r3d {

struct Solid {
  MeshData mesh;
  PXR_NS::GfMatrix4d xform;  // places the mesh in the combine's space (row vectors, as USD)
  std::string id;            // named in errors
};

enum class CombineOp { Union, Subtract, Intersect };

// Union: all joined. Subtract: the first minus all the rest. Intersect: only what every input shares.
// The result has per-vertex normals, face-varying st and triangles only. Throws r3d::Error at `where`.
MeshData combine_solids(const std::vector<Solid>& solids, CombineOp op, const std::string& where);

}  // namespace r3d
