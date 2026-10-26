// Clay: finding a stroke's dabs (clay_stroke.h). Moved from proofs/3d-clay (session.h Session::run, resample).
#include "clay_stroke.h"

#include <cstring>

namespace r3d::clay {

namespace {
const char* kOpNames[] = {"add", "carve", "smooth", "pull", "flatten", "crease"};
}

bool op_from_name(const char* name, Op& op) {
  for (int i = 0; i < 6; ++i)
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

bool StrokeDabs::add(V3 o, V3 d, float maxDist) {
  V3 on, nrm;
  hit = vol_.cast(o, d, maxDist, on, nrm);
  if (!hit) return false;
  point = on;
  normal = nrm;
  Step s;
  s.kind = Kind::Stamp;
  s.op = brush_.op;
  s.a = on;
  s.n = nrm;
  s.radius = brush_.radius;
  s.strength = brush_.strength;
  s.mirror = brush_.mirror;
  s.stroke = 1;
  s.accumulate = brush_.accumulate;
  // Pull: the pull vector (along the drag, in the surface); Crease: the line's direction
  const V3 along = havePrev_ ? sub(on, prev_) : V3{0, 0, 0};
  const V3 tang = sub(along, mul(nrm, dot(along, nrm)));
  if (brush_.op == Op::Pull) s.b = mul(unit(tang), brush_.radius * brush_.strength * 0.5f);
  if (brush_.op == Op::Crease) s.b = unit(tang);
  prev_ = on;
  havePrev_ = true;
  if ((brush_.op == Op::Pull || brush_.op == Op::Crease) && len(tang) == 0) return false;  // no direction yet
  vol_.dab(s);
  dabs_.push_back(s);
  return true;
}

std::vector<Step> stroke_along(Volume& v, const Brush& b, const std::vector<V3>& points, V3 dir) {
  dir = unit(dir);
  const float back = std::max(0.08f, 4.0f * b.radius);
  std::vector<V3> samples;
  Resampler rs(b.radius * 0.3f);
  for (const V3& p : points) rs.push(p, samples);
  StrokeDabs sd(v, b);
  v.begin_stroke();
  for (const V3& p : samples) sd.add(sub(p, mul(dir, back)), dir, 2 * back);
  v.end_stroke(sd.dabs());
  return sd.dabs();
}

std::vector<Step> dabs_from_rows(const std::vector<std::array<float, 9>>& rows, const Brush& b) {
  std::vector<Step> out;
  out.reserve(rows.size());
  for (const auto& r : rows) {
    Step s;
    s.kind = Kind::Stamp;
    s.op = b.op;
    s.a = {r[0], r[1], r[2]};
    s.n = {r[3], r[4], r[5]};
    s.b = {r[6], r[7], r[8]};
    s.radius = b.radius;
    s.strength = b.strength;
    s.mirror = b.mirror;
    s.stroke = 1;
    s.accumulate = b.accumulate;
    out.push_back(s);
  }
  return out;
}

std::array<float, 9> row_of(const Step& s) {
  return {s.a.x, s.a.y, s.a.z, s.n.x, s.n.y, s.n.z, s.b.x, s.b.y, s.b.z};
}

}  // namespace r3d::clay
