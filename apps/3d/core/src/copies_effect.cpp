// The effectors of a copies item ("Change near", ENGINE_CONTRACT.md § 2, Copies): reading them from the node, and how much
// each changes a copy: its field shape (sphere, plane, noise) and falloff. What the change does is in copies.cpp (apply).
#include <pxr/base/gf/vec3d.h>

#include <algorithm>
#include <climits>
#include <cmath>
#include <cstdint>

#include "copies.h"
#include "item_track.h"
#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace copies {
namespace {

double number(const JsValue& v, const std::string& where) {
  if (!is_number(v)) fail(where, "is " + v.GetTypeName(), "a number");
  const double d = to_number(v);
  if (!std::isfinite(d)) fail(where, "is not finite", "a finite number");
  return d;
}

template <class T, class F>
std::vector<T> track(Reader& anim, const std::string& key, size_t frames, T single, F read) {
  if (!anim.has(key)) return {single};
  const JsArray& a = anim.list(key);
  if (a.size() != frames)
    fail(anim.at(key), std::to_string(a.size()) + " values", std::to_string(frames) + " values, one per frame");
  std::vector<T> out;
  for (size_t i = 0; i < a.size(); ++i) out.push_back(read(a[i], anim.at(key) + "[" + std::to_string(i) + "]"));
  return out;
}

GfVec3f unit(const JsValue& v, const std::string& where) {
  GfVec3f n = Reader::vec3_of(v, where);
  if (n.Normalize() < 1e-6f) fail(where, "has no length", "a direction [x, y, z] (the plane's normal, world)");
  return n;
}

// Value noise, 0..1, the same on every run and machine: a number per whole-numbered corner from (seed, corner), blended
// smoothly (quintic) between the 8 corners round p.
uint64_t mix(uint64_t x) {
  x += 0x9E3779B97F4A7C15ull;
  x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
  x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
  return x ^ (x >> 31);
}
double corner(unsigned seed, int64_t x, int64_t y, int64_t z) {
  const uint64_t h = mix(mix(mix(uint64_t(seed) ^ 0xC0FFEEull) ^ uint64_t(x)) ^ mix(uint64_t(y) * 31 + uint64_t(z)));
  return double(h >> 11) * (1.0 / 9007199254740992.0);
}
double noise(unsigned seed, const GfVec3d& p) {
  const double fx = std::floor(p[0]), fy = std::floor(p[1]), fz = std::floor(p[2]);
  const int64_t x = int64_t(fx), y = int64_t(fy), z = int64_t(fz);
  const auto ease = [](double t) { return t * t * t * (t * (t * 6 - 15) + 10); };
  const double u = ease(p[0] - fx), v = ease(p[1] - fy), w = ease(p[2] - fz);
  const auto lerp = [](double a, double b, double t) { return a + (b - a) * t; };
  double c[2][2];
  for (int j = 0; j < 2; ++j)
    for (int k = 0; k < 2; ++k)
      c[j][k] = lerp(corner(seed, x, y + j, z + k), corner(seed, x + 1, y + j, z + k), u);
  return lerp(lerp(c[0][0], c[1][0], v), lerp(c[0][1], c[1][1], v), w);
}

}  // namespace

std::vector<Effector> read_effectors(const JsArray& list, const std::string& where, size_t frames) {
  std::vector<Effector> out;
  for (size_t i = 0; i < list.size(); ++i) {
    const std::string w = where + "[" + std::to_string(i) + "]";
    if (!list[i].IsObject()) fail(w, "is " + list[i].GetTypeName(), "an effector object");
    Reader r(list[i].GetJsObject(), w);
    Effector e;
    e.id = r.str("id");
    static const std::vector<std::string> kinds = {"scale", "turn", "push", "move", "hide", "colour"};
    e.kind = Effector::Kind(std::find(kinds.begin(), kinds.end(), r.one_of("kind", kinds)) - kinds.begin());
    // (v1.31) `field` left out: a sphere, as every older scene
    const std::string field = r.has("field") ? r.one_of("field", {"sphere", "plane", "noise"}) : "sphere";
    e.field = field == "plane" ? Effector::Plane : field == "noise" ? Effector::Noise : Effector::Sphere;
    if (e.field == Effector::Noise) e.seed = unsigned(r.count("seed", 0, INT_MAX));
    e.smooth = r.one_of("falloff", {"smooth", "linear"}) == "smooth";
    const std::string axis = r.one_of("axis", {"x", "y", "z"});
    e.axis = axis == "x" ? 0 : axis == "y" ? 1 : 2;
    const double radius = r.num_min("radius", 0, true), amount = r.num("amount");
    const GfVec3f colour = r.vec3("colour"), centre = r.vec3("centre");
    static const JsObject none;
    Reader anim(r.has("anim") ? r.object("anim") : none, w + ".anim");
    const auto num = [](const JsValue& v, const std::string& at) { return number(v, at); };
    e.centre = track<GfVec3f>(anim, "centre", frames, centre, Reader::vec3_of);
    e.colour = track<GfVec3f>(anim, "colour", frames, colour, Reader::vec3_of);
    e.amount = track<double>(anim, "amount", frames, amount, num);
    e.radius = track<double>(anim, "radius", frames, radius, num);
    if (e.field == Effector::Plane)  // a plane's wall faces `normal` (world), per frame when it turns
      e.normal = track<GfVec3f>(anim, "normal", frames, unit(r.get("normal", "[x, y, z]"), r.at("normal")), unit);
    anim.finish();
    r.finish();
    out.push_back(std::move(e));
  }
  return out;
}

double field_weight(const Effector& e, size_t k, const GfVec3d& here) {
  const double r = pick(e.radius, k);
  const GfVec3d centre(pick(e.centre, k));
  double t = 0;
  switch (e.field) {
    case Effector::Sphere:
      if (r <= 0) return 0;
      t = 1 - (here - centre).GetLength() / r;
      break;
    case Effector::Plane: {  // behind the wall: the full change; in front, fading out over r (0: a hard edge)
      const double d = GfDot(here - centre, GfVec3d(pick(e.normal, k)));
      t = d <= 0 ? 1 : r <= 0 ? 0 : 1 - d / r;
      break;
    }
    case Effector::Noise:  // patches about r big; the noise's middle stretched x2 so whole patches are fully on or off
      if (r <= 0) return 0;
      t = 0.5 + 2 * (noise(e.seed, (here - centre) / r) - 0.5);
      break;
  }
  t = std::clamp(t, 0.0, 1.0);
  return e.smooth ? t * t * (3 - 2 * t) : t;
}

}  // namespace copies
}  // namespace r3d
