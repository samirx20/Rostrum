// P-Clay proof: sculpt with steps, time a dab to its picture, rebuild the whole surface, replay 2,000 strokes with a
// stable hash, memory; Storm pictures and Cycles Finals. Throwaway proof code.
//
//   clay_proof.exe <out folder> bench   [--samples 256] [--no-final] [--strokes 2000] [--budget 8]
//   clay_proof.exe <out folder> look    [--samples 256]   close-ups: smoothness, a Crease line, joins
//   clay_proof.exe <out folder> compare [--samples 256]   the agent's head and character, the mouse head
//   clay_proof.exe <out folder> check                     every head step must leave a closed surface
#include <windows.h>
#include <psapi.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

#include <tbb/global_control.h>
#include <tbb/parallel_for.h>

#include "clay.h"
#include "session.h"
#include "view.h"
#ifdef CLAY_SCULPTS
#include "sculpts.h"
#endif

using namespace clay;

// draw on the discrete GPU (the RTX), not the integrated one: without these, the hidden GL context (and Storm) ran on
// the AMD Radeon and every frame cost ~40 ms (as apps/3d/core/src/main.cpp does)
extern "C" {
__declspec(dllexport) DWORD NvOptimusEnablement = 1;
__declspec(dllexport) int AmdPowerXpressRequestHighPerformance = 1;
}

namespace {

using Clock = std::chrono::steady_clock;
double ms_since(Clock::time_point t0) { return std::chrono::duration<double, std::milli>(Clock::now() - t0).count(); }

double process_cpu_ms() {
  FILETIME c, e, k, u;
  GetProcessTimes(GetCurrentProcess(), &c, &e, &k, &u);
  auto t = [](FILETIME f) { return (double(f.dwHighDateTime) * 4294967296.0 + f.dwLowDateTime) / 1e4; };
  return t(k) + t(u);
}

size_t peak_ws() {
  PROCESS_MEMORY_COUNTERS pmc{};
  GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof pmc);
  return pmc.PeakWorkingSetSize;
}
size_t now_ws() {
  PROCESS_MEMORY_COUNTERS pmc{};
  GetProcessMemoryInfo(GetCurrentProcess(), &pmc, sizeof pmc);
  return pmc.WorkingSetSize;
}

double pct(std::vector<double> v, double p) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  return v[std::min(v.size() - 1, size_t(p * (v.size() - 1) + 0.5))];
}

std::string hex(uint64_t h) {
  char b[32];
  std::snprintf(b, sizeof b, "%016llx", (unsigned long long)h);
  return b;
}

struct Json {
  std::ostringstream s;
  bool first = true;
  void num(const std::string& k, double v) { sep(); s << "\"" << k << "\": " << v; }
  void str(const std::string& k, const std::string& v) { sep(); s << "\"" << k << "\": \"" << v << "\""; }
  void sep() { s << (first ? "{\n  " : ",\n  "); first = false; }
  std::string done() { return s.str() + "\n}\n"; }
};

// Part 1's scripted head (kept as the bench's clay, so the numbers compare with part 1's).
void sculpt_head(Session& S) {
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
    S.stroke({Op::Smooth, 0.016f, 0.8f, M},
             {{0.02f, 0.05f, 0.1f}, {0.05f, 0.0f, 0.1f}, {0.045f, -0.06f, 0.1f}, {0.0f, -0.08f, 0.1f}}, front);
    S.stroke({Op::Smooth, 0.02f, 0.8f, M}, {{0.1f, 0.06f, 0.0f}, {0.1f, -0.03f, 0.03f}, {0.1f, -0.08f, 0.0f}}, side);
    S.stroke({Op::Smooth, 0.02f, 0.8f, M}, {{0.03f, -0.07f, 0.1f}, {0.0f, -0.11f, 0.1f}}, front);
  }
  S.stroke({Op::Add, 0.007f, 0.6f, M}, {{0.012f, 0.042f, 0.1f}, {0.03f, 0.045f, 0.1f}, {0.05f, 0.038f, 0.1f}}, front);
  S.stroke({Op::Add, 0.012f, 0.6f, M}, {{0.035f, -0.005f, 0.1f}, {0.055f, -0.012f, 0.1f}}, front);
  S.stroke({Op::Carve, 0.0045f, 0.6f, M}, {{0.013f, -0.024f, 0.1f}, {0.024f, -0.04f, 0.1f}, {0.026f, -0.055f, 0.1f}},
           front);
  S.stroke({Op::Carve, 0.003f, 0.5f, M}, {{0.02f, 0.026f, 0.1f}, {0.031f, 0.029f, 0.1f}, {0.042f, 0.026f, 0.1f}}, front);
  S.stroke({Op::Smooth, 0.01f, 0.5f, false}, {{0.0f, -0.07f, 0.1f}, {0.0f, -0.08f, 0.1f}}, front);
  S.stroke({Op::Smooth, 0.008f, 0.4f, false}, {{0.02f, -0.05f, 0.1f}, {-0.02f, -0.05f, 0.1f}}, front);
}

