#include "surface_spot.h"

#include <limits>

#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

std::optional<SurfaceSpot> surface_spot(const UsdStageRefPtr& stage, const SdfPath& prim, int frame, const GfRay& ray) {
  const UsdGeomMesh m(stage->GetPrimAtPath(prim));
  if (!m) return std::nullopt;
  const UsdTimeCode t(frame);
  VtVec3fArray pts;
  VtIntArray counts, indices;
  m.GetPointsAttr().Get(&pts, t);
  m.GetFaceVertexCountsAttr().Get(&counts, t);
  m.GetFaceVertexIndicesAttr().Get(&indices, t);
  GfRay local = ray;
  local.Transform(m.ComputeLocalToWorldTransform(t).GetInverse());

  // the nearest triangle hit (faces as fans), with the face corners and weights it lands between
  double best = std::numeric_limits<double>::infinity();
  int face = -1;
  size_t corner[3] = {0, 0, 0};
  GfVec3d weights;
  size_t first = 0;
  for (size_t f = 0; f < counts.size(); first += size_t(counts[f]), ++f) {
    for (int i = 1; i + 1 < counts[f]; ++i) {
      const size_t c[3] = {first, first + size_t(i), first + size_t(i) + 1};
      if (c[2] >= indices.size()) return std::nullopt;  // a broken mesh: no spot rather than a wrong one
      double d;
      GfVec3d b;
      if (!local.Intersect(GfVec3d(pts[indices[c[0]]]), GfVec3d(pts[indices[c[1]]]), GfVec3d(pts[indices[c[2]]]), &d,
                           &b, nullptr, best))
        continue;
      best = d;
      face = int(f);
      weights = b;
      for (int k = 0; k < 3; ++k) corner[k] = c[k];
    }
  }
  if (face < 0) return std::nullopt;
  SurfaceSpot spot;
  spot.face = face;
  VtVec2fArray st;
  const UsdGeomPrimvar pv = UsdGeomPrimvarsAPI(m.GetPrim()).GetPrimvar(TfToken("st"));
  if (!pv || !pv.ComputeFlattened(&st, t)) return spot;
  const TfToken interp = pv.GetInterpolation();
  GfVec2f uv(0, 0);
  for (int k = 0; k < 3; ++k) {
    size_t at;
    if (interp == UsdGeomTokens->faceVarying && st.size() == indices.size()) at = corner[k];
    else if ((interp == UsdGeomTokens->vertex || interp == UsdGeomTokens->varying) && st.size() == pts.size())
      at = size_t(indices[corner[k]]);
    else return spot;
    uv += st[at] * float(weights[k]);
  }
  spot.uv = uv;
  return spot;
}

}  // namespace r3d
