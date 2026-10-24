#include "poly.h"

#include <algorithm>
#include <cmath>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

int whole_at(const JsValue& v, const std::string& where) {
  if (!is_number(v) || to_number(v) != std::floor(to_number(v))) fail(where, "is not a whole number", "whole numbers");
  return int(to_number(v));
}

// Newell's normal: its length is twice the face's area, so summing these weights by area.
GfVec3f newell(const VtArray<GfVec3f>& pts, const int* idx, int n) {
  GfVec3f s(0);
  for (int i = 0; i < n; ++i) {
    const GfVec3f& a = pts[idx[i]];
    const GfVec3f& b = pts[idx[(i + 1) % n]];
    s += GfVec3f((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1]));
  }
  return s;
}

GfVec3f unit(const GfVec3f& v) {
  const float l = v.GetLength();
  return l > 1e-20f ? v / l : GfVec3f(0, 1, 0);
}

}  // namespace

MeshData make_poly(Reader& p, bool smooth) {
  const JsArray& jp = p.list("points");
  const JsArray& jc = p.list("faceCounts");
  const JsArray& ji = p.list("faceIndices");
  if (jp.empty()) fail(p.at("points"), "is empty", "a list of [x, y, z] points");
  if (jc.empty()) fail(p.at("faceCounts"), "is empty", "corners per face, 3 or more each");
  VtArray<GfVec3f> pts(jp.size());
  for (size_t i = 0; i < jp.size(); ++i) pts[i] = Reader::vec3_of(jp[i], p.at("points") + "[" + std::to_string(i) + "]");
  std::vector<int> counts(jc.size()), idx(ji.size());
  size_t total = 0;
  for (size_t f = 0; f < jc.size(); ++f) {
    const std::string w = p.at("faceCounts") + "[" + std::to_string(f) + "]";
    counts[f] = whole_at(jc[f], w);
    if (counts[f] < 3) fail(w, std::to_string(counts[f]) + " corners", "3 or more corners per face");
    total += size_t(counts[f]);
  }
  if (total != ji.size())
    fail(p.at("faceIndices"), std::to_string(ji.size()) + " indices but faceCounts add up to " + std::to_string(total),
         "as many indices as the face counts add up to");
  for (size_t k = 0; k < ji.size(); ++k) {
    const std::string w = p.at("faceIndices") + "[" + std::to_string(k) + "]";
    idx[k] = whole_at(ji[k], w);
    if (idx[k] < 0 || size_t(idx[k]) >= pts.size())
      fail(w, std::to_string(idx[k]) + " is out of range", "0 .. " + std::to_string(pts.size() - 1));
  }

  // Face normals (area-weighted) and the faces at each point.
  std::vector<GfVec3f> fn(counts.size());
  std::vector<std::vector<int>> at_point(pts.size());
  for (size_t f = 0, start = 0; f < counts.size(); start += counts[f], ++f) {
    fn[f] = newell(pts, &idx[start], counts[f]);
    for (int c = 0; c < counts[f]; ++c) at_point[idx[start + c]].push_back(int(f));
  }
  GfVec3f lo = pts[0], hi = pts[0];
  for (const GfVec3f& q : pts)
    for (int a = 0; a < 3; ++a) lo[a] = std::min(lo[a], q[a]), hi[a] = std::max(hi[a], q[a]);
  GfVec3f size = hi - lo;
  for (int a = 0; a < 3; ++a) if (size[a] < 1e-12f) size[a] = 1;

  const float cos30 = std::cos(30.0f * 3.14159265f / 180.0f);
  MeshData d;
  for (size_t f = 0, start = 0; f < counts.size(); start += counts[f], ++f) {
    const GfVec3f own = unit(fn[f]);
    // st: project onto the plane of the face normal's largest axis, 0..1 over the bounding box.
    int axis = 0;
    for (int a = 1; a < 3; ++a) if (std::abs(own[a]) > std::abs(own[axis])) axis = a;
    const int u = axis == 0 ? 2 : 0, v = axis == 1 ? 2 : 1;
    const float flip = (axis == 0 ? -own[0] : axis == 1 ? -own[1] : own[2]) < 0 ? -1.f : 1.f;  // never mirrored
    d.counts.push_back(counts[f]);
    for (int c = 0; c < counts[f]; ++c) {
      const int pi = idx[start + c];
      GfVec3f n = own;
      if (smooth) {
        GfVec3f sum(0);
        for (int g : at_point[pi])
          if (GfDot(unit(fn[g]), own) >= cos30) sum += fn[g];
        n = sum.GetLength() > 1e-20f ? unit(sum) : own;
      }
      const GfVec3f& q = pts[pi];
      float su = (q[u] - lo[u]) / size[u], sv = (q[v] - lo[v]) / size[v];
      if (flip < 0) su = 1 - su;
      d.indices.push_back(int(d.points.size()));
      d.points.push_back(q);
      d.normals.push_back(n);
      d.st.push_back(GfVec2f(su, sv));
    }
  }
  return d;
}

}  // namespace r3d