// 2,000 strokes over the head, from a fixed seed (own generator: the same list on any compiler), every brush
void random_strokes(Session& S, int count) {
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
    S.stroke({op, r, 0.3f + 0.4f * rnd(), rnd() < 0.3f}, {sub(c, mul(t, L * 0.5f)), add(c, mul(t, L * 0.5f))}, dir);
  }
}

bool write_steps(const std::string& path, const std::vector<Step>& steps) {
  std::ofstream f(path);
  for (const Step& s : steps) f << to_line(s) << "\n";
  return bool(f);
}

std::vector<Step> read_steps(const std::string& path) {
  std::vector<Step> v;
  std::ifstream f(path);
  std::string line;
  while (std::getline(f, line)) {
    Step s;
    if (!from_line(line, s)) throw std::runtime_error("bad step line in " + path + ": " + line);
    v.push_back(s);
  }
  return v;
}

// The live view: changed blocks wait in a queue and go to Storm nearest the brush first, at most `budget` per frame,
// so a big dab shows where the brush is at once and the rest follows over the next frames.
struct Live {
  Clay* clay;
  View* view;
  size_t budget = 8;
  std::set<BlockKey> pending;
  struct Frame {
    double meshMs = 0, usdMs = 0, renderMs = 0;
    size_t sent = 0, left = 0;
  };
  Frame frame(V3 focus) {
    Frame f;
    for (const BlockKey& k : clay->take_dirty()) pending.insert(k);
    std::vector<BlockKey> keys(pending.begin(), pending.end());
    const float bw = kBlock * clay->voxel();
    auto d2 = [&](const BlockKey& k) {
      const float x = (k.x + 0.5f) * bw - focus.x, y = (k.y + 0.5f) * bw - focus.y, z = (k.z + 0.5f) * bw - focus.z;
      return x * x + y * y + z * z;
    };
    std::sort(keys.begin(), keys.end(), [&](const BlockKey& a, const BlockKey& b) { return d2(a) < d2(b); });
    if (keys.size() > budget) keys.resize(budget);
    std::vector<BlockMesh> meshes(keys.size());
    auto t0 = Clock::now();
    tbb::parallel_for(size_t(0), keys.size(), [&](size_t i) { clay->mesh(keys[i], meshes[i]); });
    f.meshMs = ms_since(t0);
    t0 = Clock::now();
    view->begin_changes();
    for (size_t i = 0; i < keys.size(); ++i) {
      view->set_block(keys[i], meshes[i]);
      pending.erase(keys[i]);
    }
    view->end_changes();
    f.usdMs = ms_since(t0);
    f.renderMs = view->render_storm();
    f.sent = keys.size();
    f.left = pending.size();
    return f;
  }
};

