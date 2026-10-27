// Rigid bodies with Jolt (sim.h). The world is scaled so a typical falling body is about a metre across (Jolt's own
// tolerances — contact distance, sleep speeds, slop — are tuned for things that size; a 3 cm bud in metres would sink
// and jitter), and scaled back on the way out: gravity, speeds and masses scale with it, so the motion is the same.
#include "sim.h"

#include <Jolt/Jolt.h>

#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Body/BodyFilter.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <Jolt/Physics/Collision/Shape/RotatedTranslatedShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/RegisterTypes.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <map>
#include <mutex>

namespace r3d::sim {

std::string jolt_version() {
  return std::to_string(JPH_VERSION_MAJOR) + "." + std::to_string(JPH_VERSION_MINOR) + "." + std::to_string(JPH_VERSION_PATCH);
}

namespace {

constexpr double kPlastic = 1100;      // kg/m³: "Mass from size, as solid plastic"
constexpr double kGravity = 9.81;
constexpr int kStepsPerSecond = 240;   // physics steps; a 24 fps frame is 10 of them
constexpr int kMaxHullPoints = 4000;   // more points than this are thinned (the hull keeps at most 256 anyway)
constexpr JPH::ObjectLayer kStill = 0, kMoving = 1;

void once() {
  static std::once_flag f;
  std::call_once(f, [] {
    JPH::RegisterDefaultAllocator();
    JPH::Factory::sInstance = new JPH::Factory();
    JPH::RegisterTypes();
  });
}

class Layers final : public JPH::BroadPhaseLayerInterface {
 public:
  JPH::uint GetNumBroadPhaseLayers() const override { return 2; }
  JPH::BroadPhaseLayer GetBroadPhaseLayer(JPH::ObjectLayer l) const override {
    return JPH::BroadPhaseLayer(JPH::BroadPhaseLayer::Type(l));
  }
#if defined(JPH_EXTERNAL_PROFILE) || defined(JPH_PROFILE_ENABLED)
  const char* GetBroadPhaseLayerName(JPH::BroadPhaseLayer l) const override { return l.GetValue() ? "moving" : "still"; }
#endif
};

class LayerVsBroad final : public JPH::ObjectVsBroadPhaseLayerFilter {
 public:
  bool ShouldCollide(JPH::ObjectLayer o, JPH::BroadPhaseLayer b) const override {
    return o == kMoving || b.GetValue() == kMoving;
  }
};

class LayerPairs final : public JPH::ObjectLayerPairFilter {
 public:
  bool ShouldCollide(JPH::ObjectLayer a, JPH::ObjectLayer b) const override { return a == kMoving || b == kMoving; }
};

double span(const std::vector<V3>& pts, V3* lo_out = nullptr, V3* hi_out = nullptr) {
  V3 lo{1e30, 1e30, 1e30}, hi{-1e30, -1e30, -1e30};
  for (const V3& p : pts)
    for (int k = 0; k < 3; ++k) { lo[k] = std::min(lo[k], p[k]); hi[k] = std::max(hi[k], p[k]); }
  if (lo_out) *lo_out = lo;
  if (hi_out) *hi_out = hi;
  if (pts.empty()) return 0;
  return std::sqrt((hi[0] - lo[0]) * (hi[0] - lo[0]) + (hi[1] - lo[1]) * (hi[1] - lo[1]) + (hi[2] - lo[2]) * (hi[2] - lo[2]));
}

JPH::Vec3 v3(const V3& p, double k) { return JPH::Vec3(float(p[0] * k), float(p[1] * k), float(p[2] * k)); }

JPH::RefConst<JPH::Shape> made(JPH::ShapeSettings& s, const Body& b, const char* what) {
  JPH::ShapeSettings::ShapeResult r = s.Create();
  if (r.HasError())
    throw Error("simulate: " + b.name() + "'s " + what + " shape can't be built (" + std::string(r.GetError().c_str()) +
                "): set its Shape to Box or Sphere");
  return r.Get();
}

// a box round the points (its own frame), moved to their middle
JPH::RefConst<JPH::Shape> box(const Body& b, double k, bool density) {
  V3 lo, hi;
  span(b.points, &lo, &hi);
  const float least = 0.005f;  // a flat thing (a card, a plane) still gets some thickness
  JPH::Vec3 half(std::max(least, float((hi[0] - lo[0]) * k / 2)), std::max(least, float((hi[1] - lo[1]) * k / 2)),
                 std::max(least, float((hi[2] - lo[2]) * k / 2)));
  JPH::BoxShapeSettings bs(half, std::min(0.05f, 0.4f * half.ReduceMin()));
  if (density) bs.SetDensity(float(kPlastic));
  JPH::RotatedTranslatedShapeSettings rt(v3({(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2}, k),
                                         JPH::Quat::sIdentity(), made(bs, b, "box"));
  return made(rt, b, "box");
}

JPH::RefConst<JPH::Shape> sphere(const Body& b, double k, bool density) {
  V3 lo, hi;
  span(b.points, &lo, &hi);
  const V3 mid{(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2};
  double r = 0;
  for (const V3& p : b.points)
    r = std::max(r, std::sqrt((p[0] - mid[0]) * (p[0] - mid[0]) + (p[1] - mid[1]) * (p[1] - mid[1]) + (p[2] - mid[2]) * (p[2] - mid[2])));
  JPH::SphereShapeSettings ss(std::max(0.005f, float(r * k)));
  if (density) ss.SetDensity(float(kPlastic));
  JPH::RotatedTranslatedShapeSettings rt(v3(mid, k), JPH::Quat::sIdentity(), made(ss, b, "sphere"));
  return made(rt, b, "sphere");
}

JPH::RefConst<JPH::Shape> hull(const Body& b, double k) {
  JPH::Array<JPH::Vec3> pts;
  const size_t n = b.points.size(), stride = std::max<size_t>(1, n / kMaxHullPoints);
  // the thinned points, plus the extremes along each axis (thinning never cuts a corner off the outline)
  size_t ext[6] = {0, 0, 0, 0, 0, 0};
  for (size_t i = 0; i < n; ++i)
    for (int a = 0; a < 3; ++a) {
      if (b.points[i][a] < b.points[ext[2 * a]][a]) ext[2 * a] = i;
      if (b.points[i][a] > b.points[ext[2 * a + 1]][a]) ext[2 * a + 1] = i;
    }
  for (size_t i = 0; i < n; i += stride) pts.push_back(v3(b.points[i], k));
  for (size_t e : ext) pts.push_back(v3(b.points[e], k));
  JPH::ConvexHullShapeSettings hs(pts, 0.05f);
  hs.SetDensity(float(kPlastic));
  JPH::ShapeSettings::ShapeResult r = hs.Create();
  if (r.HasError()) return box(b, k, true);  // flat or a line: no hull, a thin box instead
  return r.Get();
}

JPH::RefConst<JPH::Shape> exact_mesh(const Body& b, double k) {
  JPH::TriangleList tris;
  for (size_t i = 0; i + 2 < b.triangles.size(); i += 3) {
    const JPH::Vec3 a = v3(b.triangles[i], k), c = v3(b.triangles[i + 1], k), d = v3(b.triangles[i + 2], k);
    if ((c - a).Cross(d - a).LengthSq() < 1e-14f) continue;  // a sliver: Jolt refuses degenerate triangles
    tris.push_back(JPH::Triangle(JPH::Float3(a.GetX(), a.GetY(), a.GetZ()), JPH::Float3(c.GetX(), c.GetY(), c.GetZ()),
                                 JPH::Float3(d.GetX(), d.GetY(), d.GetZ())));
  }
  if (tris.empty()) throw Error("simulate: " + b.name() + " has no surface to collide with: give it a shape, or set Simulate to Off");
  JPH::MeshShapeSettings ms(tris);
  return made(ms, b, "exact");
}

JPH::RefConst<JPH::Shape> shape_of(const Body& b, double k) {
  if (b.shape == Body::Box) return box(b, k, b.falls);
  if (b.shape == Body::Sphere) return sphere(b, k, b.falls);
  return b.falls ? hull(b, k) : exact_mesh(b, k);
}

std::string mm(double metres) { return std::to_string(std::max(1, int(std::ceil(metres * 1000)))) + " mm"; }

}  // namespace

Result run(const Setup& setup, const std::vector<Body>& bodies, const std::function<void(int, int, int)>& progress) {
  using Clock = std::chrono::steady_clock;
  const auto t0 = Clock::now();
  once();
  Result out;
  if (setup.end < setup.start) throw Error("simulate: end is before start");
  if (!(setup.fps > 0)) throw Error("simulate.fps: needs a number above 0");

  // the scale: a typical falling body about a metre across
  std::vector<double> sizes;
  for (const Body& b : bodies)
    if (b.falls) {
      if (b.points.empty()) throw Error("simulate: " + b.name() + " has no surface to simulate: give it a shape, or set Simulate to Off");
      sizes.push_back(span(b.points));
    }
  if (sizes.empty()) throw Error("simulate: nothing falls: set Simulate › Falls on the things that should move");
  std::nth_element(sizes.begin(), sizes.begin() + sizes.size() / 2, sizes.end());
  const double k = std::clamp(1.0 / std::max(1e-4, sizes[sizes.size() / 2]), 0.01, 100.0);

  Layers layers;
  LayerVsBroad layer_vs_broad;
  LayerPairs pairs;
  JPH::PhysicsSystem physics;
  const JPH::uint max_bodies = JPH::uint(bodies.size() + 8);
  physics.Init(max_bodies, 0, std::max<JPH::uint>(1024, max_bodies * 16), std::max<JPH::uint>(1024, max_bodies * 32), layers,
               layer_vs_broad, pairs);
  physics.SetGravity(JPH::Vec3(0, float(-kGravity * k), 0));
  JPH::BodyInterface& bi = physics.GetBodyInterfaceNoLock();

  // the ground: a wide slab whose top is at groundY
  double floor = 1e30;
  if (setup.ground) {
    JPH::BodyCreationSettings g(new JPH::BoxShape(JPH::Vec3(1e4f, 1.0f, 1e4f)),
                                JPH::RVec3(0, setup.groundY * k - 1.0, 0), JPH::Quat::sIdentity(), JPH::EMotionType::Static, kStill);
    g.mFriction = 0.6f;
    g.mRestitution = 0.2f;
    bi.CreateAndAddBody(g, JPH::EActivation::DontActivate);
    floor = setup.groundY;
  }

  std::vector<JPH::BodyID> ids(bodies.size());
  std::map<JPH::BodyID, size_t> which;
  for (size_t i = 0; i < bodies.size(); ++i) {
    const Body& b = bodies[i];
    JPH::RefConst<JPH::Shape> shape = shape_of(b, k);
    JPH::BodyCreationSettings s(shape, JPH::RVec3(b.pos[0] * k, b.pos[1] * k, b.pos[2] * k),
                                JPH::Quat(float(b.rot[0]), float(b.rot[1]), float(b.rot[2]), float(b.rot[3])).Normalized(),
                                b.falls ? JPH::EMotionType::Dynamic : JPH::EMotionType::Static, b.falls ? kMoving : kStill);
    s.mRestitution = float(std::clamp(b.bounce, 0.0, 1.0));
    s.mFriction = float(std::max(0.0, b.friction));
    if (b.falls) {
      s.mMotionQuality = JPH::EMotionQuality::LinearCast;  // a small fast thing never tunnels through a thin wall
      s.mLinearVelocity = v3(b.velocity, k);
      if (b.mass > 0) {
        s.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
        s.mMassPropertiesOverride.mMass = float(b.mass * k * k * k);
      }
    } else {
      const JPH::Quat q = JPH::Quat(float(b.rot[0]), float(b.rot[1]), float(b.rot[2]), float(b.rot[3])).Normalized();
      for (const V3& p : b.points.empty() ? b.triangles : b.points)  // its lowest point (world)
        floor = std::min(floor, b.pos[1] + double((q * v3(p, 1.0)).GetY()));
    }
    ids[i] = bi.CreateAndAddBody(s, b.falls && !b.asleep ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
    if (ids[i].IsInvalid()) throw Error("simulate: too many bodies (" + std::to_string(bodies.size()) + ")");
    which[ids[i]] = i;
    if (b.falls) out.rows.push_back(int(i));
  }
  physics.OptimizeBroadPhase();

  // nothing that starts moving may start inside something else
  JPH::CollideShapeSettings cs;
  cs.mBackFaceMode = JPH::EBackFaceMode::CollideWithBackFaces;
  for (int r : out.rows) {
    const Body& b = bodies[size_t(r)];
    if (b.asleep) continue;
    JPH::AllHitCollisionCollector<JPH::CollideShapeCollector> hits;
    const JPH::IgnoreSingleBodyFilter self(ids[size_t(r)]);
    physics.GetNarrowPhaseQuery().CollideShape(bi.GetShape(ids[size_t(r)]), JPH::Vec3::sReplicate(1.0f),
                                               bi.GetCenterOfMassTransform(ids[size_t(r)]), cs, JPH::RVec3::sZero(), hits, {}, {}, self);
    const double tolerance = std::max(0.0005 * k, 0.02 * sizes[sizes.size() / 2] * k);
    const JPH::CollideShapeResult* worst = nullptr;
    for (const auto& h : hits.mHits)
      if (h.mPenetrationDepth > tolerance && (!worst || h.mPenetrationDepth > worst->mPenetrationDepth)) worst = &h;
    if (!worst) continue;
    const auto other = which.find(worst->mBodyID2);
    const std::string into = other == which.end() ? "the ground" : bodies[other->second].name();
    // what a person does: lift it. The least lift that clears it (a few hundred tests at most), else the way out
    const auto clear_at = [&](double up) {
      JPH::AllHitCollisionCollector<JPH::CollideShapeCollector> again;
      const JPH::RMat44 at = bi.GetCenterOfMassTransform(ids[size_t(r)]).PostTranslated(JPH::Vec3(0, float(up), 0));
      physics.GetNarrowPhaseQuery().CollideShape(bi.GetShape(ids[size_t(r)]), JPH::Vec3::sReplicate(1.0f), at, cs,
                                                 JPH::RVec3::sZero(), again, {}, {}, self);
      for (const auto& h : again.mHits)
        if (h.mPenetrationDepth > tolerance) return false;
      return true;
    };
    const double step = std::max(0.001 * k, sizes[sizes.size() / 2] * k / 100), reach = 3 * span(b.points) * k;
    double lift = -1;
    for (double up = step; up <= reach && lift < 0; up += step)
      if (clear_at(up)) lift = up;
    const JPH::Vec3 away = -worst->mPenetrationAxis.Normalized();  // moves this body out
    const std::string by = mm(worst->mPenetrationDepth / k + 0.001);
    const std::string move = lift > 0 ? "move it up " + mm(lift / k + 0.001)
                             : away.GetY() < -0.7f ? "move it down " + by
                                                   : "move it " + by + " away from " + into;
    throw Failure(b, setup.start, "starts inside " + into, move + " or set Starts: Asleep until hit");
  }

  const int frames = setup.end - setup.start + 1;
  const int steps = std::max(1, int(std::ceil(kStepsPerSecond / setup.fps)));
  const float dt = float(1.0 / setup.fps / steps);
  JPH::TempAllocatorImpl temp(32 * 1024 * 1024);
  JPH::JobSystemSingleThreaded jobs(JPH::cMaxPhysicsJobs);
  std::vector<double> lowest(out.rows.size());
  for (size_t j = 0; j < out.rows.size(); ++j) {
    const Body& b = bodies[size_t(out.rows[j])];
    lowest[j] = std::min(floor, b.pos[1]) - std::max(5.0, 20 * span(b.points));  // below this it fell past everything
  }
  const auto t_steps = Clock::now();
  out.frames.resize(size_t(frames));
  for (int f = 0; f < frames; ++f) {
    if (f > 0)
      for (int s = 0; s < steps; ++s) {
        const JPH::EPhysicsUpdateError e = physics.Update(dt, 1, &temp, &jobs);
        if (e != JPH::EPhysicsUpdateError::None)
          throw Error("simulate: the physics ran out of room at frame " + std::to_string(setup.start + f) +
                      " (too many things touching at once): simulate fewer bodies, or give them Shape: Box");
      }
    auto& row = out.frames[size_t(f)];
    row.resize(out.rows.size());
    for (size_t j = 0; j < out.rows.size(); ++j) {
      const Body& b = bodies[size_t(out.rows[j])];
      const JPH::BodyID id = ids[size_t(out.rows[j])];
      JPH::RVec3 p;
      JPH::Quat q;
      bi.GetPositionAndRotation(id, p, q);
      row[j] = {{double(p.GetX()) / k, double(p.GetY()) / k, double(p.GetZ()) / k},
                {double(q.GetX()), double(q.GetY()), double(q.GetZ()), double(q.GetW())}};
      const double speed = double(bi.GetLinearVelocity(id).Length()) / k;
      const double dx = row[j].pos[0] - b.pos[0], dy = row[j].pos[1] - b.pos[1], dz = row[j].pos[2] - b.pos[2];
      if (!std::isfinite(speed) || speed > 200 || std::sqrt(dx * dx + dy * dy + dz * dz) > 1000)
        throw Failure(b, setup.start + f, "flew away",
                      "lower its Bounce, or check it doesn't start inside or right against something");
      if (row[j].pos[1] < lowest[j])
        throw Failure(b, setup.start + f, "fell past everything",
                      "there is nothing under it: turn the ground on, or set what it should land on to Simulate › Stays still");
    }
    if (progress) progress(f + 1, frames, setup.start + f);
  }
  for (size_t j = 0; j < out.rows.size(); ++j) {
    const JPH::BodyID id = ids[size_t(out.rows[j])];
    if (!bi.IsActive(id) || double(bi.GetLinearVelocity(id).Length()) / k < 0.01) ++out.atRest;
  }
  const auto now = Clock::now();
  out.ms = std::chrono::duration<double, std::milli>(now - t0).count();
  out.frameMs = std::chrono::duration<double, std::milli>(now - t_steps).count() / frames;
  return out;
}

}  // namespace r3d::sim
