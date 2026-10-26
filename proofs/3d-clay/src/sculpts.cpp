// P-Clay proof: the comparison sculpts (member B). Throwaway proof code.
//
// Units are world (the voxel is 0.000625, so 1 mm is about 1.6 voxels). Volume comes from pieces (a dab moves the
// surface at most 2 voxels); brushes refine. Mirror (x -> -x) does the left side of everything drawn on the right.
#include "sculpts.h"

#include <cmath>
#include <cstdint>
#include <utility>
#include <vector>

namespace clay {
namespace {

using Pts = std::vector<V3>;
constexpr float kPi = 3.14159265f;
constexpr float kDeg = kPi / 180.0f;
constexpr bool M = true;  // mirrored

const V3 kFrontDir{0, 0, -1};  // rays from the front (+Z), into the face
const V3 kSideDir{-1, 0, 0};   // rays from the right side (+X); mirror does the left
const V3 kBackDir{0, 0, 1};    // rays from behind
const V3 kDownDir{0, -1, 0};   // rays from above

Brush brush(Op op, float radius, float strength, bool mirror) {
  Brush b;
  b.op = op;
  b.radius = radius;
  b.strength = strength;
  b.mirror = mirror;
  return b;
}

Camera make_cam(V3 eye, V3 target, float fovYDeg) {
  Camera c;
  c.eye[0] = eye.x, c.eye[1] = eye.y, c.eye[2] = eye.z;
  c.target[0] = target.x, c.target[1] = target.y, c.target[2] = target.z;
  c.fovYDeg = fovYDeg;
  return c;
}

// a smooth curve through control points (Catmull-Rom), `per` points per span
Pts curve(const Pts& c, int per = 6) {
  if (c.size() < 2) return c;
  Pts out;
  for (size_t i = 0; i + 1 < c.size(); ++i) {
    const V3 p0 = c[i ? i - 1 : 0], p1 = c[i], p2 = c[i + 1], p3 = c[i + 2 < c.size() ? i + 2 : i + 1];
    for (int j = 0; j < per; ++j) {
      const float t = float(j) / per, t2 = t * t, t3 = t2 * t;
      V3 q = mul(p1, 2.0f);
      q = add(q, mul(sub(p2, p0), t));
      q = add(q, mul(add(sub(mul(p0, 2.0f), mul(p1, 5.0f)), sub(mul(p2, 4.0f), p3)), t2));
      q = add(q, mul(add(sub(mul(p1, 3.0f), p0), sub(p3, mul(p2, 3.0f))), t3));
      out.push_back(mul(q, 0.5f));
    }
  }
  out.push_back(c.back());
  return out;
}

// a chain of capsules through the points (one piece per span)
void chain(Session& S, Op op, const Pts& p, float r, float blend, bool mirror) {
  for (size_t i = 0; i + 1 < p.size(); ++i) S.apply(piece(op, p[i], p[i + 1], r, blend, mirror));
}

// a point on a sphere around c: az from straight ahead (+Z) towards +X, el up, degrees
V3 on_sphere(V3 c, float R, float azDeg, float elDeg) {
  const float a = azDeg * kDeg, e = elDeg * kDeg;
  return {c.x + R * std::sin(a) * std::cos(e), c.y + R * std::sin(e), c.z + R * std::cos(a) * std::cos(e)};
}

// an eyelid's line around an eyeball: az a0..a1, elevation e0..e1 plus `lift` towards the middle
Pts lid_line(V3 c, float R, float a0, float a1, float e0, float e1, float lift, int n) {
  Pts p;
  for (int i = 0; i <= n; ++i) {
    const float t = float(i) / n;
    const float el = e0 + (e1 - e0) * t + lift * std::sin(kPi * std::pow(t, 0.85f));
    p.push_back(on_sphere(c, R, a0 + (a1 - a0) * t, el));
  }
  return p;
}

// an arc in a plane of constant z: centre (cx, cy), radius R, angles a0..a1 degrees (0 = +X, 90 = up)
Pts arc_xy(float cx, float cy, float z, float R, float a0, float a1, int n) {
  Pts p;
  for (int i = 0; i <= n; ++i) {
    const float a = (a0 + (a1 - a0) * float(i) / n) * kDeg;
    p.push_back({cx + R * std::cos(a), cy + R * std::sin(a), z});
  }
  return p;
}

// the camera's frame, as pixel_ray builds it
void cam_frame(const Camera& c, V3& eye, V3& f, V3& r, V3& u) {
  eye = {c.eye[0], c.eye[1], c.eye[2]};
  f = unit(sub(V3{c.target[0], c.target[1], c.target[2]}, eye));
  r = unit(cross(f, {0, 1, 0}));
  u = cross(r, f);
}

// where a world point shows in a width x height picture (the inverse of pixel_ray); z = 0
V3 to_pixel(const Camera& c, int width, int height, V3 p) {
  V3 eye, f, r, u;
  cam_frame(c, eye, f, r, u);
  const V3 v = sub(p, eye);
  const float zc = std::max(1e-6f, dot(v, f));
  const float t = std::tan(c.fovYDeg * kPi / 360.0f);
  const float x = dot(v, r) / zc, y = dot(v, u) / zc;
  return {(x / (t * float(width) / float(height)) + 1.0f) * width * 0.5f - 0.5f, (1.0f - y / t) * height * 0.5f - 0.5f,
          0.0f};
}

// A person with a mouse: looks at a feature (a world point, only to know where on the screen it is), drags over it.
// The mouse reports a point every ~3 px and the hand wobbles a little (about a pixel, slowly), fixed seed.
class Mouse {
 public:
  Mouse(Session& s, int w, int h) : S_(s), w_(w), h_(h) {}

