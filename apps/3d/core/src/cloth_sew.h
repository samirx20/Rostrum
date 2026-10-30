// Sewing a garment (PR7, `seams` on a cloth): the pattern's pieces start apart around the body, flat or curved; each sewn pair
// of points (one piece's edge to another's) is a cloth edge of the solver's own (sim.cpp `cloth_settings`), as stiff as the
// solver allows, whose length shrinks evenly to nothing over the cloth's sewing time and then stays nothing: the solver pulls
// the pair together in the same passes that keep the cloth's own edges their length, so the cloth follows the seam instead of
// tearing round it, and a closed seam is held shut every pass rather than pulled shut after the step.
#pragma once
#include <Jolt/Jolt.h>

#include <Jolt/Physics/Body/BodyID.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/SoftBody/SoftBodySharedSettings.h>

#include <vector>

#include "sim.h"

namespace r3d::sim {

// Adds one edge per seam pair to `s` (after CreateConstraints, before Optimize), its rest length the pair's starting gap.
// Returns their indices into s->mEdgeConstraints before Optimize (`ClothSew` follows Optimize's renumbering).
std::vector<JPH::uint> add_seam_edges(JPH::SoftBodySharedSettings& s, const Cloth& c);

class ClothSew {
 public:
  // `s`: the cloth's own settings (shared with its body), `edges`: add_seam_edges' indices, `remap`: Optimize's edge remap
  ClothSew(JPH::Ref<JPH::SoftBodySharedSettings> s, const std::vector<JPH::uint>& edges, const JPH::Array<JPH::uint>& remap,
           const Cloth& c);
  // Before each physics step. `t`: seconds since the cloth started moving (its Falls from), at the end of this step. While
  // sewing (the first `sewTime` seconds) the cloth floats (no gravity) and every point keeps 0.9 of its speed per step, so the
  // pieces close round the body instead of falling past it; each seam's length is set to its share of the starting gap left
  // at the end of the step. Afterwards gravity is back and every seam's length is nothing.
  void before(JPH::PhysicsSystem& physics, JPH::BodyID id, double t);
  bool sewing(double t) const { return !seams_.empty() && t < time_; }

 private:
  struct Seam { JPH::uint edge; float gap; };  // gap: the starting length, scaled
  JPH::Ref<JPH::SoftBodySharedSettings> s_;
  std::vector<Seam> seams_;
  double time_ = 0;
};

}  // namespace r3d::sim