// --check: the whole surface must be closed: no edge (welded by exact position) used by one triangle only. An edge
// used by 4 is where two sheets of clay touch along a voxel edge (surface nets makes a pinch there): not a hole.
size_t open_edges(const Clay& clay) {
  std::vector<std::pair<BlockKey, BlockMesh>> all;
  clay.mesh_all(all);
  std::map<std::tuple<float, float, float>, int> ids;
  std::map<std::pair<int, int>, int> edges;
  for (auto& [k, m] : all) {
    std::vector<int> id(m.points.size() / 3);
    for (size_t i = 0; i < id.size(); ++i)
      id[i] = ids.emplace(std::make_tuple(m.points[3 * i], m.points[3 * i + 1], m.points[3 * i + 2]), int(ids.size()))
                  .first->second;
    for (size_t t = 0; t < m.indices.size(); t += 3)
      for (int e = 0; e < 3; ++e) {
        int a = id[m.indices[t + e]], b = id[m.indices[t + (e + 1) % 3]];
        if (a > b) std::swap(a, b);
        ++edges[{a, b}];
      }
  }
  size_t open = 0;
  std::vector<std::tuple<float, float, float>> pos(ids.size());
  for (auto& [p, i] : ids) pos[i] = p;
  for (auto& [e, n] : edges) {
    if (n != 1) continue;  // a hole; an edge of 4 is two sheets touching (a pinch), counted apart
    if (open++ < 4) {
      const auto [x, y, z] = pos[e.first];
      std::printf("  open edge (used %d times) near voxel (%.2f %.2f %.2f)\n", n, x / clay.voxel(), y / clay.voxel(),
                  z / clay.voxel());
    }
  }
  return open;
}

BlockMesh whole_of(const Clay& c) {
  std::vector<std::pair<BlockKey, BlockMesh>> all;
  c.mesh_all(all);
  BlockMesh w;
  for (auto& [k, m] : all) append(w, m);
  return w;
}

void show_all(Clay& c, View& view) {  // every block of the clay into the (empty) view
  std::vector<std::pair<BlockKey, BlockMesh>> all;
  c.mesh_all(all);
  c.take_dirty();
  view.begin_changes();
  for (auto& [k, m] : all) view.set_block(k, m);
  view.end_changes();
}

void clear_view(View& view, const std::set<BlockKey>& shown) {
  view.begin_changes();
  for (const BlockKey& k : shown) view.set_block(k, BlockMesh{});
  view.end_changes();
}

Camera cam_of(V3 eye, V3 target, float fov) {
  Camera c;
  c.eye[0] = eye.x, c.eye[1] = eye.y, c.eye[2] = eye.z;
  c.target[0] = target.x, c.target[1] = target.y, c.target[2] = target.z;
  c.fovYDeg = fov;
  return c;
}

const Camera kHeadCam = cam_of({0.2f, 0.035f, 0.4f}, {0, -0.015f, 0.02f}, 30);

