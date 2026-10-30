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
// first `sewTime` seconds after the cloth starts), each pair's gap shrinks evenly to nothing: the two points are given the
// speed towards each other (by their shares of the weight; a held point doesn't move) that brings the gap to its share at the
// end of the next step, so the solver's step pulls the cloth round them along with them; every point of the cloth loses a tenth of its speed per step and the cloth floats (no gravity),
// so the pieces close round the body instead of falling past it. After that gravity is back and a pair still apart keeps
// keeps closing by speed and is drawn together 2 mm a step until it is within 2 mm: from then on it is one point (the same place and
// speed every step). A pair the body holds apart stays open rather than tearing the cloth. A cloth without seams is left as it is.
class ClothSew {
 public:
  ClothSew(const Cloth& c, double k);  // k: the world's scale (sim.cpp)
  // `t`: seconds since the cloth started moving (its Falls from), after this step
  void step(JPH::PhysicsSystem& physics, JPH::BodyID id, double t, double dt);  // dt: one physics step, seconds
  bool sewing(double t) const { return !pairs_.empty() && t < time_; }

 private:
  struct Pair { int a, b; float gap; };  // gap: at the start, scaled
  std::vector<Pair> pairs_;
  double time_ = 0;
  float join_ = 0;  // scaled
};

}  // namespace r3d::sim
