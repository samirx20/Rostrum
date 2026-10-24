#include "skin.h"

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include <pxr/base/gf/matrix3d.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/usd/usdSkel/utils.h>

#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

constexpr int kMost = 4;  // influences kept per point (the nearest bones)

std::vector<double> numbers(const JsValue& v, size_t n, const std::string& where, const char* accepted) {
  if (!v.IsArray() || v.GetJsArray().size() != n) fail(where, "is not " + std::to_string(n) + " numbers", accepted);
  std::vector<double> out;
  for (const JsValue& x : v.GetJsArray()) {
    if (!is_number(x) || !std::isfinite(to_number(x))) fail(where, "holds something that is not a number", accepted);
    out.push_back(to_number(x));
  }
  return out;
}

double segment_distance(const GfVec3d& p, const GfVec3d& a, const GfVec3d& b) {
  const GfVec3d ab = b - a;
  const double len2 = GfDot(ab, ab);
  const double s = len2 > 0 ? std::clamp(GfDot(p - a, ab) / len2, 0.0, 1.0) : 0.0;
  return (p - (a + ab * s)).GetLength();
}

// Automatic weights: each point leans on its nearest bones by 1 / distance⁴, so a point beside one bone follows it
// and a point at a joint shares it between both bones: the bend is smooth over about the mesh's thickness.
void weights(const MeshData& d, const std::vector<std::vector<double>>& rest, VtIntArray& idx, VtFloatArray& w) {
  const int bones = int(rest.size()), k = std::min(kMost, bones);
  idx.assign(d.points.size() * k, 0);
  w.assign(d.points.size() * k, 0.0f);
  std::vector<std::pair<double, int>> closest(bones);
  for (size_t i = 0; i < d.points.size(); ++i) {
    const GfVec3d p(d.points[i]);
    for (int b = 0; b < bones; ++b) {
      const auto& r = rest[b];
      const double dist = segment_distance(p, GfVec3d(r[0], r[1], r[2]), GfVec3d(r[3], r[4], r[5]));
      closest[b] = {1.0 / (std::pow(dist, 4) + 1e-12), b};
    }
    std::partial_sort(closest.begin(), closest.begin() + k, closest.end(), std::greater<>());
    double sum = 0;
    for (int j = 0; j < k; ++j) sum += closest[j].first;
    for (int j = 0; j < k; ++j) {
      idx[i * k + j] = closest[j].second;
      w[i * k + j] = float(closest[j].first / sum);
    }
  }
}

// [m00..m22, tx,ty,tz] (column vectors: p' = M·p + t) as USD's row-vector matrix.
GfMatrix4d as_usd(const std::vector<double>& v) {
  GfMatrix4d g(1.0);
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c) g[r][c] = v[c * 3 + r];
  g[3][0] = v[9], g[3][1] = v[10], g[3][2] = v[11];
  return g;
}

}  // namespace

void skin_mesh(UsdGeomMesh m, const MeshData& d, const JsObject& skin, int start, const std::string& where) {
  Reader s(skin, where);
  const JsArray& jrest = s.list("rest");
  const JsArray& jpose = s.list("pose");
  s.finish();
  if (jrest.empty()) fail(s.at("rest"), "is empty", "one [head x y z, tail x y z] per bone");
  if (jpose.empty()) fail(s.at("pose"), "is empty", "one list of bone moves per frame of the shot");
  std::vector<std::vector<double>> rest;
  for (size_t b = 0; b < jrest.size(); ++b)
    rest.push_back(numbers(jrest[b], 6, s.at("rest") + "[" + std::to_string(b) + "]", "[hx, hy, hz, tx, ty, tz]"));
  VtIntArray idx;
  VtFloatArray w;
  weights(d, rest, idx, w);
  const int k = int(idx.size() / std::max<size_t>(1, d.points.size()));
  const bool normals = d.normals.size() == d.points.size();
  for (size_t f = 0; f < jpose.size(); ++f) {
    const std::string at = s.at("pose") + "[" + std::to_string(f) + "]";
    if (!jpose[f].IsArray() || jpose[f].GetJsArray().size() != rest.size())
      fail(at, "does not hold one move per bone", std::to_string(rest.size()) + " lists of 12 numbers");
    std::vector<GfMatrix4d> xf;
    std::vector<GfMatrix3d> nx;
    for (size_t b = 0; b < rest.size(); ++b) {
      xf.push_back(as_usd(numbers(jpose[f].GetJsArray()[b], 12, at + "[" + std::to_string(b) + "]",
                                  "[m00, m01, m02, m10, m11, m12, m20, m21, m22, tx, ty, tz]")));
      nx.push_back(xf.back().ExtractRotationMatrix().GetInverse().GetTranspose());
    }
    VtVec3fArray pts = d.points, nrm = d.normals;
    if (!UsdSkelSkinPointsLBS(GfMatrix4d(1.0), xf, idx, w, k, pts))
      fail(at, "the bones could not bend the mesh", "a move per bone that can be inverted");
    if (normals) UsdSkelSkinNormalsLBS(GfMatrix3d(1.0), nx, idx, w, k, nrm);
    const UsdTimeCode t(double(start) + double(f));
    m.GetPointsAttr().Set(pts, t);
    if (normals) m.GetNormalsAttr().Set(nrm, t);
    VtVec3fArray extent;
    if (UsdGeomPointBased::ComputeExtent(pts, &extent)) m.GetExtentAttr().Set(extent, t);
  }
}

}  // namespace r3d
