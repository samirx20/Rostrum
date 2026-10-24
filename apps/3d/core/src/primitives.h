// The core's own shapes (ENGINE_CONTRACT.md § 2, `mesh`). Metres, centred on the origin, Y up.
// Normals are per vertex (Cycles' Hydra delegate ignores face-varying normals): hard edges and flat
// shading come from separate vertices. `st` is face-varying, one UV per face corner, 0..1 per face group
// (side band, top, bottom), and seen from outside a texture is never mirrored.
#pragma once
#include <pxr/base/vt/array.h>
#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3f.h>

namespace r3d {

struct MeshData {
  PXR_NS::VtArray<PXR_NS::GfVec3f> points, normals;
  PXR_NS::VtArray<PXR_NS::GfVec2f> st;  // face-varying: st[k] belongs to indices[k]
  PXR_NS::VtArray<int> counts, indices;
};

// width X, height Y, depth Z; bevel = radius of every edge and corner, segments = steps per 90° of it.
MeshData make_box(float width, float height, float depth, float bevel, int segments, bool smooth);
// segments around; segments / 2 from pole to pole.
MeshData make_sphere(float radius, int segments, bool smooth);
// Axis Y. segments around; the bevel takes max(2, segments / 8) steps.
MeshData make_cylinder(float radius, float height, float bevel, int segments, bool smooth);
// Axis Y, point up: base radius, height from base to point.
MeshData make_cone(float radius, float height, int segments, bool smooth);
// Axis Y: a cylinder with half-sphere ends; height is end to end (at least 2 * radius).
MeshData make_capsule(float radius, float height, int segments, bool smooth);
// In XZ, facing +Y.
MeshData make_plane(float width, float depth);
MeshData make_disc(float radius, int segments);
// Ring in XZ around Y; tube = radius of the tube; segments around the ring, max(3, segments / 2) round the tube.
MeshData make_torus(float radius, float tube, int segments, bool smooth);

}  // namespace r3d