// ---------------------------------------------------------------------------------------------------------------
int bench(const std::string& out, float voxel, int samples, bool final, int nstrokes, size_t budget, Json& J) {
  std::vector<Step> headSteps;
  uint64_t headHash = 0;
  View view(1280, 720);
  {
    // 1. the head, sculpted by script (strokes go through the live path: dabs shown, then the stroke as one unit)
    Session S(voxel);
    auto t0 = Clock::now();
    sculpt_head(S);
    J.num("head_steps", double(S.steps.size()));
    J.num("head_sculpt_ms", ms_since(t0));
    J.num("head_active_voxels", double(S.clay.active_voxels()));
    J.num("head_grid_mb", S.clay.memory_bytes() / 1048576.0);
    headHash = S.clay.hash();
    headSteps = S.steps;
    J.str("head_hash", hex(headHash));
    if (!write_steps(out + "/head_steps.txt", S.steps)) throw std::runtime_error("could not write head_steps.txt");
    std::printf("head: %zu steps, %.0f ms, hash %s, peak %.0f MB\n", S.steps.size(), ms_since(t0),
                hex(headHash).c_str(), peak_ws() / 1048576.0);
    J.num("peak_after_head_mb", peak_ws() / 1048576.0);

    // 2. the whole-surface rebuild (what a Cycles render gets)
    t0 = Clock::now();
    BlockMesh whole = whole_of(S.clay);
    J.num("rebuild_ms", ms_since(t0));
    J.num("rebuild_triangles", double(whole.triangles()));

    // 3. Storm: all blocks in, then dabs one by one, each to its first picture
    view.set_camera(kHeadCam);
    t0 = Clock::now();
    show_all(S.clay, view);
    J.num("storm_all_blocks_usd_ms", ms_since(t0));
    for (int i = 0; i < 3; ++i) view.render_storm();
    std::vector<double> st;
    for (int i = 0; i < 10; ++i) st.push_back(view.render_storm());
    J.num("storm_static_frame_p50_ms", pct(st, 0.5));
    view.save_storm_png(out + "/head_storm.png");
    if (final) J.num("final_seconds", view.render_cycles(whole, samples, out + "/head_final.png"));

    Live live{&S.clay, &view, budget};
    const float ext = 0.331f;  // the clay's largest extent (part 1: measured from the surface)
    const struct {
      const char* name;
      float r;
    } sizes[] = {{"small", 0.004f}, {"medium", 0.012f}, {"quarter", ext / 8.0f}};
    const struct {
      const char* name;
      Op op;
    } ops[] = {{"add", Op::Add},         {"carve", Op::Carve}, {"smooth", Op::Smooth},
               {"flatten", Op::Flatten}, {"pull", Op::Pull},   {"crease", Op::Crease}};
    for (const auto& sz : sizes)
      for (const auto& op : ops)
        for (int mirror = 0; mirror < 2; ++mirror) {
          if (mirror && sz.r < 0.01f) continue;
          std::vector<double> total, apply, mesh, usd, render, settle, endMs, frames, cpu;
          const int N = 24;
          for (int i = 0; i < N; ++i) {
            // dabs around the cranium, aimed at its centre, each its own stroke
            const float az = -1.2f + 2.4f * i / (N - 1);
            const V3 dir = unit({-std::sin(az), -0.35f, -std::cos(az)});
            V3 on, nrm;
            if (!S.clay.cast(sub({0, 0.03f, 0}, mul(dir, 0.2f)), dir, 0.4f, on, nrm)) continue;
            Step s;
            s.kind = Kind::Stamp;
            s.op = op.op;
            s.a = on;
            s.n = nrm;
            s.radius = sz.r;
            s.strength = 0.5f;
            s.mirror = mirror != 0;
            s.stroke = 1;
            const V3 tang = unit(cross(nrm, {0, 1, 0}));
            if (op.op == Op::Pull) s.b = mul(tang, sz.r * 0.25f);
            if (op.op == Op::Crease) s.b = tang;
            const double c0 = process_cpu_ms();
            const auto a0 = Clock::now();
            S.clay.begin_stroke();
            S.clay.dab(s);
            const double ta = ms_since(a0);
            const Live::Frame f = live.frame(on);
            total.push_back(ms_since(a0));
            cpu.push_back(process_cpu_ms() - c0);
            apply.push_back(ta);
            mesh.push_back(f.meshMs);
            usd.push_back(f.usdMs);
            render.push_back(f.renderMs);
            // the stroke ends: the dab is applied as a unit (what replay does); the rest of the blocks follow
            const auto e0 = Clock::now();
            S.clay.end_stroke({s});
            endMs.push_back(ms_since(e0));
            int n = 1;
            const auto s0 = Clock::now();
            while (true) {
              const Live::Frame g = live.frame(on);
              ++n;
              if (!g.left) break;
            }
            settle.push_back(ta + f.meshMs + f.usdMs + f.renderMs + ms_since(s0) + endMs.back());
            frames.push_back(n);
          }
          const std::string key = std::string("dab_") + sz.name + "_" + op.name + (mirror ? "_mirror" : "");
          J.num(key + "_radius", sz.r);
          J.num(key + "_first_picture_p50_ms", pct(total, 0.5));
          J.num(key + "_first_picture_p95_ms", pct(total, 0.95));
          J.num(key + "_step_p50_ms", pct(apply, 0.5));
          J.num(key + "_mesh_p50_ms", pct(mesh, 0.5));
          J.num(key + "_usd_p50_ms", pct(usd, 0.5));
          J.num(key + "_render_p50_ms", pct(render, 0.5));
          J.num(key + "_cpu_p50_ms", pct(cpu, 0.5));
          J.num(key + "_stroke_end_p50_ms", pct(endMs, 0.5));
          J.num(key + "_all_shown_p50_ms", pct(settle, 0.5));
          J.num(key + "_frames_p50", pct(frames, 0.5));
          std::printf("%-26s r=%.4f first picture p50 %5.1f p95 %5.1f ms (step %.1f mesh %.1f usd %.1f render %.1f) "
                      "| stroke end %.1f, all shown %.1f ms in %.0f frames\n",
                      key.c_str(), sz.r, pct(total, 0.5), pct(total, 0.95), pct(apply, 0.5), pct(mesh, 0.5),
                      pct(usd, 0.5), pct(render, 0.5), pct(endMs, 0.5), pct(settle, 0.5), pct(frames, 0.5));
        }
    view.save_storm_png(out + "/after_bench_storm.png");
    J.num("peak_after_bench_mb", peak_ws() / 1048576.0);
    // replay: the head's steps into new clay, same hash
    t0 = Clock::now();
    {
      Clay c(voxel);
      replay(c, read_steps(out + "/head_steps.txt"));
      J.num("replay_head_ms", ms_since(t0));
      J.num("replay_head_same_hash", c.hash() == headHash ? 1 : 0);
    }
  }  // the bench's clay is gone

  // 4. 2,000 strokes on the head, drawn live (dab previews, each stroke settled as one unit), then replayed
  std::vector<Step> all;
  uint64_t live = 0;
  {
    Session R(voxel);
    replay(R.clay, headSteps);
    R.steps = headSteps;
    auto t0 = Clock::now();
    random_strokes(R, nstrokes);
    J.num("strokes", nstrokes);
    J.num("strokes_dabs", double(R.steps.size() - headSteps.size()));
    J.num("strokes_live_ms", ms_since(t0));
    live = R.clay.hash();
    all = R.steps;
    if (!write_steps(out + "/strokes_steps.txt", all)) throw std::runtime_error("could not write strokes_steps.txt");
  }
  {
    auto tf = Clock::now();
    const auto steps = read_steps(out + "/strokes_steps.txt");
    J.num("replay_read_file_ms", ms_since(tf));
    const std::vector<Step> head(steps.begin(), steps.begin() + headSteps.size());
    const std::vector<Step> strokes(steps.begin() + headSteps.size(), steps.end());
    Clay c(voxel);
    replay(c, head);
    auto t0 = Clock::now();
    const double c0 = process_cpu_ms();
    replay(c, strokes);
    J.num("replay_strokes_ms", ms_since(t0));
    J.num("replay_strokes_cpu_ms", process_cpu_ms() - c0);
    const uint64_t replayed = c.hash();
    J.num("replay_strokes_same_hash", replayed == live ? 1 : 0);
    J.str("strokes_hash", hex(replayed));
    std::printf("replay %d strokes (%zu dabs): %.0f ms, same hash %d\n", nstrokes, strokes.size(), ms_since(t0),
                int(replayed == live));
    if (!c.save(out + "/cache.vdb")) throw std::runtime_error("could not write cache.vdb");
    t0 = Clock::now();
    Clay cached(voxel);
    if (!cached.load(out + "/cache.vdb")) throw std::runtime_error("could not read cache.vdb");
    J.num("replay_cache_ms", ms_since(t0));
    J.num("replay_cache_same_hash", cached.hash() == replayed ? 1 : 0);
    J.num("strokes_grid_mb", c.memory_bytes() / 1048576.0);
    if (final) {
      view.set_camera(kHeadCam);
      view.render_cycles(whole_of(c), samples, out + "/strokes2000_final.png");
    }
  }
  return 0;
}

