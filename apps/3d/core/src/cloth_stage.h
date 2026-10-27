// A cloth's stored simulation on the stage (brief 26b; ENGINE_CONTRACT.md § Simulation, a mesh node's `cloth`).
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/usdGeom/mesh.h>

#include "item_track.h"

namespace r3d {

// Replaces the mesh's faces and u v with the ones the cloth was simulated with, and its points, normals and extent with the
// stored ones at each frame of the shot (`cloth` {"file", "start", "end", "step": 1..3, "smooth": 1..100}: On 2s / On 3s
// from the shot's start, Simplify's every nth frame with straight lines between). Double-sided: a sheet is seen from both
// sides. A file that doesn't match its header, or is missing, is an error naming the field.
void cloth_mesh(Item& it, PXR_NS::UsdGeomMesh m, const PXR_NS::JsObject& cloth);

}  // namespace r3d
