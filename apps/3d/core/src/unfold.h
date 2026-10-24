// Automatic unfolding (xatlas, third_party/xatlas, MIT): a mesh's faces laid flat into one square picture, so it can
// be painted (SPEC §5). The answer is face-varying: one (s, t) per face corner, in the mesh's own face order, the
// same layout as the `st` the core writes (write_mesh) and the `uvs` a mesh item holds.
#pragma once
#include <string>
#include <vector>

#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/vt/array.h>

namespace r3d {

struct Unfolded {
  std::vector<PXR_NS::GfVec2f> st;  // one per face corner; 0..1, t up (USD's st: t = 0 is the picture's bottom row)
  int charts = 0;                   // how many flat pieces the surface was cut into
  float used = 0;                   // share of the picture the pieces cover, 0..1
};

// `size`: the picture's side in pixels (the paint canvas, e.g. 2048); pieces keep a few pixels apart so painting
// near one edge never bleeds into the next piece. Throws r3d::Error (naming `where`) when xatlas can't.
Unfolded unfold_mesh(const PXR_NS::VtArray<PXR_NS::GfVec3f>& points, const PXR_NS::VtArray<int>& counts,
                     const PXR_NS::VtArray<int>& indices, int size, const std::string& where);

}  // namespace r3d