  // a drag through what the person aims at, as one smooth hand movement
  void drag(const Brush& b, const Camera& c, const Pts& aim) {
    Pts px;
    for (const V3& p : aim) px.push_back(to_pixel(c, w_, h_, p));
    hand(b, c, curve(px, 8));
  }
  // loops over an area (building up, digging, rubbing in): `turns` loops of up to worldR around `centre`
  void scribble(const Brush& b, const Camera& c, V3 centre, float worldR, float turns) {
    V3 eye, f, r, u;
    cam_frame(c, eye, f, r, u);
    const V3 o = to_pixel(c, w_, h_, centre);
    const V3 e = to_pixel(c, w_, h_, add(centre, mul(r, worldR)));
    const float R = len(sub(e, o));
    const float phase = (rnd() + 1.0f) * kPi;
    const int n = std::max(8, int(turns * 28));
    Pts px;
    for (int i = 0; i <= n; ++i) {
      const float a = 2.0f * kPi * turns * float(i) / n;
      const float rr = R * (0.6f + 0.4f * std::sin(a * 0.43f + phase));
      px.push_back({o.x + rr * std::cos(a), o.y + rr * std::sin(a) * 0.9f, 0});
    }
    hand(b, c, px);
  }
  int strokes() const { return strokes_; }
  int dabs() const { return dabs_; }

 private:
  float rnd() {  // -1..1
    seed_ = seed_ * 1664525u + 1013904223u;
    return float(seed_ >> 8) * (2.0f / 16777216.0f) - 1.0f;
  }
  void hand(const Brush& b, const Camera& c, const Pts& path) {
    if (path.empty()) return;
    std::vector<std::pair<float, float>> out;
    float nx = 0, ny = 0;
    for (size_t i = 0; i + 1 < path.size(); ++i) {
      const V3 d = sub(path[i + 1], path[i]);
      const int k = std::max(1, int(len(d) / 3.0f));
      for (int j = 0; j < k; ++j) {
        nx = 0.85f * nx + 0.6f * rnd();
        ny = 0.85f * ny + 0.6f * rnd();
        const V3 p = add(path[i], mul(d, float(j) / k));
        out.push_back({p.x + nx, p.y + ny});
      }
    }
    out.push_back({path.back().x + nx, path.back().y + ny});
    Brush hand = b;  // a person drags with Accumulate off (the default in sculpting apps): passes don't pile up
    hand.accumulate = false;
    dabs_ += S_.stroke_screen(hand, out, c, w_, h_);
    ++strokes_;
  }

