#include "copies.h"

#include <pxr/base/gf/quatd.h>
#include <pxr/base/gf/quath.h>
#include <pxr/base/gf/rotation.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/base/gf/vec3h.h>
#include <pxr/base/gf/vec4f.h>
#include <pxr/usd/sdf/changeBlock.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/bboxCache.h>
#include <pxr/usd/usdGeom/camera.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/pointInstancer.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>
#include <pxr/usd/usdGeom/xformCache.h>

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <unordered_map>

#include "inspect.h"
#include "item_track.h"
#include "json_read.h"
#include "stage_items.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace copies {
namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr float kNoMaterialGrey = 0.5f;  // Storm's colour for a mesh with no material and no displayColor (clay_usd.cpp)

// The node's props besides the transform, all sent by the compiler.
const char* const kKeys[] = {"layout", "count", "columns", "spacingX", "spacingY", "spacingZ", "radius", "faceOut",
                             "surface", "amountBy", "density", "minSpacing", "alongSurface", "onTop", "seed", "varyMove",
                             "varyTurn", "varyScale", "varyStart", "seenBy", "seenSize"};

// A number from (seed, copy, channel), 0..1, the same on every run and machine: each copy's chances are its own, so
// changing the count or the layout never reshuffles the others.
uint64_t mix(uint64_t x) {
  x += 0x9E3779B97F4A7C15ull;
  x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
  x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
  return x ^ (x >> 31);
}
double rnd(unsigned seed, int copy, uint64_t channel) {
  const uint64_t h = mix(mix((uint64_t(seed) << 32) | uint32_t(copy)) ^ mix(channel + 0x51ED27ull));
  return double(h >> 11) * (1.0 / 9007199254740992.0);
}
double signed_rnd(unsigned seed, int copy, uint64_t channel) { return 2 * rnd(seed, copy, channel) - 1; }

double number(const JsValue& v, const std::string& where) {
  if (!is_number(v)) fail(where, "is " + v.GetTypeName(), "a number");
  const double d = to_number(v);
  if (!std::isfinite(d)) fail(where, "is not finite", "a finite number");
  return d;
}
double at_least(const JsValue& v, const std::string& where, double lo) {
  const double d = number(v, where);
  if (d < lo) fail(where, std::to_string(d) + " is too small", "a number >= " + std::to_string(lo));
  return d;
}
int whole(const JsValue& v, const std::string& where, double lo, double hi) {
  const double d = number(v, where);
  if (d != std::floor(d) || d < lo || d > hi)
    fail(where, std::to_string(d) + " is out of range",
         "a whole number " + std::to_string(int64_t(lo)) + " .. " + std::to_string(int64_t(hi)));
  return int(d);
}
bool flag(const JsValue& v, const std::string& where) {
  if (!v.IsBool()) fail(where, "is " + v.GetTypeName(), "true or false");
  return v.GetBool();
}
std::string text(const JsValue& v, const std::string& where) {
  if (!v.IsString()) fail(where, "is " + v.GetTypeName(), "a string");
  return v.GetString();
}
std::string choice(const JsValue& v, const std::string& where, const std::vector<std::string>& accepted) {
  const std::string s = text(v, where);
  if (std::find(accepted.begin(), accepted.end(), s) == accepted.end()) fail(where, "\"" + s + "\" is unknown", join(accepted));
  return s;
}

// One prop into p; the same checks for the scene and the live request.
void set_param(Params& p, const std::string& key, const JsValue& v, const std::string& where) {
  if (key == "layout") p.layout = choice(v, where, {"line", "grid", "circle", "surface"});
  else if (key == "count") p.count = whole(v, where, 1, 10000);
  else if (key == "columns") p.columns = whole(v, where, 1, 10000);
  else if (key == "spacingX") p.spacing[0] = number(v, where);
  else if (key == "spacingY") p.spacing[1] = number(v, where);
  else if (key == "spacingZ") p.spacing[2] = number(v, where);
  else if (key == "radius") p.radius = at_least(v, where, 0);
  else if (key == "faceOut") p.faceOut = flag(v, where);
  else if (key == "surface") p.surface = text(v, where);
  else if (key == "amountBy") p.byDensity = choice(v, where, {"count", "density"}) == "density";
  else if (key == "density") p.density = at_least(v, where, 0);
  else if (key == "minSpacing") p.minSpacing = at_least(v, where, 0);
  else if (key == "alongSurface") p.alongSurface = flag(v, where);
  else if (key == "onTop") p.onTop = flag(v, where);
  else if (key == "seed") p.seed = unsigned(whole(v, where, 0, 2147483647));
  else if (key == "varyMove") p.varyMove = at_least(v, where, 0);
  else if (key == "varyTurn") p.varyTurn = at_least(v, where, 0);
  else if (key == "varyScale") {
    p.varyScale = at_least(v, where, 0);
    if (p.varyScale > 1) fail(where, std::to_string(p.varyScale) + " is too big", "0 .. 1");
  } else if (key == "varyStart") p.varyStart = at_least(v, where, 0);
  else if (key == "seenBy") p.seenBy = text(v, where);
  else if (key == "onlySeen") flag(v, where);  // the document's switch; `seenBy` carries it
  else if (key == "seenSize") {
    if (!v.IsArray() || v.GetJsArray().size() != 2) fail(where, "is not a list of 2", "[width, height] in pixels");
    p.seenW = whole(v.GetJsArray()[0], where + "[0]", 0, 65536);  // 0 x 0: no shot size (16:9 then)
    p.seenH = whole(v.GetJsArray()[1], where + "[1]", 0, 65536);
    if (p.seenW == 0 || p.seenH == 0) p.seenW = 16, p.seenH = 9;
  } else {
    std::vector<std::string> known(std::begin(kKeys), std::end(kKeys));
    fail(where, "unknown field", join(known));
  }
}

