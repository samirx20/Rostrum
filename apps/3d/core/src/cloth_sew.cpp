// Sewing a garment (cloth_sew.h). Position-based, like cloth_self: no code from elsewhere.
#include "cloth_sew.h"

#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/SoftBody/SoftBodyMotionProperties.h>

#include <algorithm>
#include <cmath>

namespace r3d::sim {

namespace {
constexpr int kPasses = 2;          // a point sewn to two (a corner where seams meet) settles in two
constexpr float kSewDamping = 0.9f;  // speed kept per step while sewing
}  // namespace

ClothSew::ClothSew(const Cloth& c, double k) : time_(c.sewTime) {
  for (const auto& s : c.seams) {
    if (s[0] < 0 || s[1] < 0 || size_t(s[0]) >= c.points.size() || size_t(s[1]) >= c.points.size()) continue;
    const V3 &a = c.points[size_t(s[0])], &b = c.points[size_t(s[1])];
    const double g = std::sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) + (a[2] - b[2]) * (a[2] - b[2]));
    pairs_.push_back({s[0], s[1], float(g * k)});
  }
}

void ClothSew::step(JPH::PhysicsSystem& physics, JPH::BodyID id, double t) {
  if (pairs_.empty()) return;
  JPH::BodyLockWrite lock(physics.GetBodyLockInterfaceNoLock(), id);
  if (!lock.Succeeded()) return;
  auto* mp = static_cast<JPH::SoftBodyMotionProperties*>(lock.GetBody().GetMotionProperties());
  JPH::Array<JPH::SoftBodyVertex>& v = mp->GetVertices();
  const bool sewing = t < time_;
  mp->SetGravityFactor(sewing ? 0.0f : 1.0f);
  const float left = sewing ? float(1.0 - t / time_) : 0.0f;  // the share of each starting gap still allowed
  if (sewing)
    for (JPH::SoftBodyVertex& p : v) p.mVelocity *= kSewDamping;
  for (int pass = 0; pass < kPasses; ++pass)
    for (const Pair& pr : pairs_) {
      if (size_t(std::max(pr.a, pr.b)) >= v.size()) continue;
      JPH::SoftBodyVertex &a = v[size_t(pr.a)], &b = v[size_t(pr.b)];
      const float wsum = a.mInvMass + b.mInvMass;
      if (wsum <= 0) continue;
      const float wa = a.mInvMass / wsum, wb = b.mInvMass / wsum;
      if (!sewing) {  // sewn: one point
        const JPH::Vec3 at = a.mPosition * wb + b.mPosition * wa;  // the heavier (smaller inverse) point moves less
        const JPH::Vec3 vel = a.mVelocity * wb + b.mVelocity * wa;
        a.mPosition = b.mPosition = at;
        if (a.mInvMass > 0) a.mVelocity = vel;
        if (b.mInvMass > 0) b.mVelocity = vel;
        continue;
      }
      const JPH::Vec3 d = b.mPosition - a.mPosition;
      const float len = d.Length(), most = pr.gap * left;
      if (len <= most || len <= 1e-9f) continue;
      const JPH::Vec3 dir = d / len;
      a.mPosition += dir * ((len - most) * wa);
      b.mPosition -= dir * ((len - most) * wb);
      const float apart = (b.mVelocity - a.mVelocity).Dot(dir);  // their speed apart
      if (apart > 0) {
        a.mVelocity += dir * (apart * wa);
        b.mVelocity -= dir * (apart * wb);
      }
    }
}

}  // namespace r3d::sim