  Session& S_;
  int w_, h_;
  uint32_t seed_ = 20261026u;
  int strokes_ = 0, dabs_ = 0;
};

}  // namespace

// ---------------------------------------------------------------------------------------------------------------
// The agent's head: masses as pieces (skull, face, jaw, cheekbones, brow, nose, lips, eyes and lids, ears, neck),
// then the brushes: Smooth the joins, Flatten the planes, Add / Carve the soft forms, Crease the sharp lines, Pull a
// little. Crown y 0.117, chin y -0.103, neck base about y -0.19; nose tip z 0.11.
void sculpt_agent_head(Session& S) {
  // skull: one long capsule front to back (forehead z 0.077, back of the head z -0.107, 0.154 wide)
  S.apply(piece(Op::Add, {0, 0.04f, 0.0f}, {0, 0.032f, -0.03f}, 0.077f, 0, false));
  // face mass (maxilla), down to the mouth
  S.apply(piece(Op::Add, {0, -0.005f, 0.03f}, {0, -0.05f, 0.04f}, 0.044f, 0.03f, false));
  // cheekbones (zygomatic arch, out towards the ear)
  S.apply(piece(Op::Add, {0.045f, -0.012f, 0.052f}, {0.062f, -0.008f, 0.02f}, 0.012f, 0.018f, M));
  // masseter: fills the side of the face between cheekbone and jaw
  S.apply(ball(Op::Add, {0.047f, -0.042f, 0.012f}, 0.022f, 0.02f, M));
  // jaw: ramus down from below the ear, then the body to the chin
  S.apply(piece(Op::Add, {0.058f, -0.028f, -0.022f}, {0.057f, -0.07f, -0.016f}, 0.011f, 0.018f, M));
  S.apply(piece(Op::Add, {0.057f, -0.07f, -0.016f}, {0.022f, -0.093f, 0.056f}, 0.011f, 0.018f, M));
  // chin: a centre ball and two side bumps (a squarish chin)
  S.apply(ball(Op::Add, {0, -0.088f, 0.064f}, 0.016f, 0.014f, false));
  S.apply(ball(Op::Add, {0.01f, -0.092f, 0.06f}, 0.011f, 0.01f, M));
  // neck, the two neck muscles (SCM) from behind the ear to the collarbone notch, Adam's apple, trapezius, collarbones
  S.apply(piece(Op::Add, {0, -0.055f, -0.03f}, {0, -0.165f, -0.018f}, 0.042f, 0.03f, false));
  S.apply(piece(Op::Add, {0.052f, -0.035f, -0.035f}, {0.013f, -0.16f, 0.016f}, 0.0105f, 0.014f, M));
  S.apply(ball(Op::Add, {0, -0.112f, 0.022f}, 0.0075f, 0.008f, false));
  S.apply(piece(Op::Add, {0.025f, -0.085f, -0.055f}, {0.07f, -0.17f, -0.04f}, 0.016f, 0.022f, M));
  S.apply(piece(Op::Add, {0.016f, -0.168f, 0.02f}, {0.075f, -0.172f, -0.01f}, 0.008f, 0.015f, M));
  // brow ridge and glabella
  S.apply(piece(Op::Add, {0.011f, 0.031f, 0.077f}, {0.05f, 0.03f, 0.06f}, 0.0085f, 0.012f, M));
  S.apply(ball(Op::Add, {0, 0.026f, 0.076f}, 0.008f, 0.01f, false));

  // nose: bridge in two spans (thin at the root, a dip under the glabella), tip, wings, columella, nostrils
  S.apply(piece(Op::Add, {0, 0.016f, 0.076f}, {0, 0.0f, 0.088f}, 0.0055f, 0.008f, false));
  S.apply(piece(Op::Add, {0, 0.0f, 0.088f}, {0, -0.014f, 0.099f}, 0.0068f, 0.008f, false));
  S.apply(ball(Op::Add, {0, -0.019f, 0.1f}, 0.0085f, 0.006f, false));
  S.apply(ball(Op::Add, {0.0115f, -0.025f, 0.088f}, 0.0062f, 0.004f, M));
  S.apply(piece(Op::Add, {0, -0.025f, 0.099f}, {0, -0.03f, 0.09f}, 0.0032f, 0.003f, false));
  S.apply(piece(Op::Carve, {0.0068f, -0.0345f, 0.0935f}, {0.0072f, -0.0285f, 0.0915f}, 0.0024f, 0.001f, M));

  // eyes: eyeball, cornea bulge, a shallow pupil; lids as tubes along the lid margins on the eyeball
  const V3 E{0.031f, 0.006f, 0.058f};
  const float er = 0.013f;
  S.apply(ball(Op::Add, E, er, 0.004f, M));
  S.apply(ball(Op::Add, on_sphere(E, 0.0085f, 4, 0), 0.0058f, 0.0015f, M));
  S.apply(ball(Op::Carve, on_sphere(E, er + 0.0024f, 4, 0), 0.0022f, 0.0005f, M));
  chain(S, Op::Add, lid_line(E, er + 0.0012f, -55, 60, -2, 4, 24, 5), 0.003f, 0.0015f, M);   // upper lid
  chain(S, Op::Add, lid_line(E, er + 0.0012f, -55, 60, -2, 4, -18, 5), 0.0024f, 0.0015f, M);  // lower lid

  // mouth: the dental arch under the lips, upper lip (thicker at the middle, thin to the corner), lower lip, corners
  S.apply(piece(Op::Add, {-0.012f, -0.048f, 0.066f}, {0.012f, -0.048f, 0.066f}, 0.017f, 0.012f, false));
  S.apply(piece(Op::Add, {0, -0.0475f, 0.088f}, {0.009f, -0.0488f, 0.0855f}, 0.0042f, 0.004f, M));
  S.apply(piece(Op::Add, {0.009f, -0.0488f, 0.0855f}, {0.019f, -0.0515f, 0.0785f}, 0.0032f, 0.004f, M));
  S.apply(piece(Op::Add, {0, -0.0565f, 0.0865f}, {0.009f, -0.056f, 0.0845f}, 0.0055f, 0.004f, M));
  S.apply(piece(Op::Add, {0.009f, -0.056f, 0.0845f}, {0.0175f, -0.0528f, 0.0785f}, 0.0035f, 0.004f, M));
  S.apply(ball(Op::Carve, {0.0198f, -0.0518f, 0.0795f}, 0.0022f, 0.001f, M));

  // ears: root, the shell behind the bowl, helix rim (a C from above the tragus round to the lobe), lobe, antihelix,
  // the bowl (concha) dug in, tragus
  S.apply(piece(Op::Add, {0.068f, 0.008f, -0.012f}, {0.069f, -0.018f, -0.009f}, 0.0075f, 0.006f, M));
  S.apply(piece(Op::Add, {0.071f, 0.006f, -0.02f}, {0.073f, -0.012f, -0.02f}, 0.0065f, 0.004f, M));
  chain(S, Op::Add,
        {{0.069f, 0.012f, -0.001f}, {0.073f, 0.019f, -0.009f}, {0.077f, 0.017f, -0.02f}, {0.0795f, 0.006f, -0.027f},
         {0.079f, -0.008f, -0.026f}, {0.0765f, -0.02f, -0.018f}},
        0.0028f, 0.0015f, M);
  S.apply(ball(Op::Add, {0.0735f, -0.025f, -0.012f}, 0.0048f, 0.003f, M));
  chain(S, Op::Add,
        {{0.0745f, 0.011f, -0.013f}, {0.0765f, 0.004f, -0.019f}, {0.0765f, -0.008f, -0.019f},
         {0.0745f, -0.016f, -0.014f}},
        0.0021f, 0.0015f, M);
  S.apply(ball(Op::Carve, {0.0785f, -0.005f, -0.009f}, 0.006f, 0.0015f, M));
  S.apply(ball(Op::Add, {0.0705f, -0.006f, 0.0005f}, 0.0028f, 0.002f, M));

  // --- brushes. Stroke points are near the surface; each dab lands where a ray along the direction meets the clay.
  auto F = [](float x, float y) { return V3{x, y, 0.1f}; };       // seen from the front
  auto Sd = [](float y, float z) { return V3{0.09f, y, z}; };     // seen from the right side
  const V3 q34 = unit({-0.7f, 0, -0.7f});                         // from the front-right
  const V3 under = unit({0, 0.6f, -0.8f});                        // from below the chin

  // Smooth the joins: down the side of the face (outside the eye), along the jaw, under the chin, neck to skull
  S.stroke(brush(Op::Smooth, 0.015f, 0.8f, M), curve({F(0.06f, 0.035f), F(0.062f, -0.012f), F(0.055f, -0.05f),
                                                     F(0.03f, -0.088f)}),
           kFrontDir);
  S.stroke(brush(Op::Smooth, 0.014f, 0.8f, M), curve({Sd(-0.04f, 0.035f), Sd(-0.07f, 0.01f), Sd(-0.085f, -0.02f)}),
           kSideDir);
  S.stroke(brush(Op::Smooth, 0.014f, 0.7f, M),
           curve({{0.0f, -0.1f, 0.05f}, {0.03f, -0.095f, 0.03f}, {0.05f, -0.085f, 0.0f}}), under);
  S.stroke(brush(Op::Smooth, 0.016f, 0.7f, M), curve({Sd(-0.05f, -0.06f), Sd(-0.1f, -0.065f), Sd(-0.14f, -0.03f)}),
           kSideDir);
  S.stroke(brush(Op::Smooth, 0.012f, 0.6f, M), curve({Sd(0.0f, 0.06f), Sd(-0.03f, 0.05f), Sd(-0.05f, 0.03f)}),
           kSideDir);  // cheekbone into the cheek

  // Flatten the planes: forehead (two passes across), temples, the cheek plane below the cheekbone, side of the jaw,
  // the sides of the nose bridge
  S.stroke(brush(Op::Flatten, 0.018f, 0.5f, M), {F(0.0f, 0.065f), F(0.045f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Flatten, 0.018f, 0.5f, M), {F(0.0f, 0.087f), F(0.04f, 0.082f)}, kFrontDir);
  S.stroke(brush(Op::Flatten, 0.014f, 0.5f, M), {{0.07f, 0.035f, 0.035f}, {0.07f, 0.062f, 0.02f}},
           unit({-1, 0, -0.3f}));
  S.stroke(brush(Op::Flatten, 0.012f, 0.5f, M), {{0.056f, -0.025f, 0.045f}, {0.05f, -0.052f, 0.04f}}, q34);
  S.stroke(brush(Op::Flatten, 0.012f, 0.5f, M), {Sd(-0.04f, -0.015f), Sd(-0.07f, 0.0f)}, kSideDir);
  S.stroke(brush(Op::Flatten, 0.0045f, 0.4f, M), {{0.006f, 0.014f, 0.085f}, {0.008f, -0.01f, 0.095f}},
           unit({-0.6f, 0, -0.8f}));

  // Add: cheek fat over the cheekbone, philtrum columns, a little fullness to the lower lid's cheek
  S.stroke(brush(Op::Add, 0.01f, 0.5f, M), curve({F(0.028f, -0.016f), F(0.038f, -0.02f), F(0.047f, -0.018f)}),
           kFrontDir);
  S.stroke(brush(Op::Add, 0.0022f, 0.6f, M), {F(0.0036f, -0.033f), F(0.0042f, -0.0455f)}, kFrontDir);

  // Carve: the nasolabial fold (dug, then the cheek built above it, the lip side softened), the philtrum's groove,
  // under the lower lip (mentolabial), the tear trough
  const Pts fold = curve({F(0.018f, -0.023f), F(0.024f, -0.038f), F(0.027f, -0.055f)});
  S.stroke(brush(Op::Carve, 0.0035f, 0.5f, M), fold, kFrontDir);
  S.stroke(brush(Op::Add, 0.006f, 0.4f, M), curve({F(0.025f, -0.021f), F(0.032f, -0.036f), F(0.034f, -0.052f)}),
           kFrontDir);
  S.stroke(brush(Op::Smooth, 0.005f, 0.5f, M), {F(0.016f, -0.033f), F(0.022f, -0.05f)}, kFrontDir);
  S.stroke(brush(Op::Carve, 0.0025f, 0.4f, false), {F(0.0f, -0.033f), F(0.0f, -0.045f)}, kFrontDir);
  S.stroke(brush(Op::Carve, 0.005f, 0.5f, M), curve({F(0.0f, -0.066f), F(0.007f, -0.0655f), F(0.013f, -0.063f)}),
           kFrontDir);
  S.stroke(brush(Op::Carve, 0.003f, 0.3f, M), curve({F(0.02f, -0.006f), F(0.03f, -0.011f), F(0.042f, -0.008f)}),
           kFrontDir);

  // Pull: the nose tip a touch down, the jaw angle back, the earlobe down
  S.stroke(brush(Op::Pull, 0.006f, 0.4f, M), {F(0.0f, -0.013f), F(0.0f, -0.022f)}, kFrontDir);
  S.stroke(brush(Op::Pull, 0.008f, 0.4f, M), {Sd(-0.066f, -0.006f), Sd(-0.075f, -0.02f)}, kSideDir);
  S.stroke(brush(Op::Pull, 0.004f, 0.5f, M), {Sd(-0.022f, -0.012f), Sd(-0.03f, -0.012f)}, kSideDir);

  // Crease the sharp lines: the mouth line, the upper lid fold, the lower lid line, the alar groove round the nose
  // wing, the scapha inside the helix, the corner of the mouth into the cheek
  S.stroke(brush(Op::Crease, 0.004f, 0.8f, M),
           curve({F(0.0f, -0.0513f), F(0.008f, -0.0518f), F(0.015f, -0.0516f), F(0.0205f, -0.052f)}), kFrontDir);
  S.stroke(brush(Op::Crease, 0.0035f, 0.6f, M), curve(lid_line(E, er + 0.0035f, -45, 55, 8, 12, 24, 6)), kFrontDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.35f, M), curve(lid_line(E, er + 0.0045f, -40, 50, -8, -4, -16, 6)),
           kFrontDir);
  S.stroke(brush(Op::Crease, 0.0035f, 0.7f, M), curve(arc_xy(0.0115f, -0.025f, 0.092f, 0.0075f, 115, -70, 6)),
           unit({-0.35f, 0, -1}));
  S.stroke(brush(Op::Crease, 0.0035f, 0.6f, M),
           curve({{0.08f, 0.014f, -0.013f}, {0.08f, 0.01f, -0.022f}, {0.08f, 0.0f, -0.0255f},
                  {0.08f, -0.012f, -0.0235f}}),
           kSideDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.4f, M), {F(0.021f, -0.052f), F(0.024f, -0.058f)}, kFrontDir);

