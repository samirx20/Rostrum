// FBX animation and skins into a converted layer (convert.h, convert_fbx.cpp): the file's first animation stack is
// sampled at kCodesPerSecond, one time code per sample from the stack's start, and written as time samples. Each
// sample is ufbx's own evaluation of the whole scene at that time (ufbx_evaluate_scene), so FBX's transform chain
// (pivots, pre/post rotation, rotation order, scale inheritance, the upright adjustment) and its curves'
// interpolation are ufbx's:
//  - each node the stack animates gets its local transform per sample;
//  - each skinned or blend-shaped mesh gets its points per sample (the skin's joints and the shapes' weights as they
//    stand then), put into its node's own space so Storm and Cycles draw the same moving surface; a skinned mesh's
//    normals follow its joints too (the file's own normals turned, so hard edges stay hard). A deformed mesh in a
//    file with no animation is posed once, at rest.
// Not read: a second stack (the first one plays), constraints, vertex caches, a deformed mesh's motion blur.
#pragma once

#include <ufbx.h>

#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/xform.h>

#include <cstdint>
#include <map>
#include <vector>

namespace r3d::fbx {

constexpr double kCodesPerSecond = 30;

// A skinned or blend-shaped mesh as written at rest: its mesh prim (under `node`'s Xform) and the face corners it
// was written from, in order (faces of fewer than 3 corners are left out).
struct Deformed {
  const ufbx_node* node = nullptr;
  const ufbx_mesh* mesh = nullptr;
  pxr::UsdGeomMesh out;
  std::vector<uint32_t> corners;
};

// Writes what is above; `xforms` holds every node's Xform. `scene` was loaded with evaluate_skinning on (the rest
// pose). Throws r3d::Error when ufbx can't evaluate a sample.
void write_animation(const ufbx_scene* scene, const std::map<const ufbx_node*, pxr::UsdGeomXform>& xforms,
                     const std::vector<Deformed>& deformed, const pxr::UsdStageRefPtr& stage);

}  // namespace r3d::fbx