const char* const kHeldKeys[] = {"x", "y", "z", "rx", "ry", "rz", "s"};

// `frames`: the shot's frame count (a keyed copy's tracks hold one value per frame)
std::vector<Held> read_held(const JsArray& list, const std::string& where, size_t frames) {
  std::vector<Held> out;
  for (size_t i = 0; i < list.size(); ++i) {
    const std::string w = where + "[" + std::to_string(i) + "]";
    if (!list[i].IsObject()) fail(w, "is " + list[i].GetTypeName(), "{\"copy\", \"x\", \"y\", \"z\", \"rx\", \"ry\", \"rz\", \"s\"}");
    Reader r(list[i].GetJsObject(), w);
    Held h;
    h.copy = r.count("copy", 0, 9999);
    const bool keyed = r.has("anim");
    for (int k = 0; k < 7; ++k) {
      h.given[k] = !keyed || r.has(kHeldKeys[k]);  // a plain held copy gives all seven
      if (h.given[k]) h.v[k] = k == 6 ? r.num_min("s", 0, true) : r.num(kHeldKeys[k]);
    }
    if (keyed) {
      Reader anim(r.object("anim"), w + ".anim");
      for (int k = 0; k < 6; ++k) {
        if (!anim.has(kHeldKeys[k])) continue;
        const JsArray& a = anim.list(kHeldKeys[k]);
        if (a.size() != frames)
          fail(anim.at(kHeldKeys[k]), std::to_string(a.size()) + " values", std::to_string(frames) + " values, one per frame");
        for (size_t f = 0; f < a.size(); ++f)
          h.track[k].push_back(number(a[f], anim.at(kHeldKeys[k]) + "[" + std::to_string(f) + "]"));
      }
      anim.finish();
    }
    r.finish();
    out.push_back(std::move(h));
  }
  return out;
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

std::vector<Effector> read_effectors(const JsArray& list, const std::string& where, size_t frames) {
  std::vector<Effector> out;
  for (size_t i = 0; i < list.size(); ++i) {
    const std::string w = where + "[" + std::to_string(i) + "]";
    if (!list[i].IsObject()) fail(w, "is " + list[i].GetTypeName(), "an effector object");
    Reader r(list[i].GetJsObject(), w);
    Effector e;
    e.id = r.str("id");
    const std::string kind = r.one_of("kind", {"scale", "turn", "push", "colour"});
    e.kind = kind == "scale" ? Effector::Scale : kind == "turn" ? Effector::Turn : kind == "push" ? Effector::Push
                                                                                                  : Effector::Colour;
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
    anim.finish();
    r.finish();
    out.push_back(std::move(e));
  }
  return out;
}

GfQuatf quat(const GfRotation& r) { return GfQuatf(r.GetQuat()); }
GfRotation rotation(const GfQuatf& q) { return GfRotation(GfQuatd(q)); }
const GfVec3d kAxes[3] = {GfVec3d::XAxis(), GfVec3d::YAxis(), GfVec3d::ZAxis()};

// The surface's triangles in the copies item's space at the shot's start (a moving surface: its first frame).
void read_surface(const UsdStageRefPtr& stage, State& s) {
  const std::string where = s.id + ".surface";
  const std::string accepted = "the id of a mesh, combine, import or clay item outside this copies item";
  if (s.p.surface.empty()) fail(where, "is empty", accepted);
  const SdfPath sp = item_path(stage, s.p.surface);
  if (sp.IsEmpty()) fail(where, "no item \"" + s.p.surface + "\" in the scene", accepted);
  if (sp.HasPrefix(s.path)) fail(where, "\"" + s.p.surface + "\" is inside this copies item", accepted);
  UsdGeomXformCache xc{UsdTimeCode(s.start)};
  const GfMatrix4d to_copies = xc.GetLocalToWorldTransform(stage->GetPrimAtPath(s.path)).GetInverse();
  Surface out;
  out.id = s.p.surface;
  double area = 0;
  const UsdTimeCode t(s.start);
  for (const UsdPrim& q : UsdPrimRange(stage->GetPrimAtPath(sp), UsdTraverseInstanceProxies())) {
    const UsdGeomMesh m(q);
    if (!m) continue;
    VtVec3fArray pts;
    VtIntArray counts, idx;
    m.GetPointsAttr().Get(&pts, t);
    m.GetFaceVertexCountsAttr().Get(&counts, t);
    m.GetFaceVertexIndicesAttr().Get(&idx, t);
    TfToken orient = UsdGeomTokens->rightHanded;
    m.GetOrientationAttr().Get(&orient);
    const float flip = orient == UsdGeomTokens->leftHanded ? -1.f : 1.f;
    const GfMatrix4d mw = xc.GetLocalToWorldTransform(q), mc = mw * to_copies;
    size_t at = 0;
    for (int n : counts) {
      if (n < 3 || at + n > idx.size()) { at += std::max(n, 0); continue; }
      for (int k = 1; k + 1 < n; ++k) {
        const int i0 = idx[at], i1 = idx[at + k], i2 = idx[at + k + 1];
        if (i0 < 0 || i1 < 0 || i2 < 0 || size_t(std::max({i0, i1, i2})) >= pts.size()) continue;
        const GfVec3d w0 = mw.Transform(GfVec3d(pts[i0])), w1 = mw.Transform(GfVec3d(pts[i1])),
                      w2 = mw.Transform(GfVec3d(pts[i2]));
        const GfVec3d wn = GfCross(w1 - w0, w2 - w0) * double(flip);
        const double a = 0.5 * wn.GetLength();
        if (a <= 1e-14) continue;
        if (s.p.onTop && wn[1] < 0.5 * wn.GetLength()) continue;  // a side or underside: nothing rests there
        const GfVec3f c0(mc.Transform(GfVec3d(pts[i0]))), c1(mc.Transform(GfVec3d(pts[i1]))),
                      c2(mc.Transform(GfVec3d(pts[i2])));
        GfVec3f nrm = GfCross(c1 - c0, c2 - c0) * flip;
        if (nrm.Normalize() < 1e-20f) continue;
        out.a.push_back(c0);
        out.b.push_back(c1);
        out.c.push_back(c2);
        out.normal.push_back(nrm);
        area += a;
        out.cumulative.push_back(area);
      }
      at += n;
    }
  }
  if (out.empty())
    fail(where, "\"" + s.p.surface + "\" has no mesh to scatter on" + std::string(s.p.onTop ? " facing up (onTop: off scatters on every side)" : " (an empty clay or shape has none)"), accepted);
  s.surf = std::move(out);
}

// Places on the surface, area-weighted, each at least minSpacing from the ones before it (darts from the seed: the
// first copies stay where they are when the count grows). When the surface is full at minSpacing, the rest come closer
// (the gap shrinks by steps, down to touching), so Count is always met.
void scatter(const State& s, std::vector<GfVec3f>* pos, std::vector<GfVec3f>* nrm) {
  const Params& p = s.p;
  const Surface& sf = s.surf;
  const double total = sf.cumulative.back();
  int want = p.byDensity ? int(std::lround(total * p.density)) : p.count;
  want = std::clamp(want, 0, 10000);
  float gap = float(p.minSpacing);
  std::unordered_map<int64_t, std::vector<int>> grid;  // minSpacing cells -> placed copies
  const auto cell = [&](const GfVec3f& v, int dx, int dy, int dz) {
    const int64_t x = int64_t(std::floor(v[0] / gap)) + dx, y = int64_t(std::floor(v[1] / gap)) + dy,
                  z = int64_t(std::floor(v[2] / gap)) + dz;
    return (x * 73856093) ^ (y * 19349663) ^ (z * 83492791);
  };
  constexpr int kTries = 30;
  int misses = 0;
  for (int i = 0; int(pos->size()) < want; ++i) {
    if (misses >= 64) {  // full at this gap: closer for the rest, the placed ones re-filed in the new cells
      if (gap <= 0) break;
      gap = gap > 1e-4f ? gap * 0.7f : 0.f;
      grid.clear();
      if (gap > 0)
        for (int j = 0; j < int(pos->size()); ++j) grid[cell((*pos)[j], 0, 0, 0)].push_back(j);
      misses = 0;
    }
    bool placed = false;
    for (int t = 0; t < kTries && !placed; ++t) {
      const uint64_t ch = 1000 + uint64_t(t) * 3;
      const double r = rnd(p.seed, i, ch) * total;
      const size_t tri = std::min(size_t(std::upper_bound(sf.cumulative.begin(), sf.cumulative.end(), r) -
                                         sf.cumulative.begin()), sf.cumulative.size() - 1);
      const double r1 = std::sqrt(rnd(p.seed, i, ch + 1)), r2 = rnd(p.seed, i, ch + 2);
      const GfVec3f v = sf.a[tri] * float(1 - r1) + sf.b[tri] * float(r1 * (1 - r2)) + sf.c[tri] * float(r1 * r2);
      bool clear = true;
      if (gap > 0)
        for (int dx = -1; dx <= 1 && clear; ++dx)
          for (int dy = -1; dy <= 1 && clear; ++dy)
            for (int dz = -1; dz <= 1 && clear; ++dz) {
              auto it = grid.find(cell(v, dx, dy, dz));
              if (it == grid.end()) continue;
              for (int j : it->second)
                if (((*pos)[j] - v).GetLengthSq() < gap * gap) { clear = false; break; }
            }
      if (!clear) continue;
      if (gap > 0) grid[cell(v, 0, 0, 0)].push_back(int(pos->size()));
      pos->push_back(v);
      nrm->push_back(sf.normal[tri]);
      placed = true;
    }
    misses = placed ? 0 : misses + 1;
  }
}

// A held (or keyed) copy at frame index k: what it gives replaces the layout's (turns: rotate X, then Y, then Z; a turn
// given in part keeps the rest of the layout's).
void place(Copy& c, const Held& h, size_t k) {
  const auto has = [&](int i) { return h.given[i] || (i < 6 && !h.track[i].empty()); };
  const auto val = [&](int i) {
    return i < 6 && !h.track[i].empty() ? h.track[i][std::min(k, h.track[i].size() - 1)] : h.v[i];
  };
  for (int i = 0; i < 3; ++i)
    if (has(i)) c.pos[i] = float(val(i));
  if (has(3) || has(4) || has(5)) {
    GfVec3d e(0.0);
    if (!(has(3) && has(4) && has(5))) e = rotation(c.rot).Decompose(GfVec3d::XAxis(), GfVec3d::YAxis(), GfVec3d::ZAxis());
    for (int i = 0; i < 3; ++i)
      if (has(3 + i)) e[i] = val(3 + i);
    c.rot = quat(GfRotation(GfVec3d::XAxis(), e[0]) * GfRotation(GfVec3d::YAxis(), e[1]) * GfRotation(GfVec3d::ZAxis(), e[2]));
  }
  if (h.given[6]) c.scale = float(h.v[6]);
}

// The copies before effectors: the layout, the seed's variations, then the held ones in their own places.
std::vector<Copy> lay_out(const State& s) {
  const Params& p = s.p;
  const int sources = std::max<int>(1, int(s.sources.size()));
  std::vector<Copy> out;
  std::vector<GfVec3f> normals;
  const GfRotation none(GfVec3d::YAxis(), 0);
  std::vector<GfRotation> base;
  if (p.layout == "surface") {
    std::vector<GfVec3f> pos;
    scatter(s, &pos, &normals);
    for (size_t i = 0; i < pos.size(); ++i) {
      Copy c;
      c.pos = pos[i];
      out.push_back(c);
      base.push_back(p.alongSurface ? GfRotation(GfVec3d::YAxis(), GfVec3d(normals[i])) : none);
    }
  } else {
    out.resize(size_t(p.count));
    for (int i = 0; i < p.count; ++i) {
      Copy& c = out[i];
      GfRotation r = none;
      if (p.layout == "line") {
        c.pos = GfVec3f(float(i * p.spacing[0]), float(i * p.spacing[1]), float(i * p.spacing[2]));
      } else if (p.layout == "grid") {
        const int col = i % p.columns, row = i / p.columns;
        c.pos = GfVec3f(float(col * p.spacing[0]), 0.f, float(row * p.spacing[2]));
      } else {  // circle, round Y; facing out turns the source's +Z outward
        const double a = 2 * kPi * i / p.count;
        c.pos = GfVec3f(float(p.radius * std::sin(a)), 0.f, float(p.radius * std::cos(a)));
        if (p.faceOut) r = GfRotation(GfVec3d::YAxis(), a * 180 / kPi);
      }
      base.push_back(r);
    }
  }
  const bool on_surface = p.layout == "surface";
  for (int i = 0; i < int(out.size()); ++i) {
    Copy& c = out[i];
    GfRotation r = base[i];
    if (p.varyMove > 0) {
      GfVec3f d(float(signed_rnd(p.seed, i, 1)), float(signed_rnd(p.seed, i, 2)), float(signed_rnd(p.seed, i, 3)));
      d *= float(p.varyMove);
      if (on_surface) d -= normals[i] * GfDot(d, normals[i]);  // slides along the surface, never into it
      c.pos += d;
    }
    if (p.varyTurn > 0) r = GfRotation(GfVec3d::YAxis(), signed_rnd(p.seed, i, 4) * p.varyTurn) * r;  // round its own up
    if (p.varyScale > 0) c.scale = float(std::max(0.01, 1 + signed_rnd(p.seed, i, 5) * p.varyScale));
    c.rot = quat(r);
    c.proto = sources == 1 ? 0 : std::min(sources - 1, int(rnd(p.seed, i, 6) * sources));
  }
  for (const Held& h : s.held)
    if (h.copy < int(out.size())) place(out[h.copy], h, 0);  // a held copy beyond the count doesn't exist
  return out;
}

// Keyed copies at frame index k, over the layout (the effectors come after).
void keyed_at(const std::vector<Held>& held, size_t k, std::vector<Copy>& copies) {
  for (const Held& h : held)
    if (h.keyed() && h.copy < int(copies.size())) place(copies[size_t(h.copy)], h, k);
}

bool any_keyed(const State& s) {
  return std::any_of(s.held.begin(), s.held.end(), [](const Held& h) { return h.keyed(); });
}

// The effectors at frame index k: `world` is the copies item's place then. `tints`: each copy's colour change as
// (rgb already times its share, the share 0..1): each colour effector lays its colour over what is there by
// amount x falloff, so the copy's colour = what it had x (1 - share) + rgb (Storm's grey, Cycles' material colour).
void apply(const std::vector<Effector>& effectors, size_t k, const GfMatrix4d& world, std::vector<Copy>& copies,
           std::vector<GfVec4f>* tints) {
  if (effectors.empty()) return;
  const GfMatrix4d to_local = world.GetInverse();
  for (size_t i = 0; i < copies.size(); ++i) {
    Copy& c = copies[i];
    for (const Effector& e : effectors) {
      const double r = pick(e.radius, k), amount = pick(e.amount, k);
      if (r <= 0) continue;
      const GfVec3d centre(pick(e.centre, k)), here = world.Transform(GfVec3d(c.pos));
      const double t = std::clamp(1 - (here - centre).GetLength() / r, 0.0, 1.0);
      const double w = e.smooth ? t * t * (3 - 2 * t) : t;
      if (w <= 0) continue;
      switch (e.kind) {
        case Effector::Scale: c.scale *= float(std::max(0.0, 1 + amount * w)); break;
        case Effector::Turn: c.rot = quat(GfRotation(kAxes[e.axis], amount * w) * rotation(c.rot)); break;
        case Effector::Push: {
          GfVec3d away = here - centre;
          if (away.Normalize() < 1e-12) away = GfVec3d::YAxis();
          c.pos += GfVec3f(to_local.TransformDir(away * (amount * w)));
          break;
        }
        case Effector::Colour:
          if (tints) {
            const float m = float(std::clamp(amount * w, 0.0, 1.0));
            const GfVec3f c3 = pick(e.colour, k);
            GfVec4f& t = (*tints)[i];
            t = GfVec4f(t[0] * (1 - m) + c3[0] * m, t[1] * (1 - m) + c3[1] * m, t[2] * (1 - m) + c3[2] * m,
                        1 - (1 - t[3]) * (1 - m));
          }
          break;
      }
    }
  }
}

struct Arrays {
  VtVec3fArray positions, scales, colours;
  VtVec4fArray tints;  // rostrumTint: the change's own colour and its share (Cycles' material mixes it in)
  VtQuathArray orientations;
};

Arrays arrays(const std::vector<Copy>& copies, const std::vector<GfVec4f>* tints) {
  Arrays a;
  const size_t n = copies.size();
  a.positions.resize(n);
  a.scales.resize(n);
  a.orientations.resize(n);
  for (size_t i = 0; i < n; ++i) {
    a.positions[i] = copies[i].pos;
    a.scales[i] = GfVec3f(copies[i].scale);
    a.orientations[i] = GfQuath(copies[i].rot);
  }
  if (tints) {
    a.colours.resize(n);
    a.tints.resize(n);
    for (size_t i = 0; i < n; ++i) {
      const GfVec4f& t = (*tints)[i];
      const float share = t[3], keep = (1 - share) * kNoMaterialGrey;
      a.colours[i] = GfVec3f(keep + t[0], keep + t[1], keep + t[2]);
      a.tints[i] = share > 1e-6f ? GfVec4f(t[0] / share, t[1] / share, t[2] / share, share) : GfVec4f(0);
    }
  }
  return a;
}

bool has_kind(const State& s, Effector::Kind kind) {
  for (const Effector& e : s.effectors)
    if (e.kind == kind) return true;
  return false;
}

// The copies item's world place at each frame of the shot (one entry when it never moves).
std::vector<GfMatrix4d> places(const UsdStageRefPtr& stage, const State& s, bool every_frame) {
  const UsdPrim prim = stage->GetPrimAtPath(s.path);
  UsdGeomXformCache xc{UsdTimeCode(s.start)};
  std::vector<GfMatrix4d> out{xc.GetLocalToWorldTransform(prim)};
  for (int f = s.start + 1; every_frame && f <= s.end; ++f) {
    xc.SetTime(UsdTimeCode(f));
    out.push_back(xc.GetLocalToWorldTransform(prim));
  }
  return out;
}

bool moves(const UsdStageRefPtr& stage, const State& s) {
  if (any_keyed(s)) return true;
  for (const Effector& e : s.effectors)
    if (e.moves()) return true;
  if (s.effectors.empty()) return false;
  // the copies item (or what holds it) moving moves the copies through the effectors' fields
  for (UsdPrim p = stage->GetPrimAtPath(s.path); p && !p.IsPseudoRoot(); p = p.GetParent())
    if (UsdGeomXformable(p) && UsdGeomXformable(p).TransformMightBeTimeVarying()) return true;
  return false;
}

// Writes the copies onto the instancer: plain values, or (an effector or a keyed copy moving) per-frame samples of what
// they change.
void write(const UsdStageRefPtr& stage, State& s) {
  const UsdGeomPointInstancer pi(stage->GetPrimAtPath(s.path));
  const size_t n = s.laid.size();
  VtIntArray protos(n);
  VtInt64Array ids(n);
  for (size_t i = 0; i < n; ++i) {
    protos[i] = s.laid[i].proto;
    ids[i] = int64_t(i);
  }
  const bool coloured = has_kind(s, Effector::Colour);
  s.animated = moves(stage, s);
  const std::vector<GfMatrix4d> world = places(stage, s, s.animated);
  UsdAttribute pos = pi.CreatePositionsAttr(), rot = pi.CreateOrientationsAttr(), scl = pi.CreateScalesAttr();
  UsdAttribute col, tint;
  static const TfToken kTint("rostrumTint");  // read by our Cycles patch (libs/cycles-rostrum.patch, instancer.cpp)
  if (coloured) {
    col = UsdGeomPrimvarsAPI(pi).CreatePrimvar(UsdGeomTokens->primvarsDisplayColor, SdfValueTypeNames->Color3fArray,
                                              UsdGeomTokens->vertex).GetAttr();  // vertex on an instancer = per copy
    tint = UsdGeomPrimvarsAPI(pi).CreatePrimvar(kTint, SdfValueTypeNames->Color4fArray, UsdGeomTokens->vertex).GetAttr();
  } else {
    for (const char* name : {"primvars:displayColor", "primvars:rostrumTint"})
      if (UsdAttribute old = pi.GetPrim().GetAttribute(TfToken(name))) old.Clear();
  }
  for (UsdAttribute a : {pos, rot, scl}) a.Clear();
  if (col) col.Clear();
  if (tint) tint.Clear();
  pi.CreateProtoIndicesAttr().Set(protos);
  pi.CreateIdsAttr().Set(ids);

  if (s.sim.on()) {  // a stored fall: each simulated copy's place per frame; its size and the rest as laid out
    const Arrays still = arrays(s.laid, nullptr);
    scl.Set(still.scales);
    s.animated = true;
    const int m = std::min<int>(int(n), s.sim.rows);
    for (int f = s.start; f <= s.end; ++f) {
      VtVec3fArray p = still.positions;
      VtQuathArray q = still.orientations;
      for (int c = 0; c < m; ++c) {
        GfVec3f at;
        GfQuatf turn;
        s.sim.pose(c, f, s.start, &at, &turn);
        p[size_t(c)] = at;
        q[size_t(c)] = GfQuath(turn);
      }
      pos.Set(p, UsdTimeCode(f));
      rot.Set(q, UsdTimeCode(f));
    }
    return;
  }
  const std::vector<GfVec4f> untinted(n, GfVec4f(0));
  const auto at = [&](size_t k) {
    std::vector<Copy> c = s.laid;
    std::vector<GfVec4f> tints = untinted;
    keyed_at(s.held, k, c);
    apply(s.effectors, k, world[std::min(k, world.size() - 1)], c, coloured ? &tints : nullptr);
    return arrays(c, coloured ? &tints : nullptr);
  };
  if (!s.animated) {
    const Arrays a = at(0);
    pos.Set(a.positions);
    rot.Set(a.orientations);
    scl.Set(a.scales);
    if (col) col.Set(a.colours);
    if (tint) tint.Set(a.tints);
    return;
  }
  // only what an effector or a keyed copy changes gets samples; the rest is the layout's plain value
  const bool keyed = any_keyed(s);
  const bool by_pos = keyed || has_kind(s, Effector::Push), by_rot = keyed || has_kind(s, Effector::Turn),
             by_scl = has_kind(s, Effector::Scale);
  const Arrays still = arrays(s.laid, nullptr);
  if (!by_pos) pos.Set(still.positions);
  if (!by_rot) rot.Set(still.orientations);
  if (!by_scl) scl.Set(still.scales);
  for (int f = s.start; f <= s.end; ++f) {
    const Arrays a = at(size_t(f - s.start));
    const UsdTimeCode t(f);
    if (by_pos) pos.Set(a.positions, t);
    if (by_rot) rot.Set(a.orientations, t);
    if (by_scl) scl.Set(a.scales, t);
    if (col) col.Set(a.colours, t);
    if (tint) tint.Set(a.tints, t);
  }
}

}  // namespace

