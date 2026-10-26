// P-Clay proof: a sculpting session. The clay, the steps it took, and the two ways a hand or an agent puts strokes
// on it: along world-space lines (an agent) or along pixel paths through a camera (a mouse). Throwaway proof code.
//
// A stroke is one unit: while it is drawn every dab is shown at once (Clay::dab, a preview), and when it ends the
// clay is put back as it was before the stroke and the whole stroke is applied in one pass (Clay::end_stroke). Replay
// applies the same one pass, so live and replay give the same clay bit for bit.
#pragma once
#include <algorithm>
#include <cmath>
#include <functional>
#include <vector>

#include "clay.h"
#include "view.h"

namespace clay {

inline V3 add(V3 a, V3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline V3 sub(V3 a, V3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline V3 mul(V3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
inline float dot(V3 a, V3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline V3 cross(V3 a, V3 b) { return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x}; }
inline float len(V3 a) { return std::sqrt(dot(a, a)); }
inline V3 unit(V3 a) { return mul(a, 1.0f / std::max(1e-12f, len(a))); }

inline Step piece(Op op, V3 a, V3 b, float r, float blend, bool mirror) {
  Step s;
  s.kind = Kind::Piece;
  s.op = op;
  s.a = a;
  s.b = b;
  s.radius = r;
  s.blend = blend;
  s.mirror = mirror;
  return s;
}
inline Step ball(Op op, V3 a, float r, float blend, bool mirror) { return piece(op, a, a, r, blend, mirror); }

// the ray through pixel (px, py) of a width x height picture (top-left origin), as View draws it (fovYDeg vertical)
inline void pixel_ray(const Camera& c, int width, int height, float px, float py, V3& origin, V3& dir) {
  const V3 eye{c.eye[0], c.eye[1], c.eye[2]}, tgt{c.target[0], c.target[1], c.target[2]};
  const V3 f = unit(sub(tgt, eye));
  const V3 r = unit(cross(f, {0, 1, 0}));
  const V3 u = cross(r, f);
  const float t = std::tan(c.fovYDeg * 3.14159265f / 360.0f);
  const float x = (2.0f * (px + 0.5f) / width - 1.0f) * t * float(width) / float(height);
  const float y = (1.0f - 2.0f * (py + 0.5f) / height) * t;
  origin = eye;
  dir = unit(add(f, add(mul(r, x), mul(u, y))));
}

struct Brush {
  Op op = Op::Add;
  float radius = 0.01f;   // world
  float strength = 0.5f;  // 0..1
  bool mirror = false;
};

struct Session {
  Clay clay;
  std::vector<Step> steps;
  uint32_t strokes = 0;
  std::function<void(Session&)> afterDab;   // live view: called after every dab is shown (preview)
  std::function<void(Session&)> afterUnit;  // --check: called after every piece and every finished stroke
  explicit Session(float voxel) : clay(voxel) {}

  void apply(const Step& s) {  // a piece (or a single dab as its own unit)
    clay.apply(s);
    steps.push_back(s);
    if (afterUnit) afterUnit(*this);
  }

  // A stroke along world points; each dab lands where a ray along `dir` (unit) meets the clay as it is now.
  int stroke(const Brush& b, const std::vector<V3>& pts, V3 dir) {
    dir = unit(dir);
    return run(b, resample(pts, b.radius), [&](V3 p, V3& o, V3& d) {
      o = sub(p, mul(dir, 0.08f));
      d = dir;
      return 0.16f;
    });
  }
  // A stroke along pixels of a camera's picture (a mouse drag): each dab where the pixel's ray meets the clay.
  int stroke_screen(const Brush& b, const std::vector<std::pair<float, float>>& pixels, const Camera& cam, int width,
                    int height) {
    std::vector<V3> pts;  // pixels as points of the picture, resampled there
    for (auto [x, y] : pixels) pts.push_back({x, y, 0});
    // dabs every 0.3 brush radius, as the brush looks on screen at the camera's target distance (the same spacing as
    // world strokes; dabs every 2 px piled up and grew towards the camera, each landing on the one before)
    const V3 eye{cam.eye[0], cam.eye[1], cam.eye[2]}, tgt{cam.target[0], cam.target[1], cam.target[2]};
    const float depth = len(sub(tgt, eye));
    const float radiusPx = b.radius * float(height) / (2.0f * depth * std::tan(cam.fovYDeg * 3.14159265f / 360.0f));
    return run(b, resample(pts, std::max(radiusPx, 3.0f)), [&](V3 p, V3& o, V3& d) {
      pixel_ray(cam, width, height, p.x, p.y, o, d);
      return 4.0f;
    });
  }

 private:
  static std::vector<V3> resample(const std::vector<V3>& pts, float radius) {
    std::vector<V3> out;
    const float spacing = radius * 0.3f;
    for (size_t i = 0; i + 1 < pts.size(); ++i) {
      const V3 seg = sub(pts[i + 1], pts[i]);
      const int k = std::max(1, int(len(seg) / spacing));
      for (int j = 0; j < k; ++j) out.push_back(add(pts[i], mul(seg, float(j) / k)));
    }
    if (!pts.empty()) out.push_back(pts.back());
    return out;
  }

  template <class Ray> int run(const Brush& b, const std::vector<V3>& samples, Ray ray) {
    const uint32_t id = ++strokes;
    std::vector<Step> dabs;
    V3 prev{0, 0, 0};
    bool havePrev = false;
    clay.begin_stroke();
    for (const V3& p : samples) {
      V3 o, d, on, nrm;
      const float maxDist = ray(p, o, d);
      if (!clay.cast(o, d, maxDist, on, nrm)) continue;
      Step s;
      s.kind = Kind::Stamp;
      s.op = b.op;
      s.a = on;
      s.n = nrm;
      s.radius = b.radius;
      s.strength = b.strength;
      s.mirror = b.mirror;
      s.stroke = id;
      // Pull: the pull vector (along the drag, in the surface); Crease: the line's direction
      const V3 along = havePrev ? sub(on, prev) : V3{0, 0, 0};
      const V3 tang = sub(along, mul(nrm, dot(along, nrm)));
      if (b.op == Op::Pull) s.b = mul(unit(tang), b.radius * b.strength * 0.5f);
      if (b.op == Op::Crease) s.b = unit(tang);
      prev = on;
      havePrev = true;
      if ((b.op == Op::Pull || b.op == Op::Crease) && len(tang) == 0) continue;  // no direction yet
      clay.dab(s);
      dabs.push_back(s);
      if (afterDab) afterDab(*this);
    }
    clay.end_stroke(dabs);
    steps.insert(steps.end(), dabs.begin(), dabs.end());
    if (afterUnit) afterUnit(*this);
    return int(dabs.size());
  }
};

// Replay: pieces one by one, each stroke (same non-zero `stroke` id, in a row) as one unit.
inline void replay(Clay& c, const std::vector<Step>& steps) {
  for (size_t i = 0; i < steps.size();) {
    if (steps[i].kind == Kind::Stamp && steps[i].stroke) {
      size_t j = i;
      while (j < steps.size() && steps[j].kind == Kind::Stamp && steps[j].stroke == steps[i].stroke) ++j;
      c.apply_stroke({steps.begin() + i, steps.begin() + j});
      i = j;
    } else {
      c.apply(steps[i++]);
    }
  }
}

}  // namespace clay
