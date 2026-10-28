// Rigid bodies with Jolt (sim.h). The world is scaled so a typical falling body is about a metre across (Jolt's own
// tolerances — contact distance, sleep speeds, slop — are tuned for things that size; a 3 cm bud in metres would sink
// and jitter), and scaled back on the way out: gravity, speeds and masses scale with it, so the motion is the same.
// Cloth (brief 26b) is a Jolt soft body in the same world: it lands on the still bodies, the falling ones and the ground
// (Jolt soft bodies don't collide with each other or with themselves).
#include "sim.h"

#include <Jolt/Jolt.h>

#include <Jolt/Core/Factory.h>
#include <Jolt/Core/JobSystemSingleThreaded.h>
#include <Jolt/Core/TempAllocator.h>
#include <Jolt/Physics/Body/BodyCreationSettings.h>
#include <Jolt/Physics/Body/BodyFilter.h>
#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <Jolt/Physics/Collision/Shape/RotatedTranslatedShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/PhysicsSettings.h>
#include <Jolt/Physics/PhysicsSystem.h>
#include <Jolt/Physics/SoftBody/SoftBodyCreationSettings.h>
#include <Jolt/Physics/SoftBody/SoftBodyMotionProperties.h>
#include <Jolt/Physics/SoftBody/SoftBodySharedSettings.h>
#include <Jolt/RegisterTypes.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <map>
#include <mutex>
#include <set>

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
constexpr int kClothIterations = 8;
constexpr double kBendSoftest = 6.5, kBendRange = 6;  // bend compliance 10^(softest - range × Stiffness) × weight × edge²    // a cloth's solver passes per physics step (each a sub-step)
constexpr double kClothGap = 0.002;    // m: how far a cloth's points keep off what they touch (no flicker on a plinth)
constexpr double kTear = 4;            // an edge stretched past this many times its length: the cloth came apart

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

// A still Exact body whose surface is closed and convex (a box, a ball, a plinth) collides as a solid: Jolt's triangle mesh
// is a thin shell to a cloth (each point takes one triangle's plane, with no inside), and a light sheet over a box that
// stands on the ground crept off it, pulled by its points in the box-floor corner. The hull is kept only when it holds no
// more than the surface itself (within 1%), so a chair or a bowl still collides by its triangles. Its corners stay sharp, as
// drawn (Jolt rounds a hull inwards, and the drawn corner then poked through the cloth).
JPH::RefConst<JPH::Shape> solid_if_convex(const Body& b, double k) {
  double vol = 0;  // the closed surface's volume (its triangles' signed tetrahedra; an open one comes out small or off)
  for (size_t i = 0; i + 2 < b.triangles.size(); i += 3) {
    const JPH::Vec3 a = v3(b.triangles[i], k), c = v3(b.triangles[i + 1], k), d = v3(b.triangles[i + 2], k);
    vol += double(a.Dot(c.Cross(d))) / 6;
  }
  vol = std::abs(vol);
  if (b.points.size() < 4 || !(vol > 0)) return nullptr;
  JPH::Array<JPH::Vec3> pts;
  const size_t n = b.points.size(), stride = std::max<size_t>(1, n / kMaxHullPoints);
  for (size_t i = 0; i < n; i += stride) pts.push_back(v3(b.points[i], k));
  JPH::ConvexHullShapeSettings hs(pts, 0.0f);
  JPH::ShapeSettings::ShapeResult r = hs.Create();
  return r.HasError() || double(r.Get()->GetVolume()) > vol * 1.01 ? nullptr : r.Get();
}

JPH::RefConst<JPH::Shape> shape_of(const Body& b, double k) {
  if (b.shape == Body::Box) return box(b, k, b.falls);
  if (b.shape == Body::Sphere) return sphere(b, k, b.falls);
  if (b.falls) return hull(b, k);
  if (JPH::RefConst<JPH::Shape> solid = solid_if_convex(b, k)) return solid;
  return exact_mesh(b, k);
}

// The pinned side's points (sim.h Cloth::Pin): within 1% of that side of its world bounds at the start.
std::vector<bool> pinned_points(const Cloth& c) {
  std::vector<bool> out(c.points.size(), false);
  if (c.pinned == Cloth::None) return out;
  const int axis = c.pinned == Cloth::Top || c.pinned == Cloth::Bottom ? 1
                   : c.pinned == Cloth::Left || c.pinned == Cloth::Right ? 0 : 2;
  const bool high = c.pinned == Cloth::Top || c.pinned == Cloth::Right || c.pinned == Cloth::Front;
  V3 lo, hi;
  span(c.points, &lo, &hi);
  const double tol = 0.01 * (hi[size_t(axis)] - lo[size_t(axis)]) + 1e-6, edge = high ? hi[size_t(axis)] : lo[size_t(axis)];
  for (size_t i = 0; i < c.points.size(); ++i) out[i] = std::abs(c.points[i][size_t(axis)] - edge) <= tol;
  return out;
}

