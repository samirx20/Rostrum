// Sewing a garment (PR7, `seams` on a cloth): the pattern's pieces start apart around the body, flat or curved; each sewn pair
// of points (one piece's edge to another's) is pulled together over the cloth's sewing time and then held as one point.
#pragma once
#include <Jolt/Jolt.h>

#include <Jolt/Physics/Body/BodyID.h>
#include <Jolt/Physics/PhysicsSystem.h>

#include <vector>

#include "sim.h"

namespace r3d::sim {

// Once per physics step, after the step (and after ClothSelf, so a closing seam isn't pushed apart again). While sewing (the
// first `sewTime` seconds after the cloth starts), each pair's gap may be at most its starting gap × the share of the sewing
// time left: the two points are moved towards each other by their shares of the weight (a held point doesn't move), their
// speed apart is taken away, every point of the cloth loses a tenth of its speed per step and the cloth floats (no gravity),
// so the pieces close round the body instead of falling past it. After that each pair is one point: the same place and
// speed, every step, and gravity is back. A cloth without seams is left as it is.
class ClothSew {
 public:
  ClothSew(const Cloth& c, double k);  // k: the world's scale (sim.cpp)
  // `t`: seconds since the cloth started moving (its Falls from), after this step
  void step(JPH::PhysicsSystem& physics, JPH::BodyID id, double t);
  bool sewing(double t) const { return !pairs_.empty() && t < time_; }

 private:
  struct Pair { int a, b; float gap; };  // gap: at the start, scaled
  std::vector<Pair> pairs_;
  double time_ = 0;
};

}  // namespace r3d::sim
