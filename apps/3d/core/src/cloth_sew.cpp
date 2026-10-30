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
constexpr double kJoin = 0.002;      // m: a pair this close after the sewing time is one point (snapping wider gaps tore the cloth)
}  // namespace

ClothSew::ClothSew(const Cloth& c, double k) : time_(c.sewTime), join_(float(kJoin * k)) {
  for (const auto& s : c.seams) {
    if (s[0] < 0 || s[1] < 0 || size_t(s[0]) >= c.points.size() || size_t(s[1]) >= c.points.size()) continue;
    const V3 &a = c.points[size_t(s[0])], &b = c.points[size_t(s[1])];
    const double g = std::sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) + (a[2] - b[2]) * (a[2] - b[2]));
    pairs_.push_back({s[0], s[1], float(g * k)});
  }
}

void ClothSew::step(JPH::PhysicsSystem& physics, JPH::BodyID id, double t, double dt) {
  if (pairs_.empty()) return;
  JPH::BodyLockWrite lock(physics.GetBodyLockInterfaceNoLock(), id);
  if (!lock.Succeeded()) return;
  auto* mp = static_cast<JPH::SoftBodyMotionProperties*>(lock.GetBody().GetMotionProperties());
  JPH::Array<JPH::SoftBodyVertex>& v = mp->GetVertices();
  const bool sewing = t < time_;
  mp->SetGravityFactor(sewing ? 0.0f : 1.0f);
  const float next = sewing ? float(std::max(0.0, 1.0 - (t + dt) / time_)) : 0.0f;  // the share of each starting gap allowed after the next step
  if (sewing)
    for (JPH::SoftBodyVertex& p : v) p.mVelocity *= kSewDamping;
  for (int pass = 0; pass < kPasses; ++pass)
    for (const Pair& pr : pairs_) {
      if (size_t(std::max(pr.a, pr.b)) >= v.size()) continue;
      JPH::SoftBodyVertex &a = v[size_t(pr.a)], &b = v[size_t(pr.b)];
      const float wsum = a.mInvMass + b.mInvMass;
      if (wsum <= 0) continue;
      const float wa = a.mInvMass / wsum, wb = b.mInvMass / wsum;
      const JPH::Vec3 d = b.mPosition - a.mPosition;
      const float len = d.Length();
      if (!sewing && len <= join_) {  // met: one point from now on
        const JPH::Vec3 at = a.mPosition * wb + b.mPosition * wa;  // the heavier (smaller inverse) point moves less
        const JPH::Vec3 vel = a.mVelocity * wb + b.mVelocity * wa;
        a.mPosition = b.mPosition = at;
        if (a.mInvMass > 0) a.mVelocity = vel;
        if (b.mInvMass > 0) b.mVelocity = vel;
        continue;
      }
      // closing at the pace that brings the gap to its allowance at the end of the next step, given as speed: the solver's
      // next step then carries their neighbours along (moving the points themselves after the step stretched the cloth
      // round them, most where two seams meet at a corner)
      const float most = pr.gap * next;
      if (len <= most || len <= 1e-9f) continue;
      const JPH::Vec3 dir = d / len;
      if (!sewing) {  // after the sewing time the solver holds a pair a little apart: drawn together 2 mm a step as well
        // (KNOWN OPEN: most pairs then sit ~6 mm apart, the speed and the pull overshooting each other; pulling by position
        // alone, or only the near pairs, tore the cloth at the stand's shoulders)
        const float pull = std::min(len, join_);
        a.mPosition += dir * (pull * wa);
        b.mPosition -= dir * (pull * wb);
      }
      const float want = (len - most) / float(dt), closing = (a.mVelocity - b.mVelocity).Dot(dir);
      if (want > closing) {
        a.mVelocity += dir * ((want - closing) * wa);
        b.mVelocity -= dir * ((want - closing) * wb);
      }
    }
}

}  // namespace r3d::sim