const char* side_name(Cloth::Pin p) {
  static const char* names[] = {"none", "top", "bottom", "left", "right", "front", "back"};
  return names[int(p)];
}

double dist(const V3& a, const V3& b) {
  return std::sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) + (a[2] - b[2]) * (a[2] - b[2]));
}

// A cloth as Jolt's soft body settings in the scaled world: a point weighs a third of its triangles (weight × area), a
// pinned point weighs nothing (Jolt holds it); edge, shear and bend constraints from the triangles, softer as Stiffness
// goes down. Compliances are set against the cloth's own mean point weight (and, for bending, its edge length), so the same
// Stiffness folds the same whatever its Weight or how fine it is: stretch at most a little (none at 1); bending is by the
// angle between neighbouring triangles (Jolt's dihedral constraint), from silk (0) through cotton (0.3, hangs in folds)
// to card (1). The old distance bend at a sub-step's scale held even 0.3 nearly flat: a sheet tented out over a box
// and, bent over its edge, sprang itself off it.
JPH::Ref<JPH::SoftBodySharedSettings> cloth_settings(const Cloth& c, double k, double sub_dt, int frame) {
  std::vector<double> mass(c.points.size(), 0.0);
  for (const auto& t : c.triangles) {
    const V3 &a = c.points[size_t(t[0])], &b = c.points[size_t(t[1])], &d = c.points[size_t(t[2])];
    const JPH::Vec3 u = v3({b[0] - a[0], b[1] - a[1], b[2] - a[2]}, 1.0), w = v3({d[0] - a[0], d[1] - a[1], d[2] - a[2]}, 1.0);
    const double area = 0.5 * double(u.Cross(w).Length());
    for (int i : t) mass[size_t(i)] += std::max(0.0, c.weight) * area / 3;
  }
  const std::vector<bool> pin = pinned_points(c);
  const size_t held = size_t(std::count(pin.begin(), pin.end(), true));
  if (held == c.points.size())
    throw Failure(c, frame, std::string("is flat along its ") + side_name(c.pinned) + " side, so pinning it holds all of it",
                  "pin a side it has an edge on (a sheet lying flat: Front, Back, Left or Right)");
  JPH::Ref<JPH::SoftBodySharedSettings> s = new JPH::SoftBodySharedSettings;
  s->mVertices.reserve(c.points.size());
  double inv_sum = 0;
  for (size_t i = 0; i < c.points.size(); ++i) {
    JPH::SoftBodySharedSettings::Vertex v;
    const JPH::Vec3 p = v3(c.points[i], k);
    v.mPosition = JPH::Float3(p.GetX(), p.GetY(), p.GetZ());
    const double m = std::max(1e-9, mass[i] * k * k * k);
    v.mInvMass = pin[i] ? 0.0f : float(1.0 / m);
    if (!pin[i]) inv_sum += 1.0 / m;
    s->mVertices.push_back(v);
  }
  for (const auto& t : c.triangles)
    s->AddFace(JPH::SoftBodySharedSettings::Face(JPH::uint32(t[0]), JPH::uint32(t[1]), JPH::uint32(t[2])));
  const double st = std::clamp(c.stiffness, 0.0, 1.0);
  const double base = inv_sum / double(c.points.size() - held) * sub_dt * sub_dt;  // a constraint at this gives half way
  const double w = inv_sum / double(c.points.size() - held);  // mean inverse point weight
  double edge = 0;                                             // mean edge length
  for (const auto& t : c.triangles)
    for (int q = 0; q < 3; ++q) edge += dist(c.points[size_t(t[q])], c.points[size_t(t[(q + 1) % 3])]) * k;
  edge /= double(3 * c.triangles.size());
  const float stretch = float(0.02 * (1 - st) * base), shear = float(1e-6 * w);
  const float bend = float(std::pow(10.0, kBendSoftest - kBendRange * st) * w * edge * edge);
  using SS = JPH::SoftBodySharedSettings;
  const SS::VertexAttributes va(stretch, shear, bend, held ? SS::ELRAType::EuclideanDistance : SS::ELRAType::None, 1.03f);
  s->CreateConstraints(&va, 1, SS::EBendType::Dihedral);
  s->Optimize();
  return s;
}