namespace {
SimTrack read_sim(const JsObject& o, const std::string& where) {
  Reader r(o, where);
  SimTrack t;
  t.file = r.str("file");
  t.row = r.count("row", 0, 1 << 30);
  t.rows = r.count("rows", 0, 1 << 30);
  t.of = r.count("of", 1, 1 << 30);
  t.start = int(r.num("start"));
  t.end = int(r.num("end"));
  t.step = r.count("step", 1, 3);
  t.smooth = r.count("smooth", 1, 100);
  r.finish();
  if (t.end < t.start || t.row + t.rows > t.of) fail(where, "rows or frames don't fit", "row + rows <= of, start <= end");
  const size_t want = size_t(t.end - t.start + 1) * size_t(t.of) * 7;
  std::ifstream f(std::filesystem::u8path(t.file), std::ios::binary | std::ios::ate);
  if (!f) fail(where + ".file", "no file " + t.file, "the stored simulation's bodies.bin (simulate again)");
  const auto bytes = size_t(f.tellg());
  if (bytes != want * sizeof(float))
    fail(where + ".file", t.file + " holds " + std::to_string(bytes) + " bytes, not " + std::to_string(want * sizeof(float)),
         "the stored simulation's bodies.bin (simulate again)");
  t.data.resize(want);
  f.seekg(0);
  f.read(reinterpret_cast<char*>(t.data.data()), std::streamsize(bytes));
  return t;
}
}  // namespace

