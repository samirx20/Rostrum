// Smooth surface for an editable mesh (SPEC §4.3): OpenSubdiv's Catmull-Clark, refined uniformly on the CPU so
// Storm and Cycles draw the very same mesh (preview ≡ export). Sharp edges are infinitely sharp creases.
#pragma once
#include <vector>

#include <pxr/base/gf/vec3f.h>

namespace r3d {

struct PolyCage {
  std::vector<PXR_NS::GfVec3f> points;
  std::vector<int> counts, indices;
  std::vector<int> base_face;  // per face: the face of the original mesh it came from
  std::vector<char> on_crease;  // smoothed only: per point, 1 on a sharp edge (shading breaks only there)
};

// Refines `cage` `level` times (1..3). `creases` are point index pairs a, b, a, b … kept sharp.
PolyCage subdivide(const PolyCage& cage, const std::vector<int>& creases, int level);

}  // namespace r3d
