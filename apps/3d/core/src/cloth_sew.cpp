// Sewing a garment (cloth_sew.h): seams as the solver's own edges. No code from elsewhere.
#include "cloth_sew.h"

#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/SoftBody/SoftBodyMotionProperties.h>

#include <algorithm>

namespace r3d::sim {

namespace {
constexpr float kSewDamping = 0.9f;  // speed kept per step while sewing
}  // namespace

std::vector<JPH::uint> add_seam_edges(JPH::SoftBodySharedSettings& s, const Cloth& c, float compliance) {
  std::vector<JPH::uint> out;
  for (const auto& p : c.seams) {
    if (p[0] < 0 || p[1] < 0 || size_t(p[0]) >= s.mVertices.size() || size_t(p[1]) >= s.mVertices.size()) continue;
    const JPH::Vec3 a(s.mVertices[size_t(p[0])].mPosition), b(s.mVertices[size_t(p[1])].mPosition);
    out.push_back(JPH::uint(s.mEdgeConstraints.size()));
    s.mEdgeConstraints.emplace_back(JPH::uint32(p[0]), JPH::uint32(p[1]), compliance);
    s.mEdgeConstraints.back().mRestLength = (b - a).Length();
  }
  return out;
}

ClothSew::ClothSew(JPH::Ref<JPH::SoftBodySharedSettings> s, const std::vector<JPH::uint>& edges,
                   const JPH::Array<JPH::uint>& remap, const Cloth& c)
    : s_(std::move(s)), time_(c.sewTime) {
  for (JPH::uint e : edges) {
    const JPH::uint at = e < remap.size() ? remap[e] : e;
    if (at < s_->mEdgeConstraints.size()) seams_.push_back({at, s_->mEdgeConstraints[at].mRestLength});
  }
}

void ClothSew::before(JPH::PhysicsSystem& physics, JPH::BodyID id, double t) {
  if (seams_.empty()) return;
  const bool sew = t < time_;
  const float left = sew ? float(std::max(0.0, 1.0 - t / time_)) : 0.0f;  // the share of each starting gap at the step's end
  for (const Seam& m : seams_) s_->mEdgeConstraints[m.edge].mRestLength = m.gap * left;  // between steps: the solver isn't reading
  JPH::BodyLockWrite lock(physics.GetBodyLockInterfaceNoLock(), id);
  if (!lock.Succeeded()) return;
  auto* mp = static_cast<JPH::SoftBodyMotionProperties*>(lock.GetBody().GetMotionProperties());
  mp->SetGravityFactor(sew ? 0.0f : 1.0f);
  if (sew)
    for (JPH::SoftBodyVertex& p : mp->GetVertices()) p.mVelocity *= kSewDamping;
}

}  // namespace r3d::sim
