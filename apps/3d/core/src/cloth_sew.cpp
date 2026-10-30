// Sewing a garment (cloth_sew.h): seams as the solver's own edges. No code from elsewhere.
#include "cloth_sew.h"

#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/SoftBody/SoftBodyMotionProperties.h>

#include <algorithm>
#include <set>
#include <utility>

namespace r3d::sim {

namespace {
constexpr float kSewDamping = 0.9f;  // speed kept per step while sewing
constexpr float kMostPull = 0.25f;   // of the cloth's mean edge: the most a seam asks to shorten in one step from where it is
constexpr double kShut = 2.0;        // of the cloth's mean edge: a sewn pair nearer than this is moved together after each step
constexpr double kMostClose = 0.5;   // of the cloth's mean edge: the most such a pair closes in one step (the solver reopened a
                                     // neck end by ~0.25 a step, so a quarter held it ~2 mm open)
}  // namespace

std::vector<JPH::uint> add_seam_edges(JPH::SoftBodySharedSettings& s, const Cloth& c, float compliance) {
  std::vector<JPH::uint> out;
  std::set<std::pair<int, int>> made;  // a corner where two seams meet is sewn by both: one edge, not twice the pull
  for (const auto& p : c.seams) {
    if (p[0] < 0 || p[1] < 0 || size_t(p[0]) >= s.mVertices.size() || size_t(p[1]) >= s.mVertices.size()) continue;
    if (!made.insert({std::min(p[0], p[1]), std::max(p[0], p[1])}).second) continue;
    const JPH::Vec3 a(s.mVertices[size_t(p[0])].mPosition), b(s.mVertices[size_t(p[1])].mPosition);
    out.push_back(JPH::uint(s.mEdgeConstraints.size()));
    s.mEdgeConstraints.emplace_back(JPH::uint32(p[0]), JPH::uint32(p[1]), compliance);
    s.mEdgeConstraints.back().mRestLength = (b - a).Length();
  }
  return out;
}

ClothSew::ClothSew(JPH::Ref<JPH::SoftBodySharedSettings> s, const std::vector<JPH::uint>& edges,
                   const JPH::Array<JPH::uint>& remap, const Cloth& c, double k)
    : s_(std::move(s)), time_(c.sewTime) {
  std::vector<bool> seam(s_->mEdgeConstraints.size(), false);
  for (JPH::uint e : edges) {
    const JPH::uint at = e < remap.size() ? remap[e] : e;
    if (at < s_->mEdgeConstraints.size()) {
      seams_.push_back({at, s_->mEdgeConstraints[at].mRestLength});
      seam[at] = true;
    }
  }
  double sum = 0;  // the cloth's own edges' mean length
  size_t n = 0;
  for (size_t i = 0; i < seam.size(); ++i)
    if (!seam[i]) { sum += s_->mEdgeConstraints[i].mRestLength; ++n; }
  most_ = n ? float(kMostPull * sum / double(n)) : 0.0f;
  shut_ = n ? float(kShut * sum / double(n)) : 0.0f;
  close_ = n ? float(kMostClose * sum / double(n)) : 0.0f;
}

void ClothSew::before(JPH::PhysicsSystem& physics, JPH::BodyID id, double t) {
  if (seams_.empty()) return;
  const bool sew = t < time_;
  const float left = sew ? float(std::max(0.0, 1.0 - t / time_)) : 0.0f;  // the share of each starting gap at the step's end
  JPH::BodyLockWrite lock(physics.GetBodyLockInterfaceNoLock(), id);
  if (!lock.Succeeded()) return;
  auto* mp = static_cast<JPH::SoftBodyMotionProperties*>(lock.GetBody().GetMotionProperties());
  const JPH::Array<JPH::SoftBodyVertex>& v = mp->GetVertices();
  // each seam's length for this step (between steps: the solver isn't reading). Closing: its share of the starting gap,
  // but never more than `most_` shorter than it is now, so a seam something holds open pulls like cloth stretched a
  // quarter, and keeps pulling, rather than harder every step until the cloth beside it tears. (Holding a met pair
  // infinitely stiff tore a crumpled garment on the ground: tried, taken out.)
  for (const Seam& m : seams_) {
    JPH::SoftBodySharedSettings::Edge& e = s_->mEdgeConstraints[m.edge];
    const float now = (v[e.mVertex[1]].mPosition - v[e.mVertex[0]].mPosition).Length();
    e.mRestLength = std::max(m.gap * left, now - most_);
  }
  sewn_ = !sew;
  mp->SetGravityFactor(sew ? 0.0f : 1.0f);
  if (sew)
    for (JPH::SoftBodyVertex& p : mp->GetVertices()) p.mVelocity *= kSewDamping;
}

void ClothSew::after(JPH::PhysicsSystem& physics, JPH::BodyID id) {
  if (seams_.empty() || !sewn_ || !(shut_ > 0)) return;
  JPH::BodyLockWrite lock(physics.GetBodyLockInterfaceNoLock(), id);
  if (!lock.Succeeded()) return;
  auto* mp = static_cast<JPH::SoftBodyMotionProperties*>(lock.GetBody().GetMotionProperties());
  JPH::Array<JPH::SoftBodyVertex>& v = mp->GetVertices();
  for (const Seam& m : seams_) {
    const JPH::SoftBodySharedSettings::Edge& e = s_->mEdgeConstraints[m.edge];
    JPH::SoftBodyVertex &a = v[e.mVertex[0]], &b = v[e.mVertex[1]];
    const float wsum = a.mInvMass + b.mInvMass;
    const JPH::Vec3 d = b.mPosition - a.mPosition;
    const float now = d.Length();
    if (wsum <= 0 || now <= 0 || now >= shut_) continue;
    const JPH::Vec3 move = d * (std::min(now, close_) / now / wsum);  // shared by weight, as the solver would
    a.mPosition += move * a.mInvMass;
    b.mPosition -= move * b.mInvMass;
  }
}

}  // namespace r3d::sim