// ---------------------------------------------------------------------------------------------------------------
// close-ups: a plain sphere; the same after many smooth dabs; a Crease line; a join of two pieces, smoothed
int look(const std::string& out, float voxel, int samples, Json& J) {
  View view(1280, 720);
  auto shoot = [&](Clay& c, const Camera& cam, const std::string& name) {
    view.set_camera(cam);
    show_all(c, view);
    view.render_storm();
    view.save_storm_png(out + "/" + name + "_storm.png");
    const BlockMesh w = whole_of(c);
    J.num(name + "_final_s", view.render_cycles(w, samples, out + "/" + name + "_final.png"));
    std::set<BlockKey> shown;
    for (const BlockKey& k : c.all_blocks()) shown.insert(k);
    clear_view(view, shown);
  };
  const Camera close = cam_of({0.03f, 0.03f, 0.12f}, {0, 0.0f, 0.05f}, 30);  // ~7 cm wide at the surface
  {
    Session S(voxel);
    S.apply(ball(Op::Add, {0, 0, 0}, 0.06f, 0, false));
    shoot(S.clay, close, "look_sphere");
    for (int pass = 0; pass < 4; ++pass)
      S.stroke({Op::Smooth, 0.012f, 0.8f, false}, {{-0.03f, 0.03f, 0.1f}, {0.03f, 0.0f, 0.1f}, {-0.03f, -0.03f, 0.1f}},
               {0, 0, -1});
    shoot(S.clay, close, "look_sphere_smoothed");
    for (int i = 0; i < 4; ++i)
      S.stroke({Op::Add, 0.01f, 0.6f, false}, {{-0.03f, 0.02f - 0.012f * i, 0.1f}, {0.03f, 0.02f - 0.012f * i, 0.1f}},
               {0, 0, -1});
    shoot(S.clay, close, "look_sphere_added");
  }
  {
    Session S(voxel);  // a Crease line and a Flatten patch and a Pull on a sphere
    S.apply(ball(Op::Add, {0, 0, 0}, 0.06f, 0, false));
    S.stroke({Op::Crease, 0.006f, 0.8f, false}, {{-0.03f, 0.015f, 0.1f}, {0.0f, 0.02f, 0.1f}, {0.03f, 0.012f, 0.1f}},
             {0, 0, -1});
    S.stroke({Op::Crease, 0.006f, 0.8f, false}, {{-0.03f, 0.0f, 0.1f}, {0.0f, 0.004f, 0.1f}, {0.03f, -0.002f, 0.1f}},
             {0, 0, -1});
    for (int i = 0; i < 3; ++i)
      S.stroke({Op::Flatten, 0.012f, 0.8f, false}, {{-0.025f, -0.025f, 0.1f}, {0.0f, -0.03f, 0.1f}}, {0, 0, -1});
    S.stroke({Op::Pull, 0.01f, 0.8f, false}, {{0.015f, -0.02f, 0.1f}, {0.03f, -0.035f, 0.1f}}, {0, 0, -1});
    shoot(S.clay, close, "look_brushes");
  }
  {
    Session S(voxel);  // a join: an arm into a body, blended, then smoothed along the join
    S.apply(piece(Op::Add, {0, -0.04f, 0}, {0, 0.04f, 0}, 0.045f, 0, false));
    S.apply(piece(Op::Add, {0.03f, 0.02f, 0.01f}, {0.09f, -0.02f, 0.03f}, 0.014f, 0.012f, false));
    S.stroke({Op::Smooth, 0.01f, 0.7f, false}, {{0.045f, 0.035f, 0.1f}, {0.05f, 0.0f, 0.1f}, {0.045f, -0.015f, 0.1f}},
             {0, 0, -1});
    shoot(S.clay, cam_of({0.12f, 0.03f, 0.16f}, {0.05f, 0.005f, 0.02f}, 30), "look_join");
  }
  return 0;
}

