// Simple bone chains (SPEC §9, brief 19): a mesh bent by its bones, the same in Quick and Final because the
// bent points are written onto the mesh as time samples, which every renderer reads. Weights are automatic
// (from each point's distance to each bone at rest); the bending is USD skel's linear blend skinning.
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/usdGeom/mesh.h>

#include "primitives.h"

namespace r3d {

// `skin` (ENGINE_CONTRACT.md § 2, mesh `skin`): {"rest": [[hx,hy,hz, tx,ty,tz] per bone],
// "pose": [[[m00..m22, tx,ty,tz] per bone] per frame]}, all in the mesh's own space, p_now = M·p_rest + t.
// Writes points, normals and extent per frame from `start`. `where` names the field in errors.
void skin_mesh(PXR_NS::UsdGeomMesh m, const MeshData& d, const PXR_NS::JsObject& skin, int start,
               const std::string& where);

}  // namespace r3d
