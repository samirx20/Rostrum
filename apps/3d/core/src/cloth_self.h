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
// ring of the mesh). Their speed towards each other is taken away, and their sliding along each other slows a little
// (cloth on cloth), so the pass only ever takes energy out. Points are found through a spatial hash of cells 1.3 thicknesses
// wide, so a 96 × 96 sheet costs about a millisecond a step. A cloth that is asleep is left as it is.
class ClothSelf {
 public:
  ClothSelf(const Cloth& c, double k);  // k: the world's scale (sim.cpp)
  void step(JPH::PhysicsSystem& physics, JPH::BodyID id);
  double thickness() const { return h_; }  // in the scaled world

 private:
  std::vector<std::array<float, 3>> rest_;  // the first shape, scaled
  double h_ = 0;
  // scratch, kept between steps
  std::vector<std::array<int, 3>> cell_;
  std::vector<uint32_t> start_, sorted_;
  struct Pair { uint32_t a, b; };
  std::vector<Pair> pairs_;
};

}  // namespace r3d::sim
