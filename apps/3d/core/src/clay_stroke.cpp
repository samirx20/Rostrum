// Clay: finding a stroke's dabs (clay_stroke.h). Moved from proofs/3d-clay (session.h Session::run, resample).
#include "clay_stroke.h"

#include <cmath>
#include <cstring>

namespace r3d::clay {

namespace {
const char* kOpNames[] = {"add", "carve", "smooth", "pull", "flatten", "crease", "mask"};
constexpr int kOps = int(sizeof(kOpNames) / sizeof(kOpNames[0]));
constexpr int kPullSplit = 4;  // a Pull dab moving the clay further than one dab can is cut into at most this many

// A dab of `b` at `a` (normal `n`, Pull vector / Crease direction `dir`) with the pen's scales. The one place a stamp
// is made, live and from stored rows alike, so both give the same numbers bit for bit.
Step stamp(const Brush& br, V3 a, V3 n, V3 dir, float radiusScale, float strengthScale) {
  Step s;
  s.kind = Kind::Stamp;
  s.op = br.op;
  s.a = a;
  s.n = n;
  s.b = dir;
  s.radiusScale = radiusScale;
  s.strengthScale = strengthScale;
  s.radius = br.radius * radiusScale;
  s.strength = br.strength * strengthScale;
  s.mirror = br.mirror;
  s.stroke = 1;
  s.accumulate = br.accumulate;
  s.falloff = br.falloff;
  s.invert = br.invert;
  return s;
}
}  // namespace

bool op_from_name(const char* name, Op& op) {
  for (int i = 0; i < kOps; ++i)
    if (std::strcmp(name, kOpNames[i]) == 0) {
      op = Op(i);
      return true;
    }
  return false;
}

const char* op_name(Op op) { return kOpNames[int(op)]; }

void Resampler::push(V3 p, std::vector<V3>& out) {
  // the proof cut each segment a..b into k parts and listed a + (b - a) j / k for j < k, then the last point; listing
  // the parts before b and then b itself gives the same list one point at a time
  if (have_) {
    const V3 seg = sub(p, last_);
    const int k = std::max(1, int(len(seg) / spacing_));
    for (int j = 1; j < k; ++j) out.push_back(add(last_, mul(seg, float(j) / k)));
  }
  out.push_back(p);
  last_ = p;
  have_ = true;
}

void Resampler::push(V3 p, float pressure, std::vector<V3>& out, std::vector<float>& pressures) {
  const size_t first = out.size();
  const bool had = have_;
  const V3 from = last_;
  const float p0 = lastPressure_;
  push(p, out);
  // the samples before the point lie on from..p at the same share as their pressure on p0..pressure
  const V3 seg = sub(p, from);
  const float ll = dot(seg, seg);
  for (size_t i = first; i < out.size(); ++i) {
    float t = 1.0f;
    if (had && i + 1 < out.size() && ll > 0) t = dot(sub(out[i], from), seg) / ll;
    pressures.push_back(p0 + (pressure - p0) * t);
  }
  lastPressure_ = pressure;
}

bool StrokeDabs::add(V3 o, V3 d, float maxDist, float pressure) {
  V3 on, nrm;
  hit = vol_.cast(o, d, maxDist, on, nrm);
  if (!hit) return false;
  // Front faces only: a point that faces away from the ray is the far side of a thin part (the snap went through)
  if (brush_.frontOnly && dot(nrm, d) > 0) {
    hit = false;
    return false;
  }
  point = on;
  normal = nrm;
  const float rs = pressure_radius_scale(pressure), ss = pressure_strength_scale(pressure);
  // Pull: the drag since the last dab, along the surface (all of it at strength 0.5 and above: the clay follows the
  // pointer); Crease: the line's direction
  const V3 along = havePrev_ ? sub(on, prev_) : V3{0, 0, 0};
  const V3 tang = sub(along, mul(nrm, dot(along, nrm)));
  prev_ = on;
  havePrev_ = true;
  if ((brush_.op == Op::Pull || brush_.op == Op::Crease) && len(tang) == 0) return false;  // no direction yet
  if (brush_.op == Op::Pull) {
    // one dab moves the clay at most 2 grains (the band it works on is 4 wide): a longer drag is cut into dabs at
    // the same spot that each move a part of it, so a fast drag still carries the clay along
    const V3 pull = mul(tang, std::min(1.0f, 2.0f * brush_.strength * ss));
    const int k = std::min(kPullSplit, std::max(1, int(std::ceil(len(pull) / (2.0f * vol_.voxel())))));
    const V3 part = mul(pull, 1.0f / float(k));
    for (int i = 0; i < k; ++i) {
      const Step s = stamp(brush_, on, nrm, part, rs, ss);
      vol_.dab(s);
      dabs_.push_back(s);
    }
    return true;
  }
  const Step s = stamp(brush_, on, nrm, brush_.op == Op::Crease ? unit(tang) : V3{0, 0, 0}, rs, ss);
  vol_.dab(s);
  dabs_.push_back(s);
  return true;
}

std::vector<Step> stroke_along(Volume& v, const Brush& b, const std::vector<V3>& points, V3 dir) {
  dir = unit(dir);
  const float back = std::max(0.08f, 4.0f * b.radius);
  std::vector<V3> samples;
  Resampler rs(b.radius * b.spacing);
  for (const V3& p : points) rs.push(p, samples);
  StrokeDabs sd(v, b);
  v.begin_stroke();
  for (const V3& p : samples) sd.add(sub(p, mul(dir, back)), dir, 2 * back);
  v.end_stroke(sd.dabs());
  return sd.dabs();
}

std::vector<Step> dabs_from_rows(const std::vector<DabRow>& rows, const Brush& b) {
  std::vector<Step> out;
  out.reserve(rows.size());
  for (const DabRow& r : rows)
    out.push_back(stamp(b, {r[0], r[1], r[2]}, {r[3], r[4], r[5]}, {r[6], r[7], r[8]}, r[9], r[10]));
  return out;
}

DabRow row_of(const Step& s) {
  return {s.a.x, s.a.y, s.a.z, s.n.x, s.n.y, s.n.z, s.b.x, s.b.y, s.b.z, s.radiusScale, s.strengthScale};
}

}  // namespace r3d::clay
