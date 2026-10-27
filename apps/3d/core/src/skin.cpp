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

// [m00..m22, tx,ty,tz] (column vectors: p' = M·p + t) as USD's row-vector matrix.
GfMatrix4d as_usd(const BoneMove& v) {
  GfMatrix4d g(1.0);
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c) g[r][c] = v[c * 3 + r];
  g[3][0] = v[9], g[3][1] = v[10], g[3][2] = v[11];
  return g;
}

}  // namespace

BoneMove read_bone_move(const JsValue& v, const std::string& where) {
  const std::vector<double> n = numbers(v, 12, where, "[m00, m01, m02, m10, m11, m12, m20, m21, m22, tx, ty, tz]");
  BoneMove m;
  std::copy(n.begin(), n.end(), m.begin());
  return m;
}

SkinRig read_skin(const JsObject& skin, const std::string& where) {
  Reader s(skin, where);
  const JsArray& jrest = s.list("rest");
  const JsArray& jpose = s.list("pose");
  s.finish();
  if (jrest.empty()) fail(s.at("rest"), "is empty", "one [head x y z, tail x y z] per bone");
  if (jpose.empty()) fail(s.at("pose"), "is empty", "one list of bone moves per frame of the shot");
  SkinRig rig;
  for (size_t b = 0; b < jrest.size(); ++b) {
    const std::vector<double> r =
        numbers(jrest[b], 6, s.at("rest") + "[" + std::to_string(b) + "]", "[hx, hy, hz, tx, ty, tz]");
    std::array<double, 6> a;
    std::copy(r.begin(), r.end(), a.begin());
    rig.rest.push_back(a);
  }
  for (size_t f = 0; f < jpose.size(); ++f) {
    const std::string at = s.at("pose") + "[" + std::to_string(f) + "]";
    if (!jpose[f].IsArray() || jpose[f].GetJsArray().size() != rig.rest.size())
      fail(at, "does not hold one move per bone", std::to_string(rig.rest.size()) + " lists of 12 numbers");
    std::vector<BoneMove> frame;
    for (size_t b = 0; b < rig.rest.size(); ++b)
      frame.push_back(read_bone_move(jpose[f].GetJsArray()[b], at + "[" + std::to_string(b) + "]"));
    rig.pose.push_back(std::move(frame));
  }
  return rig;
}

// Automatic weights: each point leans on its nearest bones by 1 / distance⁴, so a point beside one bone follows it
// and a point at a joint shares it between both bones: the bend is smooth over about the item's thickness.
void skin_weights(const float* xyz, size_t n, const std::vector<std::array<double, 6>>& rest, int* idx, float* w) {
  const int bones = int(rest.size()), k = skin_influences(rest.size());
  if (k == 0) return;
  std::vector<std::pair<double, int>> closest(bones);
  for (size_t i = 0; i < n; ++i) {
    const GfVec3d p(xyz[3 * i], xyz[3 * i + 1], xyz[3 * i + 2]);
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

void skin_mesh(UsdGeomMesh m, const MeshData& d, const JsObject& skin, int start, const std::string& where) {
  const SkinRig rig = read_skin(skin, where);
  const int k = skin_influences(rig.rest.size());
  VtIntArray idx(d.points.size() * k);
  VtFloatArray w(d.points.size() * k);
  skin_weights(reinterpret_cast<const float*>(d.points.cdata()), d.points.size(), rig.rest, idx.data(), w.data());
  const bool normals = d.normals.size() == d.points.size();
  for (size_t f = 0; f < rig.pose.size(); ++f) {
    const std::string at = where + ".pose[" + std::to_string(f) + "]";
    std::vector<GfMatrix4d> xf;
    std::vector<GfMatrix3d> nx;
    for (const BoneMove& b : rig.pose[f]) {
      xf.push_back(as_usd(b));
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
