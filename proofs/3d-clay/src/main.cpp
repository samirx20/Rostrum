// P-Clay proof, part 1: sculpt a head with steps, time stamp -> picture, the whole-surface rebuild, replay of 2,000
// strokes with a stable hash, memory; Storm pictures and a Cycles Final. Throwaway proof code.
//
//   clay_proof.exe <out folder> [--voxel 0.000625] [--samples 256] [--no-final] [--strokes 2000]
//
// Writes into <out folder>: numbers.json, head_steps.txt, strokes_steps.txt, cache.vdb, *.png, clay_blocks.usda.
#include <windows.h>
#include <psapi.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <tuple>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include <tbb/parallel_for.h>

#include "clay.h"
#include "view.h"

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

V3 add(V3 a, V3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
V3 sub(V3 a, V3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
V3 mul(V3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
float len(V3 a) { return std::sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }
V3 unit(V3 a) { return mul(a, 1.0f / std::max(1e-12f, len(a))); }

double pct(std::vector<double> v, double p) {
  if (v.empty()) return 0;
  std::sort(v.begin(), v.end());
  return v[std::min(v.size() - 1, size_t(p * (v.size() - 1) + 0.5))];
}

struct Json {
  std::ostringstream s;
  bool first = true;
  void num(const std::string& k, double v) { sep(); s << "\"" << k << "\": " << v; }
  void str(const std::string& k, const std::string& v) { sep(); s << "\"" << k << "\": \"" << v << "\""; }
  void sep() { s << (first ? "{\n  " : ",\n  "); first = false; }
  std::string done() { return s.str() + "\n}\n"; }
};

// The sculpting session: the clay, the steps it took, and (optionally) the live Storm view kept in step.
struct Session {
  Clay clay;
  std::vector<Step> steps;
  View* view = nullptr;
  explicit Session(float voxel) : clay(voxel) {}

  void (*after)(Session&) = nullptr;  // --check: called after every step
  void apply(const Step& s) {
    clay.apply(s);
    steps.push_back(s);
    if (after) after(*this);
  }
  // one brush stroke: the polyline resampled every 0.3 radius; each dab lands where a ray along `dir` meets the clay
  // as it is now (like a pen on the screen), so later dabs ride on earlier ones
  int stroke(Op op, const std::vector<V3>& pts, V3 dir, float radius, float strength, bool mirror) {
    dir = unit(dir);
    int n = 0;
    const float spacing = std::max(radius * 0.3f, clay.voxel());
    for (size_t i = 0; i + 1 < pts.size(); ++i) {
      const V3 seg = sub(pts[i + 1], pts[i]);
      const int k = std::max(1, int(len(seg) / spacing));
      for (int j = 0; j < k + (i + 2 == pts.size() ? 1 : 0); ++j) {
        const V3 p = add(pts[i], mul(seg, float(j) / k));
        V3 on, nrm;
        if (!clay.cast(sub(p, mul(dir, 0.08f)), dir, 0.16f, on, nrm)) continue;
        Step s;
        s.kind = Kind::Stamp;
        s.op = op;
        s.a = on;
        s.n = nrm;
        s.radius = radius;
        s.strength = strength;
        s.mirror = mirror;
        apply(s);
        ++n;
      }
    }
    return n;
  }
};

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

// The scripted sculpt ("the agent"): a head, Y up, facing +Z, symmetric in X. Units: metres-ish, ~0.25 tall.
void sculpt_head(Session& S) {
  const bool M = true;
  // big forms
  S.apply(ball(Op::Add, {0, 0.035f, -0.01f}, 0.082f, 0, false));                          // cranium
  S.apply(piece(Op::Add, {0, 0.03f, -0.03f}, {0, 0.01f, -0.06f}, 0.07f, 0.03f, false));     // back of the skull
  S.apply(piece(Op::Add, {0, 0.01f, 0.03f}, {0, -0.045f, 0.035f}, 0.052f, 0.035f, false));  // face mass
  S.apply(piece(Op::Add, {0.044f, -0.03f, -0.005f}, {0.018f, -0.083f, 0.045f}, 0.02f, 0.025f, M));  // jaw
  S.apply(ball(Op::Add, {0, -0.088f, 0.058f}, 0.019f, 0.02f, false));                       // chin
  S.apply(piece(Op::Add, {0, -0.05f, -0.02f}, {0, -0.17f, -0.035f}, 0.043f, 0.025f, false)); // neck
  S.apply(ball(Op::Add, {0.048f, -0.008f, 0.052f}, 0.02f, 0.022f, M));                       // cheekbones
  // eyes: sockets carved, eyeballs set in, brow ridge
  S.apply(ball(Op::Carve, {0.031f, 0.016f, 0.086f}, 0.019f, 0.012f, M));
  S.apply(ball(Op::Add, {0.031f, 0.013f, 0.062f}, 0.012f, 0.003f, M));
  S.apply(piece(Op::Add, {0.019f, 0.021f, 0.071f}, {0.043f, 0.021f, 0.066f}, 0.0045f, 0.004f, M));  // upper lids
  S.apply(piece(Op::Add, {0.021f, 0.004f, 0.071f}, {0.041f, 0.005f, 0.067f}, 0.0035f, 0.004f, M));  // lower lids
  S.apply(piece(Op::Add, {0.01f, 0.036f, 0.079f}, {0.05f, 0.036f, 0.064f}, 0.0095f, 0.012f, M));
  // nose
  S.apply(piece(Op::Add, {0, 0.026f, 0.081f}, {0, -0.014f, 0.098f}, 0.0085f, 0.012f, false));
  S.apply(ball(Op::Add, {0, -0.016f, 0.097f}, 0.0105f, 0.006f, false));
  S.apply(ball(Op::Add, {0.011f, -0.02f, 0.087f}, 0.0068f, 0.006f, M));
  S.apply(ball(Op::Carve, {0.0062f, -0.0275f, 0.0905f}, 0.0028f, 0.002f, M));  // nostrils
  // mouth
  S.apply(piece(Op::Add, {-0.017f, -0.045f, 0.084f}, {0.017f, -0.045f, 0.084f}, 0.006f, 0.01f, false));
  S.apply(piece(Op::Add, {-0.015f, -0.0555f, 0.082f}, {0.015f, -0.0555f, 0.082f}, 0.0062f, 0.01f, false));
  S.apply(piece(Op::Carve, {-0.019f, -0.0502f, 0.092f}, {0.019f, -0.0502f, 0.092f}, 0.0022f, 0.0015f, false));
  // ears
  S.apply(piece(Op::Add, {0.08f, 0.012f, -0.008f}, {0.082f, -0.024f, -0.002f}, 0.0105f, 0.008f, M));
  S.apply(ball(Op::Carve, {0.091f, -0.004f, -0.002f}, 0.0062f, 0.003f, M));

  // brush work: smooth the joins, build the brow and cheeks, carve the folds
  const V3 front{0, 0, -1}, side{-1, 0, 0};
  for (int pass = 0; pass < 2; ++pass) {
    S.stroke(Op::Smooth, {{0.02f, 0.05f, 0.1f}, {0.05f, 0.0f, 0.1f}, {0.045f, -0.06f, 0.1f}, {0.0f, -0.08f, 0.1f}},
             front, 0.016f, 0.8f, M);
    S.stroke(Op::Smooth, {{0.1f, 0.06f, 0.0f}, {0.1f, -0.03f, 0.03f}, {0.1f, -0.08f, 0.0f}}, side, 0.02f, 0.8f, M);
    S.stroke(Op::Smooth, {{0.03f, -0.07f, 0.1f}, {0.0f, -0.11f, 0.1f}}, front, 0.02f, 0.8f, M);
  }
  S.stroke(Op::Add, {{0.012f, 0.042f, 0.1f}, {0.03f, 0.045f, 0.1f}, {0.05f, 0.038f, 0.1f}}, front, 0.007f, 0.6f, M);
  S.stroke(Op::Add, {{0.035f, -0.005f, 0.1f}, {0.055f, -0.012f, 0.1f}}, front, 0.012f, 0.6f, M);
  S.stroke(Op::Carve, {{0.013f, -0.024f, 0.1f}, {0.024f, -0.04f, 0.1f}, {0.026f, -0.055f, 0.1f}}, front, 0.0045f,
           0.6f, M);  // the folds from the nose to the mouth corners
  S.stroke(Op::Carve, {{0.02f, 0.026f, 0.1f}, {0.031f, 0.029f, 0.1f}, {0.042f, 0.026f, 0.1f}}, front, 0.003f, 0.5f,
           M);  // upper eyelid crease
  S.stroke(Op::Smooth, {{0.0f, -0.07f, 0.1f}, {0.0f, -0.08f, 0.1f}}, front, 0.01f, 0.5f, false);
  S.stroke(Op::Smooth, {{0.02f, -0.05f, 0.1f}, {-0.02f, -0.05f, 0.1f}}, front, 0.008f, 0.4f, false);  // the lips
}

// 2,000 strokes over the head, from a fixed seed (own generator: the same list on any compiler)
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
    const Op op = u < 0.5f ? Op::Add : u < 0.75f ? Op::Carve : Op::Smooth;
    S.stroke(op, {sub(c, mul(t, L * 0.5f)), add(c, mul(t, L * 0.5f))}, dir, r, 0.3f + 0.4f * rnd(), rnd() < 0.3f);
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

// send the dirty blocks to the view (meshing in parallel); returns {mesh ms, usd ms, blocks}
struct Sent {
  double meshMs = 0, usdMs = 0;
  size_t blocks = 0, tris = 0;
};
Sent send_dirty(Clay& clay, View& view) {
  Sent r;
  const auto dirty = clay.take_dirty();
  std::vector<BlockKey> keys(dirty.begin(), dirty.end());
  std::vector<BlockMesh> meshes(keys.size());
  auto t0 = Clock::now();
  tbb::parallel_for(size_t(0), keys.size(), [&](size_t i) { clay.mesh(keys[i], meshes[i]); });
  r.meshMs = ms_since(t0);
  t0 = Clock::now();
  view.begin_changes();
  for (size_t i = 0; i < keys.size(); ++i) {
    view.set_block(keys[i], meshes[i]);
    r.tris += meshes[i].triangles();
  }
  view.end_changes();
  r.usdMs = ms_since(t0);
  r.blocks = keys.size();
  return r;
}

// --check: the whole surface after a step must be closed (every edge, welded by exact position, used twice)
size_t open_edges(const Clay& clay) {
  std::vector<std::pair<BlockKey, BlockMesh>> all;
  clay.mesh_all(all);  // exactly what the view and the Final get
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
  std::map<int, size_t> byCount;
  for (auto& [e, n] : edges) {
    if (n == 2) continue;
    ++byCount[n];
    if (open++ < 6) {
      const auto [x, y, z] = pos[e.first];
      std::printf("  open edge used %d times near voxel (%.2f %.2f %.2f)\n", n, x / clay.voxel(), y / clay.voxel(),
                  z / clay.voxel());
    }
  }
  for (auto& [n, c] : byCount) std::printf("  edges used %d times: %zu\n", n, c);
  return open;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(stderr, "usage: clay_proof <out folder> [--voxel v] [--samples n] [--no-final] [--strokes n]\n");
    return 2;
  }
  const std::string out = argv[1];
  float voxel = 0.000625f;
  int samples = 256, nstrokes = 2000;
  bool final = true;
  for (int i = 2; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--voxel" && i + 1 < argc) voxel = std::stof(argv[++i]);
    else if (a == "--samples" && i + 1 < argc) samples = std::stoi(argv[++i]);
    else if (a == "--strokes" && i + 1 < argc) nstrokes = std::stoi(argv[++i]);
    else if (a == "--no-final") final = false;
  }
  CreateDirectoryA(out.c_str(), nullptr);
  if (argc > 2 && std::string(argv[2]) == "--check") {  // find the first head step that leaves the surface open
    Session S(voxel);
    S.after = [](Session& s) {
      const size_t open = open_edges(s.clay);
      std::printf("step %zu %s: open edges %zu\n", s.steps.size() - 1, to_line(s.steps.back()).c_str(), open);
      if (open) {
        std::exit(3);
      }
    };
    sculpt_head(S);
    return 0;
  }
  Json J;
  J.num("voxel", voxel);
  try {
    // 1. the head, sculpted by script
    Session S(voxel);
    auto t0 = Clock::now();
    sculpt_head(S);
    J.num("head_steps", double(S.steps.size()));
    J.num("head_sculpt_ms", ms_since(t0));
    J.num("head_active_voxels", double(S.clay.active_voxels()));
    J.num("head_grid_mb", S.clay.memory_bytes() / 1048576.0);
    const uint64_t headHash = S.clay.hash();
    char hx[32];
    std::snprintf(hx, sizeof hx, "%016llx", (unsigned long long)headHash);
    J.str("head_hash", hx);
    if (!write_steps(out + "/head_steps.txt", S.steps)) throw std::runtime_error("could not write head_steps.txt");
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("head: %zu steps, %.0f ms, hash %s\n", S.steps.size(), ms_since(t0), hx);

    // 2. the whole-surface rebuild (what a Cycles render gets)
    std::vector<std::pair<BlockKey, BlockMesh>> all;
    t0 = Clock::now();
    const double cpu0 = process_cpu_ms();
    S.clay.mesh_all(all);
    BlockMesh whole;
    for (auto& [k, m] : all) append(whole, m);
    J.num("rebuild_ms", ms_since(t0));
    J.num("rebuild_cpu_ms", process_cpu_ms() - cpu0);
    J.num("rebuild_blocks", double(all.size()));
    J.num("rebuild_triangles", double(whole.triangles()));
    std::printf("rebuild: %zu blocks, %zu triangles, %.0f ms\n", all.size(), whole.triangles(), ms_since(t0));

    // 3. Storm: all blocks in, then stamps one by one, each to a finished picture
    View view(1280, 720);
    Camera cam;
    const float eye[3] = {0.2f, 0.035f, 0.4f}, tgt[3] = {0, -0.015f, 0.02f};
    std::copy(eye, eye + 3, cam.eye);
    std::copy(tgt, tgt + 3, cam.target);
    cam.fovYDeg = 30;
    view.set_camera(cam);
    S.clay.take_dirty();
    t0 = Clock::now();
    view.begin_changes();
    for (auto& [k, m] : all) view.set_block(k, m);
    view.end_changes();
    J.num("storm_all_blocks_usd_ms", ms_since(t0));
    t0 = Clock::now();
    view.render_storm();
    J.num("storm_first_frame_ms", ms_since(t0));
    for (int i = 0; i < 3; ++i) view.render_storm();
    {
      std::vector<double> st;  // a frame with nothing changed: the floor under every stamp's time
      for (int i = 0; i < 10; ++i) st.push_back(view.render_storm());
      J.num("storm_static_frame_p50_ms", pct(st, 0.5));
      std::printf("storm static frame p50 %.1f ms\n", pct(st, 0.5));
    }
    view.save_storm_png(out + "/head_storm.png");
    view.export_usda(out + "/clay_blocks.usda");

    // brush sizes: small, medium, and a quarter of the clay across (the budget's largest)
    float ext = 0;  // the clay's largest extent, from the surface's bounds
    {
      float mn[3] = {1e9f, 1e9f, 1e9f}, mx[3] = {-1e9f, -1e9f, -1e9f};
      for (size_t i = 0; i < whole.points.size(); i += 3)
        for (int a = 0; a < 3; ++a) {
          mn[a] = std::min(mn[a], whole.points[i + a]);
          mx[a] = std::max(mx[a], whole.points[i + a]);
        }
      ext = std::max({mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]});
    }
    J.num("clay_extent", ext);
    const struct {
      const char* name;
      float r;
    } sizes[] = {{"small", 0.004f}, {"medium", 0.012f}, {"quarter", ext / 8.0f}};
    const struct {
      const char* name;
      Op op;
    } ops[] = {{"add", Op::Add}, {"carve", Op::Carve}, {"smooth", Op::Smooth}};
    for (const auto& sz : sizes) {
      for (const auto& op : ops) {
        for (int mirror = 0; mirror < 2; ++mirror) {
          if (mirror && sz.r < 0.01f) continue;  // mirrored: medium and quarter only
          std::vector<double> total, apply, mesh, usd, render, cpu;
          double blocks = 0;
          const int N = 30;
          for (int i = 0; i < N; ++i) {
            // dabs around the cranium, aimed at its centre, each a separate stroke so they don't pile up
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
            const double c0 = process_cpu_ms();
            const auto a0 = Clock::now();
            S.apply(s);
            const double ta = ms_since(a0);
            const Sent sent = send_dirty(S.clay, view);
            const double tr = view.render_storm();
            total.push_back(ms_since(a0));
            apply.push_back(ta);
            mesh.push_back(sent.meshMs);
            usd.push_back(sent.usdMs);
            render.push_back(tr);
            cpu.push_back(process_cpu_ms() - c0);
            blocks += double(sent.blocks);
          }
          const std::string key = std::string("stamp_") + sz.name + "_" + op.name + (mirror ? "_mirror" : "");
          J.num(key + "_radius", sz.r);
          J.num(key + "_n", double(total.size()));
          J.num(key + "_total_p50_ms", pct(total, 0.5));
          J.num(key + "_total_p95_ms", pct(total, 0.95));
          J.num(key + "_apply_p50_ms", pct(apply, 0.5));
          J.num(key + "_mesh_p50_ms", pct(mesh, 0.5));
          J.num(key + "_usd_p50_ms", pct(usd, 0.5));
          J.num(key + "_render_p50_ms", pct(render, 0.5));
          J.num(key + "_cpu_p50_ms", pct(cpu, 0.5));
          J.num(key + "_blocks_avg", total.empty() ? 0 : blocks / total.size());
          std::printf("%-28s r=%.4f  total p50 %.1f p95 %.1f ms (apply %.1f mesh %.1f usd %.1f render %.1f) blocks %.0f\n",
                      key.c_str(), sz.r, pct(total, 0.5), pct(total, 0.95), pct(apply, 0.5), pct(mesh, 0.5),
                      pct(usd, 0.5), pct(render, 0.5), total.empty() ? 0 : blocks / total.size());
        }
      }
    }
    view.save_storm_png(out + "/after_bench_storm.png");

    // 4. Final: a fresh head (without the bench dabs), whole surface rebuilt, Cycles
    if (final) {
      view.set_camera(cam);
      const double sec = view.render_cycles(whole, samples, out + "/head_final.png");
      J.num("final_seconds", sec);
      // one Final per run: a second Cycles engine after the first is gone crashes (part 2: keep one engine)
    }

    // 5. replay: the head's steps into new clay, same hash
    {
      const auto steps = read_steps(out + "/head_steps.txt");
      Clay c(voxel);
      t0 = Clock::now();
      for (const Step& s : steps) c.apply(s);
      J.num("replay_head_ms", ms_since(t0));
      J.num("replay_head_same_hash", c.hash() == headHash ? 1 : 0);
    }
    // 6. 2,000 strokes on the head, recorded, then replayed from the file into new clay
    {
      Session R(voxel);
      for (const Step& s : read_steps(out + "/head_steps.txt")) R.apply(s);
      const size_t before = R.steps.size();
      t0 = Clock::now();
      random_strokes(R, nstrokes);
      J.num("strokes", nstrokes);
      J.num("strokes_dabs", double(R.steps.size() - before));
      J.num("strokes_live_ms", ms_since(t0));
      const uint64_t live = R.clay.hash();
      if (!write_steps(out + "/strokes_steps.txt", R.steps)) throw std::runtime_error("could not write strokes_steps.txt");
      // the file read and the head's own steps are timed apart from the 2,000 strokes
      auto tf = Clock::now();
      const auto steps = read_steps(out + "/strokes_steps.txt");
      J.num("replay_read_file_ms", ms_since(tf));
      Clay c(voxel);
      tf = Clock::now();
      for (size_t i = 0; i < before; ++i) c.apply(steps[i]);
      J.num("replay_head_part_ms", ms_since(tf));
      t0 = Clock::now();
      const double c0 = process_cpu_ms();
      for (size_t i = before; i < steps.size(); ++i) c.apply(steps[i]);
      J.num("replay_strokes_ms", ms_since(t0));
      J.num("replay_strokes_cpu_ms", process_cpu_ms() - c0);
      const uint64_t replayed = c.hash();
      J.num("replay_strokes_same_hash", replayed == live ? 1 : 0);
      std::snprintf(hx, sizeof hx, "%016llx", (unsigned long long)replayed);
      J.str("strokes_hash", hx);
      std::printf("replay %d strokes (%zu dabs): %.0f ms, same hash %d\n", nstrokes, steps.size() - before,
                  ms_since(t0), int(replayed == live));
      // from the cache: the saved grid
      if (!c.save(out + "/cache.vdb")) throw std::runtime_error("could not write cache.vdb");
      t0 = Clock::now();
      Clay cached(voxel);
      if (!cached.load(out + "/cache.vdb")) throw std::runtime_error("could not read cache.vdb");
      J.num("replay_cache_ms", ms_since(t0));
      J.num("replay_cache_same_hash", cached.hash() == replayed ? 1 : 0);
      J.num("strokes_grid_mb", c.memory_bytes() / 1048576.0);
      // the surface after 2,000 strokes, rebuilt and shown
      std::vector<std::pair<BlockKey, BlockMesh>> all2;
      t0 = Clock::now();
      c.mesh_all(all2);
      J.num("strokes_rebuild_ms", ms_since(t0));
      BlockMesh whole2;
      for (auto& [k, m] : all2) append(whole2, m);
      J.num("strokes_rebuild_triangles", double(whole2.triangles()));
    }
    J.num("peak_working_set_mb", peak_ws() / 1048576.0);
    J.num("working_set_end_mb", now_ws() / 1048576.0);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "FAILED: %s\n", e.what());
    std::ofstream(out + "/numbers.json") << J.done();
    return 1;
  }
  std::ofstream(out + "/numbers.json") << J.done();
  std::printf("%s", J.done().c_str());
  return 0;
}
