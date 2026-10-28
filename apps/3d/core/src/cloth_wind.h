// A gentle moving air on a cloth (round 4 of the 3D gaps, `clothWind`): a settled drape in still air is frozen for the rest
// of the shot; a little breeze keeps its free edges and hanging sides breathing, as real fabric in a room does.
#pragma once
#include <Jolt/Jolt.h>

#include <Jolt/Physics/Body/BodyInterface.h>
#include <Jolt/Physics/PhysicsSystem.h>

#include "sim.h"

namespace r3d::sim {

// Once per physics step, while the cloth falls or rests: the air moves at `c.wind` m/s along `c.windTurn` degrees about the
// up axis (0 blows towards +x, 90 towards -z), in slow travelling gusts (two waves, about 4 s / 1.6 m and 1.7 s / 0.7 m,
// between about 0.1x and 1x the speed), so neighbouring parts of the sheet move differently. Each free point is pushed
// along its normal as a flat plate is (½ ρ Cd u² over the cloth's weight, with its Air: a light sheet moves more), never
// past the air's own speed. `t`: seconds since the simulation's start. Keeps the cloth awake (a resting soft body sleeps).
// Nothing at all when `c.wind` is 0, so a still-air result is the same as before.
void cloth_wind(JPH::PhysicsSystem& physics, JPH::BodyInterface& bi, JPH::BodyID id, const Cloth& c, double k, double dt,
                double t);

}  // namespace r3d::sim
