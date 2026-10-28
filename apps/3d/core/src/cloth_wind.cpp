#include "cloth_wind.h"

#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/SoftBody/SoftBodyMotionProperties.h>

#include <algorithm>
#include <cmath>
#include <vector>

namespace r3d::sim {

namespace {
constexpr double kAirDensity = 1.2, kPlateDrag = 1.2;   // as sim.cpp's air_drag
constexpr double kTwoPi = 6.28318530717958647692;
constexpr double kSlowS = 4.0, kSlowM = 1.6;            // the long gust: period (s), wavelength (m)
constexpr double kQuickS = 1.7, kQuickM = 0.7;          // the short flutter on top
constexpr double kLeast = 0.1;                           // the gusts' lull, of the full speed
constexpr double kMinAir = 0.25;                         // a cloth with Air 0 still feels a wind a little
}  // namespace

void cloth_wind(JPH::PhysicsSystem& physics, JPH::BodyInterface& bi, JPH::BodyID id, const Cloth& c, double k, double dt,
                double t) {
  if (!(c.wind > 0)) return;
  {
    JPH::BodyLockWrite lock(physics.GetBodyLockInterfaceNoLock(), id);
    if (!lock.Succeeded()) return;
    auto* mp = static_cast<JPH::SoftBodyMotionProperties*>(lock.GetBody().GetMotionProperties());
    JPH::Array<JPH::SoftBodyVertex>& v = mp->GetVertices();
    std::vector<JPH::Vec3> n(v.size(), JPH::Vec3::sZero());
    for (const auto& tri : c.triangles) {
      const JPH::Vec3 a = v[size_t(tri[0])].mPosition, b = v[size_t(tri[1])].mPosition, d = v[size_t(tri[2])].mPosition;
      const JPH::Vec3 f = (b - a).Cross(d - a);
      for (int i : tri) n[size_t(i)] += f;
    }
    const double turn = c.windTurn * kTwoPi / 360.0;
    const double dx = std::cos(turn), dz = -std::sin(turn);   // along the wind; across it: (-dz, dx)
    const double per = 0.5 * kAirDensity * kPlateDrag * std::max(kMinAir, c.air) / std::max(1e-3, c.weight);  // 1/m
    for (size_t i = 0; i < v.size(); ++i) {
      if (v[i].mInvMass <= 0 || n[i].LengthSq() <= 0) continue;
      const double x = double(v[i].mPosition.GetX()) / k, z = double(v[i].mPosition.GetZ()) / k;  // real metres
      const double along = x * dx + z * dz, across = -x * dz + z * dx;
      const double g = 0.6 * std::sin(kTwoPi * (t / kSlowS - along / kSlowM)) +
                       0.4 * std::sin(kTwoPi * (t / kQuickS - along / kQuickM) + 1.7 + kTwoPi * across / kSlowM);
      const double speed = c.wind * (kLeast + (1 - kLeast) * (0.5 + 0.5 * g));   // m/s, kLeast..1 of the wind
      const JPH::Vec3 nn = n[i].Normalized();
      const double u = speed * (dx * double(nn.GetX()) + dz * double(nn.GetZ()));        // the air's speed through the sheet
      const double vn = double((v[i].mVelocity / float(k)).Dot(nn));
      const double room = u - vn;                                                          // never past the air's own speed
      if (u == 0 || room * u <= 0) continue;
      const double dv = std::min(std::abs(room), per * u * u * dt);
      v[i].mVelocity += nn * float((u > 0 ? dv : -dv) * k);
    }
  }
  bi.ActivateBody(id);  // a soft body at rest sleeps, and a sleeping one ignores the push
}

}  // namespace r3d::sim