std::string mm(double metres) { return std::to_string(std::max(1, int(std::ceil(metres * 1000)))) + " mm"; }

}  // namespace

Result run(const Setup& setup, const std::vector<Body>& bodies, const std::vector<Cloth>& cloths,
           const std::function<void(int, int, int)>& progress) {
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
  for (const Cloth& c : cloths) {
    if (c.triangles.empty() || c.points.empty())
      throw Error("simulate: " + c.name() + " has no surface to drape: give it a shape (a plane drapes best), or set Simulate to Off");
    sizes.push_back(span(c.points));
  }
  if (sizes.empty()) throw Error("simulate: nothing falls: set Simulate › Falls or Cloth on the things that should move");
  std::nth_element(sizes.begin(), sizes.begin() + sizes.size() / 2, sizes.end());
  const double k = std::clamp(1.0 / std::max(1e-4, sizes[sizes.size() / 2]), 0.01, 100.0);

  Layers layers;
  LayerVsBroad layer_vs_broad;
  LayerPairs pairs;
  JPH::PhysicsSystem physics;
  const JPH::uint max_bodies = JPH::uint(bodies.size() + cloths.size() + 8);
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
                                !b.falls ? JPH::EMotionType::Static : b.wake > 0 ? JPH::EMotionType::Kinematic
                                                                                 : JPH::EMotionType::Dynamic,
                                b.falls ? kMoving : kStill);
    s.mAllowDynamicOrKinematic = b.falls && b.wake > 0;  // held still (kinematic) until its Falls from frame
    s.mRestitution = float(std::clamp(b.bounce, 0.0, 1.0));
    s.mFriction = float(std::max(0.0, b.friction));
    if (b.falls) {
      s.mMotionQuality = JPH::EMotionQuality::LinearCast;  // a small fast thing never tunnels through a thin wall
      s.mLinearVelocity = b.wake > 0 ? JPH::Vec3::sZero() : v3(b.velocity, k);  // a held one gets it when it falls
      if (b.mass > 0) {
        s.mOverrideMassProperties = JPH::EOverrideMassProperties::CalculateInertia;
        s.mMassPropertiesOverride.mMass = float(b.mass * k * k * k);
      }
    } else {
      const JPH::Quat q = JPH::Quat(float(b.rot[0]), float(b.rot[1]), float(b.rot[2]), float(b.rot[3])).Normalized();
      for (const V3& p : b.points.empty() ? b.triangles : b.points)  // its lowest point (world)
        floor = std::min(floor, b.pos[1] + double((q * v3(p, 1.0)).GetY()));
    }
    ids[i] = bi.CreateAndAddBody(s, b.falls && !b.asleep && b.wake == 0 ? JPH::EActivation::Activate : JPH::EActivation::DontActivate);
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
    if (b.asleep || b.wake > 0) continue;
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

  // how far a cloth's points keep off what they touch: at least kClothGap, and half its typical edge, since a triangle
  // between two points bridges a sharp corner (a plinth's edge showed through a 2 cm grid at 2 mm, a box's top corner
  // through a 2.5 cm grid at a third: the critic's "dark notch"); half an edge clears a right-angled corner
  const auto cloth_gap = [](const Cloth& cl) {
    std::vector<double> e;
    for (const auto& t : cl.triangles)
      for (int i = 0; i < 3; ++i) {
        const V3 &a = cl.points[size_t(t[i])], &b = cl.points[size_t(t[(i + 1) % 3])];
        e.push_back(std::sqrt((a[0] - b[0]) * (a[0] - b[0]) + (a[1] - b[1]) * (a[1] - b[1]) + (a[2] - b[2]) * (a[2] - b[2])));
      }
    if (e.empty()) return kClothGap;
    std::nth_element(e.begin(), e.begin() + long(e.size() / 2), e.end());
    return std::max(kClothGap, e[e.size() / 2] / 2);
  };

  const int frames = setup.end - setup.start + 1;
  const int steps = std::max(1, int(std::ceil(kStepsPerSecond / setup.fps)));
  const float dt = float(1.0 / setup.fps / steps);

  // the cloths, after the starts-inside test (a cloth may start lying on something)
  struct Edge { int a, b; double rest; };
  std::vector<JPH::BodyID> cloth_ids;
  std::vector<std::vector<Edge>> cloth_edges(cloths.size());
  std::vector<double> cloth_lowest(cloths.size());
  for (size_t c = 0; c < cloths.size(); ++c) {
    const Cloth& cl = cloths[c];
    JPH::SoftBodyCreationSettings sb(cloth_settings(cl, k, double(dt) / kClothIterations, setup.start), JPH::RVec3::sZero(),
                                     JPH::Quat::sIdentity(), kMoving);
    sb.mNumIterations = kClothIterations;
    sb.mFriction = float(std::max(0.0, cl.friction));
    sb.mRestitution = 0.0f;
    sb.mVertexRadius = float(cloth_gap(cl) * k);
    sb.mFacesDoubleSided = true;
    const JPH::BodyID id = bi.CreateAndAddSoftBody(sb, JPH::EActivation::Activate);
    if (id.IsInvalid()) throw Error("simulate: too many bodies (" + std::to_string(bodies.size() + cloths.size()) + ")");
    cloth_ids.push_back(id);
    std::set<std::pair<int, int>> seen;
    for (const auto& t : cl.triangles)
      for (size_t e = 0; e < 3; ++e) {
        const int a = std::min(t[e], t[(e + 1) % 3]), b = std::max(t[e], t[(e + 1) % 3]);
        if (seen.insert({a, b}).second) cloth_edges[c].push_back({a, b, dist(cl.points[size_t(a)], cl.points[size_t(b)])});
      }
    V3 lo;
    span(cl.points, &lo);
    cloth_lowest[c] = std::min(floor, lo[1]) - std::max(5.0, 20 * span(cl.points));
  }
  out.cloth.resize(cloths.size());
  for (size_t c = 0; c < cloths.size(); ++c) out.cloth[c].reserve(size_t(frames) * cloths[c].points.size() * 3);
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
    for (int r : out.rows)  // Falls from: held still until its frame, then it falls (with its keyed speed)
      if (const Body& b = bodies[size_t(r)]; b.wake > 0 && b.wake == f) {
        bi.SetMotionType(ids[size_t(r)], JPH::EMotionType::Dynamic, b.asleep ? JPH::EActivation::DontActivate : JPH::EActivation::Activate);
        if (!b.asleep) bi.SetLinearVelocity(ids[size_t(r)], v3(b.velocity, k));
      }
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
    for (size_t c = 0; c < cloths.size(); ++c) {
      const Cloth& cl = cloths[c];
      JPH::BodyLockRead lock(physics.GetBodyLockInterfaceNoLock(), cloth_ids[c]);
      if (!lock.Succeeded()) throw Error("simulate: " + cl.name() + " was lost by the physics");
      const JPH::Body& body = lock.GetBody();
      const auto* mp = static_cast<const JPH::SoftBodyMotionProperties*>(body.GetMotionProperties());
      const JPH::RMat44 com = body.GetCenterOfMassTransform();
      std::vector<float>& rows = out.cloth[c];
      const size_t at = rows.size();
      double top = -1e30, fastest = 0, farthest = 0;
      size_t i = 0;
      for (const JPH::SoftBodyVertex& v : mp->GetVertices()) {
        if (i >= cl.points.size()) break;
        const JPH::RVec3 w = com * v.mPosition;
        const V3 p{double(w.GetX()) / k, double(w.GetY()) / k, double(w.GetZ()) / k};
        for (double x : p) rows.push_back(float(x));
        top = std::max(top, p[1]);
        fastest = std::max(fastest, double(v.mVelocity.Length()) / k);
        farthest = std::max(farthest, dist(p, cl.points[i++]));
        if (!std::isfinite(p[0]) || !std::isfinite(p[1]) || !std::isfinite(p[2])) fastest = 1e30;
      }
      if (i != cl.points.size())
        throw Error("simulate: " + cl.name() + ": the physics gave " + std::to_string(i) + " points, not " + std::to_string(cl.points.size()));
      if (!std::isfinite(fastest) || fastest > 200 || farthest > 1000)
        throw Failure(cl, setup.start + f, "flew apart",
                      "lower its Stiffness, raise its Weight, or check it doesn't start inside or right against something");
      for (const Edge& e : cloth_edges[c]) {
        const float* a = &rows[at + size_t(e.a) * 3];
        const float* b = &rows[at + size_t(e.b) * 3];
        const double len = dist({a[0], a[1], a[2]}, {b[0], b[1], b[2]});
        if (len > kTear * e.rest + 1e-4)
          throw Failure(cl, setup.start + f, "tore apart (an edge stretched to " + std::to_string(int(len / std::max(1e-9, e.rest))) + " times its length)",
                        "check it doesn't start inside something, lower its Stiffness, or pin fewer points");
      }
      if (top < cloth_lowest[c])
        throw Failure(cl, setup.start + f, "fell past everything",
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