bool Held::keyed() const {
  return std::any_of(std::begin(track), std::end(track), [](const std::vector<double>& t) { return !t.empty(); });
}

void SimTrack::pose(int c, int f, int shot_start, GfVec3f* pos, GfQuatf* rot) const {
  const int last = end - start;
  const int held = shot_start + (f - shot_start) / step * step;  // On 2s / On 3s, from the shot's start
  const int i = std::clamp(held - start, 0, last);
  const int a = i / smooth * smooth, b = std::min(a + smooth, last);  // Simplify: every nth pose, blended between
  const auto at = [&](int k, GfVec3f* p, GfQuatf* q) {
    const float* v = &data[(size_t(k) * size_t(of) + size_t(row + c)) * 7];
    *p = GfVec3f(v[0], v[1], v[2]);
    *q = GfQuatf(v[6], v[3], v[4], v[5]);
  };
  GfVec3f pa, pb;
  GfQuatf qa, qb;
  at(a, &pa, &qa);
  if (b == a || i == a) { *pos = pa; *rot = qa; return; }
  at(b, &pb, &qb);
  const float u = float(i - a) / float(b - a);
  *pos = pa + (pb - pa) * u;
  *rot = GfSlerp(double(u), qa, qb).GetNormalized();
}

void build(Item& it, const JsArray& children, const JsArray& held, const JsArray& effectors, const JsObject* sim,
           const SdfPath& path) {
  ItemsContext& ctx = it.ctx;
  const UsdGeomPointInstancer pi = UsdGeomPointInstancer::Define(ctx.stage, path);
  author_transform(it, pi.GetPrim());
  State s;
  s.id = it.id;
  s.path = path;
  s.start = ctx.start;
  s.end = ctx.end;
  for (const char* key : kKeys) set_param(s.p, key, it.props.get(key, "a value"), it.props.at(key));
  if (it.props.has("onlySeen")) set_param(s.p, "onlySeen", it.props.get("onlySeen", "true or false"), it.props.at("onlySeen"));
  s.held = read_held(held, it.id + ".held", size_t(ctx.end - ctx.start + 1));
  s.effectors = read_effectors(effectors, it.id + ".effectors", size_t(ctx.end - ctx.start + 1));
  if (sim) s.sim = read_sim(*sim, it.id + ".sim");
  const std::string accepted = "one or more mesh, combine, import, group or clay items (the copies' sources)";
  if (children.empty()) fail(it.id + ".children", "no source", accepted);
  SdfPathVector protos;
  for (size_t i = 0; i < children.size(); ++i) {
    const std::string where = it.id + ".children[" + std::to_string(i) + "]";
    if (!children[i].IsObject()) fail(where, "is " + children[i].GetTypeName(), accepted);
    const JsObject& o = children[i].GetJsObject();
    const auto type = o.find("type"), id = o.find("id");
    const std::string t = type != o.end() && type->second.IsString() ? type->second.GetString() : "";
    if (t == "light" || t == "camera" || t == "copies")
      fail(where + ".type", "a " + t + " can't be a copies item's source", accepted);
    if (id != o.end() && id->second.IsString()) {
      s.sources.push_back(id->second.GetString());
      protos.push_back(path.AppendChild(TfToken(id->second.GetString())));
    }
  }
  build_items(ctx, children, path, it.id + ".children");  // checks every child fully (ids, types)
  pi.CreatePrototypesRel().SetTargets(protos);  // under the instancer and targeted: drawn only as copies
  ctx.copies.push_back(std::move(s));
}

