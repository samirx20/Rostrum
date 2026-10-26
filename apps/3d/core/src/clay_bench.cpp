// Clay: the replay bench behind the `clay_bench` check request (clay_replay.h). The clay is the proof's bench clay
// (proofs/3d-clay/src/main.cpp: sculpt_head, random_strokes; the same steps and seed), at the proof's grain 0.625 mm.
#include <tbb/task_arena.h>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <utility>
#include <vector>

#include "clay_replay.h"
#include "clay_stroke.h"

namespace r3d::clay {

namespace {

constexpr float kVoxel = 0.000625f;

double ms_since(std::chrono::steady_clock::time_point t0) {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

Step piece(Op op, V3 a, V3 b, float r, float blend, bool mirror) {
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
Step ball(Op op, V3 a, float r, float blend, bool mirror) { return piece(op, a, a, r, blend, mirror); }

// a brush as the proof's (accumulate on)
Brush brush(Op op, float r, float strength, bool mirror) {
  Brush b;
  b.op = op;
  b.radius = r;
  b.strength = strength;
  b.mirror = mirror;
  b.accumulate = true;
  return b;
}

// The clay as it is sculpted: pieces and strokes applied, each stroke's dabs kept.
struct Sculpt {
  Volume& v;
  std::vector<Step> pieces;
  std::vector<std::vector<Step>> strokes;
  void apply(const Step& s) {
    v.apply(s);
    pieces.push_back(s);
  }
  void stroke(const Brush& b, const std::vector<V3>& pts, V3 dir) {
    std::vector<Step> d = stroke_along(v, b, pts, dir);
    if (!d.empty()) strokes.push_back(std::move(d));
  }
};

// The proof's scripted head (part 1's; all pieces come before the strokes).
void sculpt_head(Sculpt& S) {
  const bool M = true;
  S.apply(ball(Op::Add, {0, 0.035f, -0.01f}, 0.082f, 0, false));
  S.apply(piece(Op::Add, {0, 0.03f, -0.03f}, {0, 0.01f, -0.06f}, 0.07f, 0.03f, false));
  S.apply(piece(Op::Add, {0, 0.01f, 0.03f}, {0, -0.045f, 0.035f}, 0.052f, 0.035f, false));
  S.apply(piece(Op::Add, {0.044f, -0.03f, -0.005f}, {0.018f, -0.083f, 0.045f}, 0.02f, 0.025f, M));
  S.apply(ball(Op::Add, {0, -0.088f, 0.058f}, 0.019f, 0.02f, false));
  S.apply(piece(Op::Add, {0, -0.05f, -0.02f}, {0, -0.17f, -0.035f}, 0.043f, 0.025f, false));
  S.apply(ball(Op::Add, {0.048f, -0.008f, 0.052f}, 0.02f, 0.022f, M));
  S.apply(ball(Op::Carve, {0.031f, 0.016f, 0.086f}, 0.019f, 0.012f, M));
  S.apply(ball(Op::Add, {0.031f, 0.013f, 0.062f}, 0.012f, 0.003f, M));
  S.apply(piece(Op::Add, {0.019f, 0.021f, 0.071f}, {0.043f, 0.021f, 0.066f}, 0.0045f, 0.004f, M));
  S.apply(piece(Op::Add, {0.021f, 0.004f, 0.071f}, {0.041f, 0.005f, 0.067f}, 0.0035f, 0.004f, M));
  S.apply(piece(Op::Add, {0.01f, 0.036f, 0.079f}, {0.05f, 0.036f, 0.064f}, 0.0095f, 0.012f, M));
  S.apply(piece(Op::Add, {0, 0.026f, 0.081f}, {0, -0.014f, 0.098f}, 0.0085f, 0.012f, false));
  S.apply(ball(Op::Add, {0, -0.016f, 0.097f}, 0.0105f, 0.006f, false));
  S.apply(ball(Op::Add, {0.011f, -0.02f, 0.087f}, 0.0068f, 0.006f, M));
  S.apply(ball(Op::Carve, {0.0062f, -0.0275f, 0.0905f}, 0.0028f, 0.002f, M));
  S.apply(piece(Op::Add, {-0.017f, -0.045f, 0.084f}, {0.017f, -0.045f, 0.084f}, 0.006f, 0.01f, false));
  S.apply(piece(Op::Add, {-0.015f, -0.0555f, 0.082f}, {0.015f, -0.0555f, 0.082f}, 0.0062f, 0.01f, false));
  S.apply(piece(Op::Carve, {-0.019f, -0.0502f, 0.092f}, {0.019f, -0.0502f, 0.092f}, 0.0022f, 0.0015f, false));
  S.apply(piece(Op::Add, {0.08f, 0.012f, -0.008f}, {0.082f, -0.024f, -0.002f}, 0.0105f, 0.008f, M));
  S.apply(ball(Op::Carve, {0.091f, -0.004f, -0.002f}, 0.0062f, 0.003f, M));
  const V3 front{0, 0, -1}, side{-1, 0, 0};
  for (int pass = 0; pass < 2; ++pass) {
    S.stroke(brush(Op::Smooth, 0.016f, 0.8f, M),
             {{0.02f, 0.05f, 0.1f}, {0.05f, 0.0f, 0.1f}, {0.045f, -0.06f, 0.1f}, {0.0f, -0.08f, 0.1f}}, front);
    S.stroke(brush(Op::Smooth, 0.02f, 0.8f, M), {{0.1f, 0.06f, 0.0f}, {0.1f, -0.03f, 0.03f}, {0.1f, -0.08f, 0.0f}},
             side);
    S.stroke(brush(Op::Smooth, 0.02f, 0.8f, M), {{0.03f, -0.07f, 0.1f}, {0.0f, -0.11f, 0.1f}}, front);
  }
  S.stroke(brush(Op::Add, 0.007f, 0.6f, M), {{0.012f, 0.042f, 0.1f}, {0.03f, 0.045f, 0.1f}, {0.05f, 0.038f, 0.1f}},
           front);
  S.stroke(brush(Op::Add, 0.012f, 0.6f, M), {{0.035f, -0.005f, 0.1f}, {0.055f, -0.012f, 0.1f}}, front);
  S.stroke(brush(Op::Carve, 0.0045f, 0.6f, M),
           {{0.013f, -0.024f, 0.1f}, {0.024f, -0.04f, 0.1f}, {0.026f, -0.055f, 0.1f}}, front);
  S.stroke(brush(Op::Carve, 0.003f, 0.5f, M), {{0.02f, 0.026f, 0.1f}, {0.031f, 0.029f, 0.1f}, {0.042f, 0.026f, 0.1f}},
           front);
  S.stroke(brush(Op::Smooth, 0.01f, 0.5f, false), {{0.0f, -0.07f, 0.1f}, {0.0f, -0.08f, 0.1f}}, front);
  S.stroke(brush(Op::Smooth, 0.008f, 0.4f, false), {{0.02f, -0.05f, 0.1f}, {-0.02f, -0.05f, 0.1f}}, front);
}

// The proof's random strokes over the head: a fixed seed and its own generator (the same list on any compiler)
void random_strokes(Sculpt& S, int count) {
  uint64_t st = 0x9E3779B97F4A7C15ull;
  auto rnd = [&]() {
    st = st * 6364136223846793005ull + 1442695040888963407ull;
    return float((st >> 40) & 0xFFFFFF) / float(0xFFFFFF);
  };
  for (int i = 0; i < count; ++i) {
    const float az = (rnd() * 2 - 1) * 3.1f, el = (rnd() * 2 - 1) * 0.9f;
    const V3 dir = unit({-std::sin(az) * std::cos(el), -std::sin(el), -std::cos(az) * std::cos(el)});
    const V3 c = sub({0, -0.01f, 0}, mul(dir, 0.13f));
    const V3 t = unit({dir.z, 0.3f * (rnd() - 0.5f), -dir.x});
    const float L = 0.01f + 0.03f * rnd();
    const float r = 0.003f + 0.012f * rnd();
    const float u = rnd();
    const Op op = u < 0.35f ? Op::Add : u < 0.55f ? Op::Carve : u < 0.75f ? Op::Smooth : u < 0.85f ? Op::Flatten
                : u < 0.93f ? Op::Pull : Op::Crease;
    // (the brush's fields read in the proof's order: strength, then mirror)
    const float strength = 0.3f + 0.4f * rnd();
    const bool mirror = rnd() < 0.3f;
    S.stroke(brush(op, r, strength, mirror), {sub(c, mul(t, L * 0.5f)), add(c, mul(t, L * 0.5f))}, dir);
  }
}

}  // namespace

BenchResult bench(int nstrokes, int threads) {
  BenchResult r;
  r.strokes = nstrokes;
  tbb::task_arena arena(threads > 0 ? threads : tbb::task_arena::automatic);
  r.threads = arena.max_concurrency();
  arena.execute([&] {
    // the clay sculpted live (dabs shown, each stroke then applied as one unit), its steps kept
    std::vector<Step> pieces;
    std::vector<std::vector<Step>> head, strokes;
    {
      Volume v(kVoxel);
      Sculpt S{v, {}, {}};
      sculpt_head(S);
      pieces = std::move(S.pieces);
      head = std::move(S.strokes);
      S.strokes.clear();
      const auto t0 = std::chrono::steady_clock::now();
      random_strokes(S, nstrokes);
      r.liveMs = ms_since(t0);
      strokes = std::move(S.strokes);
      r.live = v.hash();
    }
    for (const auto& s : strokes) r.dabs += s.size();
    // the head replayed (untimed), then the strokes: one after another, and together
    auto head_clay = [&](Volume& v) {
      for (const Step& p : pieces) v.apply(p);
      for (const auto& s : head) v.apply_stroke(s);
    };
    {
      Volume v(kVoxel);
      head_clay(v);
      const auto t0 = std::chrono::steady_clock::now();
      for (const auto& s : strokes) v.apply_stroke(s);
      r.serialMs = ms_since(t0);
      r.serial = v.hash();
    }
    {
      Volume v(kVoxel);
      head_clay(v);
      const ReplayStats st = replay_strokes(v, strokes);
      r.parallelMs = st.ms;
      r.chain = st.chain;
      r.parallel = v.hash();
    }
  });
  return r;
}

}  // namespace r3d::clay
