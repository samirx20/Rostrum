// glTF animation and skins into a converted layer (convert.h, convert_gltf.cpp): the file's first animation is
// sampled at kCodesPerSecond, one time code per sample from 0, and written as time samples:
//  - each node a channel moves gets its local transform per sample (translation, rotation, scale; STEP, LINEAR and
//    CUBICSPLINE as glTF defines them);
//  - each skinned mesh gets its points and normals per sample, skinned on the CPU (JOINTS_0 / WEIGHTS_0, the skin's
//    inverse bind matrices, the joints where the animation has them) and put into its node's own space, so Storm and
//    Cycles draw the same moving surface. A skinned mesh in a file with no animation is skinned once, at rest.
// Not read: morph target weights, a second animation (the first one plays), a skinned mesh's motion blur.
#pragma once

#include <cgltf.h>

#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/xform.h>

#include <map>
#include <vector>

#include "convert_usd.h"

namespace r3d::gltf {

constexpr double kCodesPerSecond = 30;

// A skinned primitive as written at rest: its mesh prim (under `node`'s Xform) and the arrays it was written from.
struct Skinned {
  cgltf_node* node = nullptr;
  const cgltf_primitive* prim = nullptr;
  pxr::UsdGeomMesh mesh;
  cv::MeshArrays rest;
};

// Writes what is above; `xforms` holds every node's Xform. Throws r3d::Error when a skin's data is broken.
void write_animation(cgltf_data* data, const std::map<const cgltf_node*, pxr::UsdGeomXform>& xforms,
                     const std::vector<Skinned>& skinned, const pxr::UsdStageRefPtr& stage);

}  // namespace r3d::gltf