void lay_out_all(const UsdStageRefPtr& stage, std::vector<State>& all, const SdfPathVector& clays) {
  for (State& s : all) {
    if (!s.p.seenBy.empty()) {
      const UsdPrim cam = stage->GetPrimAtPath(item_path(stage, s.p.seenBy));
      if (!cam || !cam.IsA<UsdGeomCamera>())
        fail(s.id + ".seenBy", "no camera \"" + s.p.seenBy + "\" in the scene", "\"\" or a camera item's id");
    }
    const UsdPrim self = stage->GetPrimAtPath(s.path);
    UsdGeomBBoxCache bb(UsdTimeCode(s.start), {UsdGeomTokens->default_, UsdGeomTokens->render});
    s.bounds.clear();
    for (const std::string& src : s.sources)
      s.bounds.push_back(bb.ComputeRelativeBound(self.GetChild(TfToken(src)), self).ComputeAlignedRange());
    s.late = s.p.layout == "surface" &&
             std::find(clays.begin(), clays.end(), item_path(stage, s.p.surface)) != clays.end();
    if (s.late) continue;  // its clay's blocks are written on the held stage by the clay store, after this build
    if (s.p.layout == "surface") read_surface(stage, s);
    s.laid = lay_out(s);
    write(stage, s);
  }
}

