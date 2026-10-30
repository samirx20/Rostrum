// A cloth's mesh made fine enough to fold (sim.h `refine`, brief 26b). Plain numbers, no USD, no Jolt.
// A plane is one four-point face: it becomes a kClothGrid × kClothGrid grid (its corners blended, so a turned or stretched
// plane stays that shape), the diagonals alternating so it folds the same way in every direction. Any other mesh is
// triangulated (a fan per face, its winding kept) and every triangle split in four (shared edges split once) until no edge
// is longer than 1/kClothGrid of its size. A garment (seams: the app made it fine already) is only triangulated.
#include <algorithm>
#include <cmath>
#include <map>
#include <utility>

#include "sim.h"

namespace r3d::sim {

namespace {

V3 lerp(const V3& a, const V3& b, double t) { return {a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t}; }

std::array<float, 2> lerp2(const std::array<float, 2>& a, const std::array<float, 2>& b, double t) {
  return {float(a[0] + (b[0] - a[0]) * t), float(a[1] + (b[1] - a[1]) * t)};
}

double dist2(const V3& a, const V3& b) {
  return (a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) + (a[2] - b[2]) * (a[2] - b[2]);
}

double area2(const V3& a, const V3& b, const V3& c) {  // |(b - a) × (c - a)|²
  const V3 u{b[0] - a[0], b[1] - a[1], b[2] - a[2]}, v{c[0] - a[0], c[1] - a[1], c[2] - a[2]};
  const V3 n{u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]};
  return n[0] * n[0] + n[1] * n[1] + n[2] * n[2];
}

void grid(Cloth& c, const std::vector<int>& f) {
  const int n = kClothGrid;
  const V3 p0 = c.points[size_t(f[0])], p1 = c.points[size_t(f[1])], p2 = c.points[size_t(f[2])], p3 = c.points[size_t(f[3])];
  const auto s0 = c.st[size_t(f[0])], s1 = c.st[size_t(f[1])], s2 = c.st[size_t(f[2])], s3 = c.st[size_t(f[3])];
  std::vector<V3> pts;
  std::vector<std::array<float, 2>> st;
  for (int j = 0; j <= n; ++j)
    for (int i = 0; i <= n; ++i) {  // corner 0 at (0, 0), 1 at (1, 0), 2 at (1, 1), 3 at (0, 1): the face's own order
      const double u = double(i) / n, v = double(j) / n;
      pts.push_back(lerp(lerp(p0, p1, u), lerp(p3, p2, u), v));
      st.push_back(lerp2(lerp2(s0, s1, u), lerp2(s3, s2, u), v));
    }
  c.triangles.clear();
  for (int j = 0; j < n; ++j)
    for (int i = 0; i < n; ++i) {
      const int a = j * (n + 1) + i, b = a + 1, d = a + n + 1, e = d + 1;
      if ((i + j) % 2 == 0) {
        c.triangles.push_back({a, b, e});
        c.triangles.push_back({a, e, d});
      } else {
        c.triangles.push_back({a, b, d});
        c.triangles.push_back({b, e, d});
      }
    }
  c.points = std::move(pts);
  c.st = std::move(st);
  c.refined = true;
}

void split(Cloth& c) {
  std::map<std::pair<int, int>, int> mid;
  const auto at = [&](int a, int b) {
    const std::pair<int, int> key(std::min(a, b), std::max(a, b));
    const auto it = mid.find(key);
    if (it != mid.end()) return it->second;
    const int m = int(c.points.size());
    c.points.push_back(lerp(c.points[size_t(a)], c.points[size_t(b)], 0.5));
    c.st.push_back(lerp2(c.st[size_t(a)], c.st[size_t(b)], 0.5));
    mid.emplace(key, m);
    return m;
  };
  std::vector<std::array<int, 3>> out;
  out.reserve(c.triangles.size() * 4);
  for (const auto& t : c.triangles) {
    const int ab = at(t[0], t[1]), bc = at(t[1], t[2]), ca = at(t[2], t[0]);
    out.push_back({t[0], ab, ca});
    out.push_back({ab, t[1], bc});
    out.push_back({ca, bc, t[2]});
    out.push_back({ab, bc, ca});
  }
  c.triangles = std::move(out);
  c.refined = true;
}

}  // namespace

void refine(Cloth& c, const std::vector<std::vector<int>>& faces) {
  c.st.resize(c.points.size(), {0.0f, 0.0f});
  V3 lo{1e30, 1e30, 1e30}, hi{-1e30, -1e30, -1e30};
  for (const V3& p : c.points)
    for (int k = 0; k < 3; ++k) { lo[k] = std::min(lo[k], p[k]); hi[k] = std::max(hi[k], p[k]); }
  const double size2 = c.points.empty() ? 0 : dist2(lo, hi);
  const auto valid = [&](const std::vector<int>& f) {
    for (int i : f)
      if (i < 0 || size_t(i) >= c.points.size()) return false;
    return true;
  };

  if (c.seams.empty() && faces.size() == 1 && faces[0].size() == 4 && c.points.size() == 4 && valid(faces[0])) {
    grid(c, faces[0]);
  } else {
    c.triangles.clear();
    for (const auto& f : faces)
      if (f.size() >= 3 && valid(f))
        for (size_t k = 1; k + 1 < f.size(); ++k) c.triangles.push_back({f[0], f[k], f[k + 1]});
    const double most2 = size2 / double(kClothGrid * kClothGrid);
    for (;;) {
      double longest2 = 0;
      for (const auto& t : c.triangles)
        for (int e = 0; e < 3; ++e) longest2 = std::max(longest2, dist2(c.points[size_t(t[e])], c.points[size_t(t[(e + 1) % 3])]));
      if (!c.seams.empty() || longest2 <= most2 * 1.0001 || c.triangles.size() * 4 > kMaxClothTriangles) break;
      split(c);
    }
  }

  // no faces without area, no points without a face
  const double least = std::max(1e-24, size2 * size2 * 1e-16);
  std::vector<std::array<int, 3>> kept;
  for (const auto& t : c.triangles)
    if (t[0] != t[1] && t[1] != t[2] && t[0] != t[2] &&
        area2(c.points[size_t(t[0])], c.points[size_t(t[1])], c.points[size_t(t[2])]) > least)
      kept.push_back(t);
  std::vector<int> renum(c.points.size(), -1);
  std::vector<V3> pts;
  std::vector<std::array<float, 2>> st;
  for (auto& t : kept)
    for (int& i : t) {
      if (renum[size_t(i)] < 0) {
        renum[size_t(i)] = int(pts.size());
        pts.push_back(c.points[size_t(i)]);
        st.push_back(c.st[size_t(i)]);
      }
      i = renum[size_t(i)];
    }
  c.points = std::move(pts);
  c.st = std::move(st);
  c.triangles = std::move(kept);
  std::vector<std::array<int, 2>> sewn;
  for (const auto& s : c.seams) {
    const int a = s[0] >= 0 && size_t(s[0]) < renum.size() ? renum[size_t(s[0])] : -1;
    const int b = s[1] >= 0 && size_t(s[1]) < renum.size() ? renum[size_t(s[1])] : -1;
    if (a >= 0 && b >= 0 && a != b) sewn.push_back({a, b});
  }
  c.seams = std::move(sewn);
}

}  // namespace r3d::sim
