// A cloth touching itself (cloth_self.h). Point against point with a thickness larger than a triangle's reach from its
// corners (a right triangle of the grid: 0.71 of an edge), the published position-based way; no code from elsewhere.
#include "cloth_self.h"

#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/SoftBody/SoftBodyMotionProperties.h>

#include <algorithm>
#include <cmath>

namespace r3d::sim {

namespace {
constexpr double kThick = 0.9;    // of the cloth's middle edge length
constexpr double kOwn = 1.6;      // pairs closer than this many thicknesses in the first shape are neighbours (a grid's diagonal: 1.57)
constexpr double kReach = 1.3;    // pairs gathered out to this many thicknesses, so the passes still see points pushed closer
constexpr int kPasses = 3;
constexpr float kFriction = 0.3f;  // cloth on cloth

uint32_t hash(int x, int y, int z, uint32_t n) {
  return (uint32_t(x) * 73856093u ^ uint32_t(y) * 19349663u ^ uint32_t(z) * 83492791u) % n;
}
}  // namespace

ClothSelf::ClothSelf(const Cloth& c, double k) {
  rest_.reserve(c.points.size());
  for (const V3& p : c.points) rest_.push_back({float(p[0] * k), float(p[1] * k), float(p[2] * k)});
  std::vector<double> e;
  for (const auto& t : c.triangles)
    for (int i = 0; i < 3; ++i) {
      const V3 &a = c.points[size_t(t[i])], &b = c.points[size_t(t[(i + 1) % 3])];
      e.push_back(std::sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) + (a[2] - b[2]) * (a[2] - b[2])));
    }
  if (e.empty()) return;
  std::nth_element(e.begin(), e.begin() + long(e.size() / 2), e.end());
  h_ = kThick * e[e.size() / 2] * k;
}

void ClothSelf::step(JPH::PhysicsSystem& physics, JPH::BodyID id) {
  if (!(h_ > 0)) return;
  JPH::BodyLockWrite lock(physics.GetBodyLockInterfaceNoLock(), id);
  if (!lock.Succeeded() || !lock.GetBody().IsActive()) return;
  auto* mp = static_cast<JPH::SoftBodyMotionProperties*>(lock.GetBody().GetMotionProperties());
  JPH::Array<JPH::SoftBodyVertex>& v = mp->GetVertices();
  const size_t n = std::min(v.size(), rest_.size());
  if (n < 2) return;

  // the hash: points sorted by bucket (a counting sort), each point's own cell kept to drop other cells in its bucket
  const double cs = h_ * kReach;
  const uint32_t buckets = uint32_t(2 * n + 1);
  cell_.resize(n);
  start_.assign(size_t(buckets) + 1, 0);
  sorted_.resize(n);
  for (size_t i = 0; i < n; ++i) {
    const JPH::Vec3 p = v[i].mPosition;
    cell_[i] = {int(std::floor(p.GetX() / cs)), int(std::floor(p.GetY() / cs)), int(std::floor(p.GetZ() / cs))};
    ++start_[hash(cell_[i][0], cell_[i][1], cell_[i][2], buckets) + 1];
  }
  for (uint32_t b = 0; b < buckets; ++b) start_[b + 1] += start_[b];
  {
    std::vector<uint32_t> fill(start_.begin(), start_.end() - 1);
    for (size_t i = 0; i < n; ++i) sorted_[fill[hash(cell_[i][0], cell_[i][1], cell_[i][2], buckets)]++] = uint32_t(i);
  }

  // the pairs near enough to matter that weren't neighbours in the first shape
  pairs_.clear();
  const float reach2 = float(cs * cs), own2 = float(kOwn * kOwn * h_ * h_);
  for (size_t i = 0; i < n; ++i) {
    if (v[i].mInvMass <= 0) continue;  // a held point is reached from the free one
    const auto& c = cell_[i];
    for (int dx = -1; dx <= 1; ++dx)
      for (int dy = -1; dy <= 1; ++dy)
        for (int dz = -1; dz <= 1; ++dz) {
          const std::array<int, 3> q{c[0] + dx, c[1] + dy, c[2] + dz};
          const uint32_t b = hash(q[0], q[1], q[2], buckets);
          for (uint32_t s = start_[b]; s < start_[b + 1]; ++s) {
            const uint32_t j = sorted_[s];
            if (j == i || cell_[j] != q || (j < i && v[j].mInvMass > 0)) continue;  // each free pair once
            if ((v[i].mPosition - v[j].mPosition).LengthSq() > reach2) continue;
            const auto &ri = rest_[i], &rj = rest_[j];
            const float rx = ri[0] - rj[0], ry = ri[1] - rj[1], rz = ri[2] - rj[2];
            if (rx * rx + ry * ry + rz * rz < own2) continue;
            pairs_.push_back({uint32_t(i), j});
          }
        }
  }
  if (pairs_.empty()) return;

  // push apart, a few passes; then take away their speed into each other and slow their sliding
  const float h = float(h_), h2 = h * h;
  for (int pass = 0; pass < kPasses; ++pass)
    for (const Pair& pr : pairs_) {
      JPH::SoftBodyVertex &a = v[pr.a], &b = v[pr.b];
      const float wsum = a.mInvMass + b.mInvMass;
      const JPH::Vec3 d = a.mPosition - b.mPosition;
      const float d2 = d.LengthSq();
      if (d2 >= h2 || wsum <= 0) continue;
      const float len = std::sqrt(d2);
      const JPH::Vec3 nrm = len > 1e-9f * h ? d / len : JPH::Vec3(0, 1, 0);
      const JPH::Vec3 push = nrm * ((h - len) / wsum);
      a.mPosition += push * a.mInvMass;
      b.mPosition -= push * b.mInvMass;
    }
  const float slack2 = (1.05f * h) * (1.05f * h);
  for (const Pair& pr : pairs_) {
    JPH::SoftBodyVertex &a = v[pr.a], &b = v[pr.b];
    const float wsum = a.mInvMass + b.mInvMass;
    const JPH::Vec3 d = a.mPosition - b.mPosition;
    const float d2 = d.LengthSq();
    if (d2 >= slack2 || d2 <= 0 || wsum <= 0) continue;
    const JPH::Vec3 nrm = d / std::sqrt(d2);
    const JPH::Vec3 rel = a.mVelocity - b.mVelocity;
    const float vn = rel.Dot(nrm);
    JPH::Vec3 dv = JPH::Vec3::sZero();
    if (vn < 0) dv = nrm * vn;  // closing: stop it
    const JPH::Vec3 vt = rel - nrm * vn;
    const float vtl = vt.Length();
    if (vtl > 0 && vn < 0) dv += vt * std::min(1.0f, kFriction * -vn / vtl);  // as much as the stop allows (Coulomb)
    a.mVelocity -= dv * (a.mInvMass / wsum);
    b.mVelocity += dv * (b.mInvMass / wsum);
  }
}

}  // namespace r3d::sim
