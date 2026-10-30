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
constexpr double kMet = 0.001;       // m: a pair this close has met, and from then on holds like thread
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
    : s_(std::move(s)), time_(c.sewTime), met_(float(kMet * k)) {
  std::vector<bool> seam(s_->mEdgeConstraints.size(), false);
  for (JPH::uint e : edges) {
    const JPH::uint at = e < remap.size() ? remap[e] : e;
    if (at < s_->mEdgeConstraints.size()) {
      seams_.push_back({at, s_->mEdgeConstraints[at].mRestLength, s_->mEdgeConstraints[at].mCompliance});
      seam[at] = true;
    }
  }
  double sum = 0;  // the cloth's own edges' mean length
  size_t n = 0;
  for (size_t i = 0; i < seam.size(); ++i)
    if (!seam[i]) { sum += s_->mEdgeConstraints[i].mRestLength; ++n; }
  most_ = n ? float(kMostPull * sum / double(n)) : 0.0f;
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
  // quarter, and keeps pulling, rather than harder every step until the cloth beside it tears. Met (once within 1 mm):
  // nothing, as stiff as the solver allows, so the garment's weight hanging on it can't pull it open again.
  for (Seam& m : seams_) {
    JPH::SoftBodySharedSettings::Edge& e = s_->mEdgeConstraints[m.edge];
    const float now = (v[e.mVertex[1]].mPosition - v[e.mVertex[0]].mPosition).Length();
    m.met = m.met || now <= met_;
    e.mRestLength = m.met ? 0.0f : std::max(m.gap * left, now - most_);
    e.mCompliance = m.met ? 0.0f : m.compliance;
  }
  mp->SetGravityFactor(sew ? 0.0f : 1.0f);
  if (sew)
    for (JPH::SoftBodyVertex& p : mp->GetVertices()) p.mVelocity *= kSewDamping;
}

}  // namespace r3d::sim
