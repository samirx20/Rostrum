// The `texels` picture's surface half (ENGINE_CONTRACT.md › texels): Storm says which prim each pixel shows and how
// deep (Hydra::ids); this finds, for a mesh prim's pixels, the face each pixel's ray meets and the mesh's `st` there.
// Storm's raster pass writes no primvar or face outputs (hdSt renderPass.glslfx: colour, ids, Neye only), so the
// (u, v) is worked out here, exactly as surface_spot.h does for one picked ray, for every pixel at once: each
// triangle tests only the pixels its corners cover on screen.
#pragma once
#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include <vector>

namespace r3d {

// a width x height picture's pixel rays through `frustum` (pixel centres, rows top first)
struct PixelRays {
  PixelRays(const PXR_NS::GfFrustum& frustum, int width, int height);
  int width, height;
  PXR_NS::GfMatrix4d toClip, fromClip;
  PXR_NS::GfVec3d eye;
  // the pixel's ray from the near plane (t = 0) to the far one (t = 1)
  void ray(int x, int y, PXR_NS::GfVec3d* from, PXR_NS::GfVec3d* along) const;
  // metres from the eye to what a window depth (0..1) at pixel (x, y) shows
  double distance(int x, int y, float depth) const;
};

// For the pixels whose `primIds` value is `id` (their indices, `pixels`), the mesh `prim`'s st where each pixel's ray
// meets it: u, v into out[4 i], out[4 i + 1] and the hit's distance from the eye into out[4 i + 3] (the face nearest
// the distance Storm drew, `drawn`, metres a pixel, < 0 = none). Pixels the mesh has no st for or no face under are
// left as they were. False when `prim` is no mesh with a usable st.
bool mesh_texels(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& prim, int frame, const PixelRays& rays,
                 const std::vector<int>& primIds, int id, const std::vector<int>& pixels,
                 const std::vector<double>& drawn, std::vector<float>* out);

}  // namespace r3d