// ---------------------------------------------------------------------------------------------------------------
#ifdef CLAY_SCULPTS
int compare(const std::string& out, float voxel, int samples, Json& J) {
  View view(1280, 720);
  auto shoot = [&](Session& S, const Camera& cam, const std::string& name) {
    view.set_camera(cam);
    show_all(S.clay, view);
    view.render_storm();
    view.save_storm_png(out + "/" + name + "_storm.png");
    view.render_cycles(whole_of(S.clay), samples, out + "/" + name + "_final.png");
    std::set<BlockKey> shown;
    for (const BlockKey& k : S.clay.all_blocks()) shown.insert(k);
    clear_view(view, shown);
  };
  auto run = [&](const char* name, auto sculpt) {
    Session S(voxel);
    const auto t0 = Clock::now();
    sculpt(S);
    J.num(std::string(name) + "_ms", ms_since(t0));
    J.num(std::string(name) + "_steps", double(S.steps.size()));
    write_steps(out + "/" + name + "_steps.txt", S.steps);
    std::printf("%s: %zu steps, %.0f ms\n", name, S.steps.size(), ms_since(t0));
    return S.steps;
  };
  {
    Session S(voxel);
    replay(S.clay, run("agent_head", [](Session& s) { sculpt_agent_head(s); }));
    shoot(S, head_three_quarter(), "agent_head_34");
    shoot(S, head_front(), "agent_head_front");
  }
  {
    Session S(voxel);
    replay(S.clay, run("agent_character", [](Session& s) { sculpt_agent_character(s); }));
    shoot(S, character_three_quarter(), "agent_character_34");
  }
  {
    Session S(voxel);
    replay(S.clay, run("mouse_head", [](Session& s) { sculpt_mouse_head(s, 1280, 720); }));
    shoot(S, head_three_quarter(), "mouse_head_34");
    shoot(S, head_front(), "mouse_head_front");
  }
  return 0;
}
#endif

}  // namespace