  // last: a light smooth down the nose bridge and over the chin
  S.stroke(brush(Op::Smooth, 0.006f, 0.4f, false), {F(0.0f, 0.016f), F(0.0f, -0.01f)}, kFrontDir);
  S.stroke(brush(Op::Smooth, 0.01f, 0.5f, M), {F(0.0f, -0.08f), F(0.012f, -0.09f)}, kFrontDir);
}

// ---------------------------------------------------------------------------------------------------------------
// The agent's character: about 2.8 heads tall. Big round head with a hair cap, cartoon eyes with upper lids, a button
// nose, a smile; a pear-shaped body, short legs, shoes with flat soles on y = -0.125, arms with mitts; a belt with a
// buckle, shirt folds, a V collar, cuffs, knee folds, trouser hems, sole lines; the joins smoothed.
void sculpt_agent_character(Session& S) {
  // head (top y 0.119), the lower face, the hair cap (shows on top and at the back; the hairline is where it meets)
  S.apply(ball(Op::Add, {0, 0.075f, 0}, 0.044f, 0, false));
  S.apply(ball(Op::Add, {0, 0.06f, 0.006f}, 0.038f, 0.015f, false));
  S.apply(ball(Op::Add, {0, 0.086f, -0.01f}, 0.046f, 0, false));
  // ears
  S.apply(ball(Op::Add, {0.044f, 0.072f, -0.002f}, 0.009f, 0.004f, M));
  S.apply(ball(Op::Carve, {0.0505f, 0.072f, 0.0005f}, 0.0055f, 0.001f, M));
  // neck, torso, belly / hips
  S.apply(piece(Op::Add, {0, 0.035f, 0}, {0, 0.024f, 0}, 0.013f, 0.008f, false));
  S.apply(piece(Op::Add, {0, 0.008f, 0}, {0, -0.035f, 0.002f}, 0.03f, 0.01f, false));
  S.apply(ball(Op::Add, {0, -0.04f, 0.002f}, 0.031f, 0.012f, false));
  // legs, shoes, the soles cut flat at y = -0.125
  S.apply(piece(Op::Add, {0.016f, -0.065f, 0}, {0.018f, -0.108f, 0}, 0.0125f, 0.008f, M));
  S.apply(piece(Op::Add, {0.019f, -0.117f, -0.004f}, {0.021f, -0.118f, 0.024f}, 0.0098f, 0.006f, M));
  S.apply(ball(Op::Carve, {0.02f, -0.155f, 0.01f}, 0.03f, 0, M));
  // arms: upper arm, forearm, mitt, thumb
  S.apply(piece(Op::Add, {0.03f, 0.022f, 0}, {0.045f, -0.008f, 0.004f}, 0.0095f, 0.008f, M));
  S.apply(piece(Op::Add, {0.045f, -0.008f, 0.004f}, {0.05f, -0.035f, 0.014f}, 0.0085f, 0.004f, M));
  S.apply(ball(Op::Add, {0.052f, -0.046f, 0.016f}, 0.0115f, 0.004f, M));
  S.apply(piece(Op::Add, {0.046f, -0.04f, 0.024f}, {0.045f, -0.045f, 0.028f}, 0.0045f, 0.003f, M));
  // face: cheeks, nose, eyes (eyeball, pupil dimple, an upper lid over the top)
  S.apply(ball(Op::Add, {0.025f, 0.061f, 0.03f}, 0.011f, 0.01f, M));
  S.apply(ball(Op::Add, {0, 0.068f, 0.043f}, 0.007f, 0.004f, false));
  const V3 E{0.016f, 0.08f, 0.036f};
  S.apply(ball(Op::Add, E, 0.0085f, 0.002f, M));
  S.apply(ball(Op::Carve, on_sphere(E, 0.0085f + 0.0015f, 3, 2), 0.003f, 0.0005f, M));
  chain(S, Op::Add, lid_line(E, 0.0092f, -55, 60, 5, 10, 32, 4), 0.0024f, 0.0015f, M);

  auto F = [](float x, float y, float z) { return V3{x, y, z}; };
  const V3 q34 = unit({-0.7f, 0, -0.7f});

  // Smooth the joins: neck, shoulders, hips into legs, wrists, ankles
  S.stroke(brush(Op::Smooth, 0.008f, 0.5f, M), {F(0.0f, 0.03f, 0.05f), F(0.022f, 0.03f, 0.05f)}, kFrontDir);
  S.stroke(brush(Op::Smooth, 0.009f, 0.6f, M), curve({F(0.022f, 0.032f, 0.05f), F(0.036f, 0.026f, 0.05f),
                                                    F(0.042f, 0.012f, 0.05f)}),
           kFrontDir);
  S.stroke(brush(Op::Smooth, 0.009f, 0.6f, M), {F(0.004f, -0.063f, 0.05f), F(0.03f, -0.064f, 0.05f)}, kFrontDir);
  S.stroke(brush(Op::Smooth, 0.009f, 0.6f, M), {F(0.004f, -0.063f, -0.05f), F(0.03f, -0.064f, -0.05f)}, kBackDir);
  S.stroke(brush(Op::Smooth, 0.005f, 0.5f, M), {F(0.044f, -0.036f, 0.04f), F(0.058f, -0.037f, 0.04f)}, kFrontDir);
  S.stroke(brush(Op::Smooth, 0.006f, 0.5f, M), {F(0.01f, -0.112f, 0.05f), F(0.028f, -0.112f, 0.05f)}, kFrontDir);

  // Flatten: the belly front a little, the tops of the shoes (planes, not balls)
  S.stroke(brush(Op::Flatten, 0.014f, 0.3f, M), {F(0.0f, -0.01f, 0.06f), F(0.0f, -0.045f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Flatten, 0.006f, 0.5f, M), {F(0.02f, -0.108f, 0.0f), F(0.021f, -0.111f, 0.026f)},
           unit({0, -0.6f, -0.8f}));

  // Add: brows, the belt band (front and back), the buckle
  S.stroke(brush(Op::Add, 0.003f, 0.8f, M), curve({F(0.008f, 0.094f, 0.06f), F(0.017f, 0.0965f, 0.06f),
                                                 F(0.025f, 0.094f, 0.06f)}),
           kFrontDir);
  S.stroke(brush(Op::Add, 0.004f, 0.8f, M), {F(0.0f, -0.021f, 0.06f), F(0.031f, -0.021f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Add, 0.004f, 0.8f, M), {F(0.0f, -0.021f, -0.06f), F(0.031f, -0.021f, -0.06f)}, kBackDir);
  S.stroke(brush(Op::Add, 0.0045f, 1.0f, M), {F(0.0f, -0.021f, 0.06f), F(0.0045f, -0.021f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Flatten, 0.004f, 0.6f, M), {F(0.0f, -0.021f, 0.06f), F(0.004f, -0.021f, 0.06f)}, kFrontDir);

  // Pull: a forelock out of the hair, forwards over the forehead
  S.stroke(brush(Op::Pull, 0.008f, 0.8f, false), {F(0.0f, 0.13f, 0.0f), F(0.0f, 0.125f, 0.02f)}, kDownDir);

  // Crease: the smile; the belt's edges (front and back) and the buckle's sides; V collar; shirt folds; elbow fold;
  // cuffs; knee folds; trouser hems; the crotch seam; the sole lines; the line round the eyes' tops
  S.stroke(brush(Op::Crease, 0.0035f, 0.8f, M), curve({F(0.0f, 0.0545f, 0.06f), F(0.008f, 0.0555f, 0.06f),
                                                     F(0.015f, 0.059f, 0.06f)}),
           kFrontDir);
  for (float y : {-0.0165f, -0.0255f}) {
    S.stroke(brush(Op::Crease, 0.003f, 0.7f, M), {F(0.0f, y, 0.06f), F(0.032f, y, 0.06f)}, kFrontDir);
    S.stroke(brush(Op::Crease, 0.003f, 0.7f, M), {F(0.0f, y, -0.06f), F(0.032f, y, -0.06f)}, kBackDir);
  }
  S.stroke(brush(Op::Crease, 0.0025f, 0.7f, M), {F(0.0058f, -0.016f, 0.06f), F(0.0058f, -0.026f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.7f, M), {F(0.0f, 0.0f, 0.06f), F(0.013f, 0.021f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.5f, M), {F(0.025f, 0.012f, 0.06f), F(0.012f, -0.008f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.5f, M), {F(0.028f, 0.0f, 0.06f), F(0.018f, -0.012f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.0025f, 0.5f, M), {F(0.041f, -0.006f, 0.05f), F(0.047f, -0.01f, 0.05f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.0025f, 0.7f, M), {F(0.041f, -0.03f, 0.05f), F(0.059f, -0.032f, 0.05f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.0025f, 0.5f, M), {F(0.012f, -0.088f, 0.05f), F(0.02f, -0.092f, 0.05f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.0025f, 0.5f, M), {F(0.013f, -0.097f, 0.05f), F(0.022f, -0.099f, 0.05f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.6f, M), {F(0.006f, -0.107f, 0.05f), F(0.03f, -0.107f, 0.05f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.6f, M), {F(0.006f, -0.107f, -0.05f), F(0.03f, -0.107f, -0.05f)}, kBackDir);
  S.stroke(brush(Op::Crease, 0.003f, 0.6f, false), {F(0.0f, -0.05f, 0.06f), F(0.0f, -0.068f, 0.06f)}, kFrontDir);
  S.stroke(brush(Op::Crease, 0.0025f, 0.6f, M), {F(0.06f, -0.1215f, 0.03f), F(0.06f, -0.1215f, -0.012f)}, kSideDir);
  S.stroke(brush(Op::Crease, 0.0025f, 0.6f, M), curve(lid_line(E, 0.0115f, -50, 60, 10, 14, 38, 5)), q34);
}

// ---------------------------------------------------------------------------------------------------------------
// A head made with a mouse: four pieces (skull, face, neck, the two eyeballs with symmetry on), then everything else
// as drags in a 1280x720 viewport, the way a person works: build up with repeated passes and loops, turn the view
// (front, three-quarter, side, from below for the nostrils), dig, crease, smooth. Symmetry on throughout.
void sculpt_mouse_head(Session& S, int width, int height) {
  S.apply(ball(Op::Add, {0, 0.035f, -0.012f}, 0.079f, 0, false));                              // skull
  S.apply(piece(Op::Add, {0, 0.0f, 0.028f}, {0, -0.06f, 0.038f}, 0.046f, 0.03f, false));        // face and jaw
  S.apply(piece(Op::Add, {0, -0.06f, -0.028f}, {0, -0.165f, -0.02f}, 0.042f, 0.03f, false));    // neck
  const V3 E{0.031f, 0.006f, 0.056f};
  S.apply(ball(Op::Add, E, 0.013f, 0.003f, M));                                                  // eyeballs

  // working views: closer than the pictures, as a person zooms in
  const Camera Fr = make_cam({0, 0.0f, 0.55f}, {0, -0.01f, 0}, 30);
  const Camera Q = make_cam({0.38f, 0.0f, 0.4f}, {0, -0.01f, 0}, 30);
  const Camera Sd = make_cam({0.55f, 0.0f, -0.01f}, {0, -0.01f, -0.01f}, 30);
  const Camera Lo = make_cam({0, -0.24f, 0.42f}, {0, -0.03f, 0.02f}, 30);
  Mouse m(S, width, height);

  // brow: back and forth along the brow ridge
  m.drag(brush(Op::Add, 0.009f, 0.8f, M), Fr,
         {{0.006f, 0.03f, 0.08f}, {0.03f, 0.034f, 0.075f}, {0.05f, 0.027f, 0.06f}, {0.03f, 0.032f, 0.075f},
          {0.008f, 0.029f, 0.08f}, {0.03f, 0.033f, 0.075f}, {0.05f, 0.027f, 0.06f}});
  // nose: drags down the middle, each starting lower, so the tip builds most; then the sides of the bridge planed
  for (float ys : {0.022f, 0.014f, 0.006f, -0.002f, -0.008f, -0.012f})
    m.drag(brush(Op::Add, 0.0075f, 1.0f, M), Fr, {{0, ys, 0.08f}, {0, -0.022f, 0.09f}});
  m.drag(brush(Op::Flatten, 0.005f, 0.6f, M), Q, {{0.007f, 0.015f, 0.08f}, {0.009f, -0.01f, 0.09f}});
  // nose wings: loops
  for (int i = 0; i < 2; ++i) m.scribble(brush(Op::Add, 0.005f, 0.9f, M), Fr, {0.011f, -0.026f, 0.085f}, 0.004f, 2);
  // cheekbones (three-quarter view), twice
  for (int i = 0; i < 2; ++i)
    m.drag(brush(Op::Add, 0.012f, 0.7f, M), Q,
           {{0.035f, -0.01f, 0.06f}, {0.055f, -0.008f, 0.045f}, {0.062f, 0.0f, 0.02f}});
  // lids: along the upper lid line twice and the lower once, then the fold above, a soft dig under the eye
  for (int i = 0; i < 2; ++i)
    m.drag(brush(Op::Add, 0.0035f, 0.9f, M), Fr, lid_line(E, 0.0145f, -55, 60, -2, 4, 24, 6));
  m.drag(brush(Op::Add, 0.003f, 0.9f, M), Fr, lid_line(E, 0.0145f, -55, 60, -2, 4, -18, 6));
  m.drag(brush(Op::Crease, 0.0035f, 0.8f, M), Fr, lid_line(E, 0.017f, -45, 55, 8, 12, 24, 6));
  m.drag(brush(Op::Carve, 0.004f, 0.4f, M), Fr, {{0.022f, -0.008f, 0.07f}, {0.032f, -0.011f, 0.07f},
                                                 {0.042f, -0.006f, 0.065f}});
  // mouth: build the muzzle with loops, the upper lip (back and forth), the lower lip, the mouth line, the philtrum,
  // under the lower lip
  m.scribble(brush(Op::Add, 0.012f, 0.6f, M), Fr, {0.01f, -0.05f, 0.08f}, 0.012f, 1.5f);
  m.drag(brush(Op::Add, 0.0055f, 0.9f, M), Fr,
         {{0, -0.047f, 0.088f}, {0.012f, -0.049f, 0.085f}, {0.019f, -0.0515f, 0.08f}, {0.012f, -0.0488f, 0.085f},
          {0, -0.0472f, 0.088f}, {0.012f, -0.049f, 0.085f}, {0.019f, -0.0515f, 0.08f}});
  m.drag(brush(Op::Add, 0.006f, 0.9f, M), Fr,
         {{0, -0.057f, 0.087f}, {0.015f, -0.0555f, 0.083f}, {0, -0.0568f, 0.087f}, {0.015f, -0.0555f, 0.083f}});
  m.drag(brush(Op::Crease, 0.004f, 1.0f, M), Fr, {{0, -0.0515f, 0.09f}, {0.01f, -0.052f, 0.088f},
                                                  {0.021f, -0.0525f, 0.082f}});
  m.drag(brush(Op::Carve, 0.0025f, 0.7f, M), Fr, {{0, -0.034f, 0.088f}, {0, -0.046f, 0.09f}});
  m.drag(brush(Op::Carve, 0.005f, 0.7f, M), Fr, {{0, -0.066f, 0.085f}, {0.013f, -0.063f, 0.082f}});
  // chin: loops
  m.scribble(brush(Op::Add, 0.01f, 0.8f, M), Fr, {0, -0.087f, 0.075f}, 0.008f, 2);
  // three-quarter: the nasolabial fold dug and softened, the groove round the nose wing
  m.drag(brush(Op::Carve, 0.0035f, 0.8f, M), Q, {{0.018f, -0.024f, 0.085f}, {0.025f, -0.04f, 0.08f},
                                                 {0.028f, -0.056f, 0.075f}});
  m.drag(brush(Op::Smooth, 0.005f, 0.5f, M), Q, {{0.016f, -0.033f, 0.085f}, {0.022f, -0.05f, 0.08f}});
  m.drag(brush(Op::Crease, 0.0035f, 0.8f, M), Q, arc_xy(0.0115f, -0.026f, 0.088f, 0.0075f, 115, -70, 6));
  // from below: the nostrils, two short digs each
  for (int i = 0; i < 2; ++i)
    m.drag(brush(Op::Carve, 0.0026f, 1.0f, M), Lo, {{0.0068f, -0.032f, 0.094f}, {0.0072f, -0.031f, 0.0905f}});
  // side: the jaw line twice, flattened; the ear built with loops, its rim, the bowl dug, the inner line, the lobe
  // pulled down; the neck muscle
  for (int i = 0; i < 2; ++i)
    m.drag(brush(Op::Add, 0.01f, 0.8f, M), Sd,
           {{0.06f, -0.03f, -0.022f}, {0.058f, -0.07f, -0.014f}, {0.035f, -0.09f, 0.04f}});
  m.drag(brush(Op::Flatten, 0.014f, 0.5f, M), Sd, {{0.06f, -0.04f, -0.01f}, {0.058f, -0.07f, 0.01f}});
  for (int i = 0; i < 3; ++i) m.scribble(brush(Op::Add, 0.008f, 1.0f, M), Sd, {0.07f, -0.003f, -0.014f}, 0.012f, 2);
  const Pts helix{{0.075f, 0.012f, -0.001f}, {0.075f, 0.019f, -0.009f}, {0.075f, 0.017f, -0.02f},
                  {0.075f, 0.006f, -0.027f}, {0.075f, -0.008f, -0.026f}, {0.075f, -0.02f, -0.018f},
                  {0.075f, -0.026f, -0.012f}};
  for (int i = 0; i < 2; ++i) m.drag(brush(Op::Add, 0.0035f, 1.0f, M), Sd, helix);
  for (int i = 0; i < 2; ++i) m.scribble(brush(Op::Carve, 0.005f, 1.0f, M), Sd, {0.075f, -0.005f, -0.009f}, 0.003f, 2);
  m.drag(brush(Op::Crease, 0.0035f, 0.8f, M), Sd,
         {{0.075f, 0.013f, -0.012f}, {0.075f, 0.009f, -0.021f}, {0.075f, -0.001f, -0.024f},
          {0.075f, -0.012f, -0.022f}});
  m.drag(brush(Op::Pull, 0.004f, 0.7f, M), Sd, {{0.075f, -0.02f, -0.012f}, {0.075f, -0.03f, -0.012f}});
  for (int i = 0; i < 2; ++i)
    m.drag(brush(Op::Add, 0.008f, 0.7f, M), Sd, {{0.05f, -0.04f, -0.035f}, {0.03f, -0.1f, -0.01f},
                                                 {0.013f, -0.16f, 0.018f}});
  // front again: plane the forehead with a zigzag
  m.drag(brush(Op::Flatten, 0.018f, 0.5f, M), Fr,
         {{0.0f, 0.09f, 0.07f}, {0.045f, 0.085f, 0.06f}, {0.0f, 0.075f, 0.075f}, {0.045f, 0.07f, 0.065f},
          {0.0f, 0.06f, 0.078f}, {0.045f, 0.055f, 0.065f}});
  // smooth it together: down the cheek and jaw (front), the cheek (three-quarter), the neck join (side)
  m.drag(brush(Op::Smooth, 0.016f, 0.6f, M), Fr, {{0.055f, 0.0f, 0.05f}, {0.056f, -0.035f, 0.05f},
                                                  {0.045f, -0.065f, 0.05f}, {0.025f, -0.09f, 0.06f}});
  m.drag(brush(Op::Smooth, 0.016f, 0.6f, M), Q, {{0.06f, 0.02f, 0.03f}, {0.062f, -0.02f, 0.03f},
                                                 {0.055f, -0.06f, 0.02f}});
  m.drag(brush(Op::Smooth, 0.016f, 0.6f, M), Sd, {{0.05f, -0.06f, -0.06f}, {0.05f, -0.09f, -0.03f},
                                                  {0.05f, -0.1f, 0.0f}, {0.05f, -0.08f, 0.03f}});
}

// ---------------------------------------------------------------------------------------------------------------
// cameras: the bust (crown y 0.117 to the neck's base about y -0.207) fills about 70-75 % of the frame height
Camera head_three_quarter() { return make_cam({0.56f, 0.0f, 0.6f}, {0, -0.045f, 0}, 30); }
Camera head_front() { return make_cam({0, -0.035f, 0.82f}, {0, -0.045f, 0}, 30); }
// the whole character (y -0.125 .. 0.13) about 80 % of the frame height
Camera character_three_quarter() { return make_cam({0.36f, 0.07f, 0.46f}, {0, 0.0f, 0}, 30); }

}  // namespace clay
