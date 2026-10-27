// Where on a mesh's surface a picked ray lands: the face it hits and the (u, v) there, from the mesh's `st`
// (face-varying, as the core writes it, or per point). The `pick` request adds them to its answer so a brush
// stroke on the viewport becomes canvas pixels (SPEC §5, painting). CPU ray against the drawn mesh's triangles:
// the core draws exactly these faces (smoothing is done before writing), so the spot is the one seen.
#pragma once
#include <optional>

#include <pxr/base/gf/ray.h>
#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

namespace r3d {

struct SurfaceSpot {
  int face = -1;                       // the mesh's face (as written, after smoothing)
  std::optional<PXR_NS::GfVec2f> uv;   // none when the mesh has no usable st
  // 3d-cl4: the spot and the surface's normal there in the prim's own space (a clay's block: the clay's space); the
  // normal blended from the mesh's per-point normals, else the triangle's own
  PXR_NS::GfVec3d local, localNormal;
};

// `ray` in world space through the picked pixel; `prim` the picked prim. None when `prim` is not a mesh or the ray
// misses its faces.
std::optional<SurfaceSpot> surface_spot(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& prim, int frame,
                                        const PXR_NS::GfRay& ray);

}  // namespace r3d