int main(int argc, char** argv) {
  if (argc < 3) {
    std::fprintf(stderr, "usage: clay_proof <out folder> bench|look|compare|check [--samples n] [--no-final] "
                         "[--strokes n] [--budget blocks]\n");
    return 2;
  }
  std::setvbuf(stdout, nullptr, _IONBF, 0);
  const std::string out = argv[1], mode = argv[2];
  float voxel = 0.000625f;
  int samples = 256, nstrokes = 2000;
  size_t budget = 8;
  bool final = true;
  for (int i = 3; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--voxel" && i + 1 < argc) voxel = std::stof(argv[++i]);
    else if (a == "--samples" && i + 1 < argc) samples = std::stoi(argv[++i]);
    else if (a == "--strokes" && i + 1 < argc) nstrokes = std::stoi(argv[++i]);
    else if (a == "--budget" && i + 1 < argc) budget = size_t(std::stoi(argv[++i]));
    else if (a == "--no-final") final = false;
  }
  CreateDirectoryA(out.c_str(), nullptr);
  std::unique_ptr<tbb::global_control> threads;  // CLAY_THREADS=n: at most n threads (to see what the parallel loops buy)
  if (const char* t = std::getenv("CLAY_THREADS"))
    threads = std::make_unique<tbb::global_control>(tbb::global_control::max_allowed_parallelism, size_t(std::atoi(t)));
  Json J;
  J.num("voxel", voxel);
  int rc = 0;
  try {
    if (mode == "check") {
      Session S(voxel);
      S.afterUnit = [](Session& s) {
        const size_t open = open_edges(s.clay);
        std::printf("unit ending at step %zu: open edges %zu\n", s.steps.size() - 1, open);
        if (open) std::exit(3);
      };
      sculpt_head(S);
      return 0;
    } else if (mode == "replay") {  // replay <out> replay <steps file>: pieces and strokes timed apart
      const auto steps = read_steps(argv[3]);
      std::vector<Step> pieces, strokes;
      for (const Step& s : steps) (s.kind == Kind::Piece ? pieces : strokes).push_back(s);
      Clay c(voxel);
      auto t0 = Clock::now();
      replay(c, pieces);
      const double tp = ms_since(t0);
      t0 = Clock::now();
      const double c0 = process_cpu_ms();
      replay(c, strokes);
      std::printf("pieces %zu: %.0f ms; dabs %zu: %.0f ms wall, %.0f ms cpu (%.2f ms a dab)\n", pieces.size(), tp,
                  strokes.size(), ms_since(t0), process_cpu_ms() - c0, ms_since(t0) / std::max<size_t>(1, strokes.size()));
      return 0;
    } else if (mode == "bench") {
      rc = bench(out, voxel, samples, final, nstrokes, budget, J);
    } else if (mode == "look") {
      rc = look(out, voxel, samples, J);
#ifdef CLAY_SCULPTS
    } else if (mode == "compare") {
      rc = compare(out, voxel, samples, J);
#endif
    } else {
      throw std::runtime_error("unknown mode " + mode);
    }
  } catch (const std::exception& e) {
    std::fprintf(stderr, "FAILED: %s\n", e.what());
    rc = 1;
  }
  J.num("peak_working_set_mb", peak_ws() / 1048576.0);
  J.num("working_set_end_mb", now_ws() / 1048576.0);
  std::ofstream(out + "/numbers_" + mode + ".json") << J.done();
  std::printf("%s", J.done().c_str());
  return rc;
}
