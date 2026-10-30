// A cloth touching itself (round 5 of the 3D gaps): Jolt's soft bodies have no self-collision, so a sheet folding at a
// box's corners passed through its own layers and the judges saw crumpled spiky tabs. This keeps a cloth's points apart.
#pragma once
#include <Jolt/Jolt.h>

#include <Jolt/Physics/Body/BodyID.h>
#include <Jolt/Physics/PhysicsSystem.h>

#include <array>
#include <cstdint>
#include <vector>

#include "sim.h"

namespace r3d::sim {

// Once per physics step, after the step: every two points of the cloth closer than its thickness (0.9 of its typical edge,
// so no point can slip between the three corners of a triangle) are pushed apart to it, each by its share of the weight
// (a held or pinned point doesn't move), unless they were that close in the cloth's first shape (its own neighbours: one
// ring of the mesh; for a garment, also near each other across a seam, measured from a point's sewn partner). Their speed towards each other is taken away, and their sliding along each other slows a little
// (cloth on cloth), so the pass only ever takes energy out. No point moves more than a quarter of the thickness in one step (a
// garment landing in a heap is sorted out over a few steps instead of torn), and a garment's sewn pair moves together, never
// apart (the pass can't open a seam). Points are found through a spatial hash of cells 1.3 thicknesses
// wide, so a 96 × 96 sheet costs about a millisecond a step. A cloth that is asleep is left as it is.
class ClothSelf {
 public:
  ClothSelf(const Cloth& c, double k);  // k: the world's scale (sim.cpp)
  void step(JPH::PhysicsSystem& physics, JPH::BodyID id);
  double thickness() const { return h_; }  // in the scaled world

 private:
  std::vector<std::array<float, 3>> rest_;  // the first shape, scaled
  std::vector<int> sewn_;                   // a garment's point sewn to this one (cloth_sew.h), else -1
  std::vector<int> across_;                 // the partner of the sewn point nearest this one (itself if sewn), else -1
  std::vector<std::array<int, 2>> seams_;   // a garment's sewn pairs: the pass moves each pair together
  std::vector<JPH::Vec3> was_;              // scratch: each point before the pass
  double h_ = 0;
  bool own(size_t i, size_t j, float own2) const;  // neighbours in the first shape
  // scratch, kept between steps
  std::vector<std::array<int, 3>> cell_;
  std::vector<uint32_t> start_, sorted_;
  struct Pair { uint32_t a, b; };
  std::vector<Pair> pairs_;
};

}  // namespace r3d::sim