void lay_out_late(const UsdStageRefPtr& stage, State& s) {
  read_surface(stage, s);
  s.laid = lay_out(s);
  write(stage, s);
  s.late = false;
}

double relay(const UsdStageRefPtr& stage, State& s, const JsObject& props, const JsValue* held) {
  const auto t0 = std::chrono::steady_clock::now();
  Params p = s.p;  // checked whole before anything changes
  for (const auto& [key, value] : props) set_param(p, key, value, "copies.props." + key);
  std::vector<Held> h = s.held;
  if (held) {
    if (!held->IsArray()) fail("copies.held", "is " + held->GetTypeName(), "a list of held copies");
    h = read_held(held->GetJsArray(), "copies.held", size_t(s.end - s.start + 1));
  }
  const Surface had = s.surf;
  const Params was = s.p;
  s.p = p;
  if (p.layout == "surface" && (s.surf.empty() || s.surf.id != p.surface || was.onTop != p.onTop)) {
    try {
      read_surface(stage, s);
    } catch (...) {
      s.p = was;
      s.surf = had;
      throw;
    }
  }
  s.held = std::move(h);
  s.laid = lay_out(s);
  {
    const SdfChangeBlock block;  // one change for Hydra
    write(stage, s);
  }
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

std::vector<Copy> at_frame(const UsdStageRefPtr& stage, const State& s, int frame, GfMatrix4d* world) {
  UsdGeomXformCache xc{UsdTimeCode(frame)};
  *world = xc.GetLocalToWorldTransform(stage->GetPrimAtPath(s.path));
  std::vector<Copy> c = s.laid;
  const size_t k = size_t(std::clamp(frame - s.start, 0, s.end - s.start));
  keyed_at(s.held, k, c);
  apply(s.effectors, k, *world, c, nullptr);
  return c;
}

std::vector<Copy> drawn_at(const UsdStageRefPtr& stage, const State& s, int frame, GfMatrix4d* world) {
  if (!s.sim.on()) return at_frame(stage, s, frame, world);
  UsdGeomXformCache xc{UsdTimeCode(frame)};
  *world = xc.GetLocalToWorldTransform(stage->GetPrimAtPath(s.path));
  std::vector<Copy> c = s.laid;  // as `write` draws a stored fall: no keys, no effectors on it
  const int m = std::min<int>(int(c.size()), s.sim.rows);
  for (int i = 0; i < m; ++i) s.sim.pose(i, frame, s.start, &c[size_t(i)].pos, &c[size_t(i)].rot);
  return c;
}

std::vector<GfVec3d> seen_points(const UsdStageRefPtr& stage, const State& s, int frame) {
  GfMatrix4d world;
  const std::vector<Copy> copies = drawn_at(stage, s, frame, &world);
  std::vector<GfVec3d> out;
  out.reserve(copies.size() * 2);
  for (const Copy& c : copies) {
    out.push_back(world.Transform(GfVec3d(c.pos)));
    const GfRange3d& b = s.bounds[std::min<size_t>(c.proto, s.bounds.size() - 1)];
    const GfVec3f mid = b.IsEmpty() ? GfVec3f(0.f) : GfVec3f(b.GetMidpoint());
    out.push_back(world.Transform(GfVec3d(c.pos + c.rot.Transform(mid * c.scale))));
  }
  return out;
}

GfRange3d world_box(const UsdStageRefPtr& stage, const State& s, int frame) {
  GfMatrix4d world;
  const std::vector<Copy> copies = drawn_at(stage, s, frame, &world);
  GfRange3d out;
  for (const Copy& c : copies) {
    const GfRange3d& b = s.bounds.empty() ? GfRange3d() : s.bounds[std::min<size_t>(c.proto, s.bounds.size() - 1)];
    if (b.IsEmpty()) {
      out.UnionWith(world.Transform(GfVec3d(c.pos)));
      continue;
    }
    for (int i = 0; i < 8; ++i)
      out.UnionWith(world.Transform(GfVec3d(c.pos + c.rot.Transform(GfVec3f(b.GetCorner(i)) * c.scale))));
  }
  return out;
}

void write_shown(const UsdStageRefPtr& stage, const State& s) {
  const UsdGeomPointInstancer pi(stage->GetPrimAtPath(s.path));
  VtInt64Array hidden;
  for (size_t i = 0; i < s.shown.size(); ++i)
    if (!s.shown[i]) hidden.push_back(int64_t(i));
  if (hidden.empty()) {
    if (UsdAttribute a = pi.GetInvisibleIdsAttr()) a.Clear();
    return;
  }
  pi.CreateInvisibleIdsAttr().Set(hidden);
}

int copy_at(const UsdStageRefPtr& stage, const State& s, int frame, const GfVec3d& point, int hint, int proto) {
  GfMatrix4d world;
  const std::vector<Copy> copies = drawn_at(stage, s, frame, &world);
  const GfVec3f local(world.GetInverse().Transform(point));
  // how far inside copy i's bounds the point is (< 1 inside, as a share of their half size); -1 = not a candidate
  const auto score = [&](int i) -> double {
    if (i < 0 || i >= int(copies.size())) return -1;
    if (i < int(s.shown.size()) && !s.shown[i]) return -1;
    const Copy& c = copies[i];
    if (proto >= 0 && c.proto != proto) return -1;
    if (c.scale <= 1e-6f) return -1;
    const GfVec3f q = c.rot.GetInverse().Transform(local - c.pos) / c.scale;
    const GfRange3d& b = s.bounds[std::min<size_t>(c.proto, s.bounds.size() - 1)];
    if (b.IsEmpty()) return double(q.GetLength());  // no bounds (a clay): nearest copy
    const GfVec3d half = b.GetSize() * 0.5 + GfVec3d(1e-3), d = GfVec3d(q) - b.GetMidpoint();
    return std::max({std::abs(d[0]) / half[0], std::abs(d[1]) / half[1], std::abs(d[2]) / half[2]});
  };
  if (const double h = score(hint); h >= 0 && h <= 1.02) return hint;
  int best = -1;
  double best_score = 1e300;
  for (int i = 0; i < int(copies.size()); ++i) {
    const double v = score(i);
    if (v >= 0 && v < best_score) best = i, best_score = v;
  }
  return best;
}

int start_delay(const Params& p, int copy, double fps) {
  return p.varyStart > 0 ? int(std::lround(rnd(p.seed, copy, 7) * p.varyStart * fps)) : 0;
}

}  // namespace copies
}  // namespace r3d
