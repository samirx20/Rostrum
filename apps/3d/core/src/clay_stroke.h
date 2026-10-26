// Clay: how a stroke's dabs are found, the same for a mouse drag (pixels through a camera) and an agent's path
// (clay-space points and a direction). Moved from proofs/3d-clay (session.h).
//
// The path is resampled every `spacing` x the brush radius (each segment cut into max(1, length / spacing) equal
// parts, then the last point); each sample's ray meets the clay as it is at that moment, and the dab is shown at once
// (Volume::dab). When the stroke ends, the clay is put back and the dabs are applied as one unit (Volume::end_stroke),
// which is exactly what a replay of the stored dabs does: live = replay, bit for bit.
#pragma once
#include <vector>

#include "clay_dabs.h"
#include "clay_step.h"
#include "clay_volume.h"

namespace r3d::clay {

// Points of a path every `spacing`, fed one at a time: push() hands back the new samples (the point itself last), so
// the samples so far are always the proof's resampling of the points so far. A pen's pressure goes along: each
// sample gets the pressure between its two points (the distance is measured on the points alone).
class Resampler {
 public:
  explicit Resampler(float spacing) : spacing_(spacing) {}
  void push(V3 p, std::vector<V3>& out);
  void push(V3 p, float pressure, std::vector<V3>& out, std::vector<float>& pressures);

 private:
  float spacing_;
  bool have_ = false;
  V3 last_;
  float lastPressure_ = 1.0f;
};

// One stroke while it is drawn: dabs land where their rays meet the clay, and are shown at once.
class StrokeDabs {
 public:
  StrokeDabs(Volume& v, const Brush& b) : vol_(v), brush_(b) {}
  // a sample's ray (clay space, `dir` unit) and the pen's pressure there (1 without a pen); true when a dab landed
  bool add(V3 origin, V3 dir, float maxDist, float pressure = 1.0f);
  const std::vector<Step>& dabs() const { return dabs_; }
  bool hit = false;       // the last ray met the clay (on a face towards it, with Front faces only)
  V3 point, normal;       // where (clay space), when it did

 private:
  Volume& vol_;
  Brush brush_;
  std::vector<Step> dabs_;
  V3 prev_;
  bool havePrev_ = false;
};

// An agent's stroke along clay-space points: each dab where a ray along `dir` meets the clay (starting a little
// before the point: max(0.08 m, 4 x radius), reaching as far past it). Applied as one unit; returns the dabs.
std::vector<Step> stroke_along(Volume& v, const Brush& b, const std::vector<V3>& points, V3 dir);

// a stroke's dabs from stored rows (a.xyz n.xyz b.xyz radiusScale strengthScale) and its brush
std::vector<Step> dabs_from_rows(const std::vector<DabRow>& rows, const Brush& b);
DabRow row_of(const Step& s);

}  // namespace r3d::clay
