// Simple bone chains (SPEC §9, brief 19): a mesh bent by its bones, the same in Quick and Final because the
// bent points are written onto the mesh as time samples, which every renderer reads. Weights are automatic
// (from each point's distance to each bone at rest); the bending is USD skel's linear blend skinning.
// CL5: a clay's blocks bend by the same weights (clay_skin.h), so the rule and the `skin` reader live here.
#pragma once
#include <array>
#include <cstddef>
#include <string>
#include <vector>

#include <pxr/base/js/value.h>
#include <pxr/usd/usdGeom/mesh.h>

#include "primitives.h"

namespace r3d {

// One bone's move from rest: [m00, m01, m02, m10, m11, m12, m20, m21, m22, tx, ty, tz], M row by row,
// p_now = M·p_rest + t.
using BoneMove = std::array<double, 12>;

// `skin` (ENGINE_CONTRACT.md § 2, mesh and clay `skin`): {"rest": [[hx,hy,hz, tx,ty,tz] per bone],
// "pose": [[move per bone] per frame]}, all in the item's own space.
struct SkinRig {
  std::vector<std::array<double, 6>> rest;   // each bone's head and tail at rest
  std::vector<std::vector<BoneMove>> pose;   // per frame of the shot (from its start), one move per bone
};

// Read loudly: an empty `rest` or `pose`, a frame without one move per bone, a list that isn't 6 / 12 numbers.
SkinRig read_skin(const PXR_NS::JsObject& skin, const std::string& where);
// one [12 numbers] move; `where` names it in errors
BoneMove read_bone_move(const PXR_NS::JsValue& v, const std::string& where);

// Automatic weights: each point leans on its nearest kSkinMost bones by 1 / distance⁴ to their rest segments,
// normalised. `xyz`: n points, 3 floats each; `idx` / `w`: n × skin_influences(bones) each, filled.
constexpr int kSkinMost = 4;
inline int skin_influences(size_t bones) { return int(bones < size_t(kSkinMost) ? bones : size_t(kSkinMost)); }
void skin_weights(const float* xyz, size_t n, const std::vector<std::array<double, 6>>& rest, int* idx, float* w);

// Writes points, normals and extent per frame from `start`. `where` names the field in errors.
void skin_mesh(PXR_NS::UsdGeomMesh m, const MeshData& d, const PXR_NS::JsObject& skin, int start,
               const std::string& where);

}  // namespace r3d
