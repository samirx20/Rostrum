// P-Clay proof: surface nets mesher for one block (see mesh.h). Throwaway proof code.
//
// One vertex per cell that a surface edge touches, made lazily the first time an owned quad uses it, so the
// output has no unused vertices. Inside = value < 0 everywhere (an exact 0 counts as outside).
// A vertex depends only on its cell's 8 corners and the cell's global index, computed in one fixed order, so
// neighbouring blocks give the same floats for a shared cell (keep /fp:precise; /fp:fast may reorder).
#include "mesh.h"

#include <cmath>
#include <cstring>
#include <utility>
#ifdef _MSC_VER
#include <intrin.h>
#endif

namespace clay {

namespace {

constexpr int kCells = kDense - 1;  // cells per axis in the dense array: [-1, kBlock) relative to block min
constexpr int kCellCount = kCells * kCells * kCells;
constexpr int kSY = kDense;            // dense stride in y
constexpr int kSZ = kDense * kDense;   // dense stride in z

// Cell corners: bit 0 = +x, bit 1 = +y, bit 2 = +z. The 12 edges as corner pairs, in a fixed order.
constexpr int kEdges[12][2] = {{0, 1}, {2, 3}, {4, 5}, {6, 7}, {0, 2}, {1, 3},
                               {4, 6}, {5, 7}, {0, 4}, {1, 5}, {2, 6}, {3, 7}};

inline int ctz64(uint64_t v) {
#ifdef _MSC_VER
  unsigned long i;
  _BitScanForward64(&i, v);
  return int(i);
#else
  return __builtin_ctzll(v);
#endif
}

struct Mesher {
  const float* d;
  const float* wide;  // kWide^3, origin one voxel before d's, or null
  float voxel;
  int ox, oy, oz;    // global voxel index of dense sample 0
  int32_t* cellVert; // kCellCount, -1 = no vertex yet
  BlockMesh* out;
  std::vector<int32_t>* touched;  // cells given a vertex, to reset afterwards

  int32_t vertex(int cx, int cy, int cz) {
    const int32_t cell = cx + kCells * (cy + kCells * cz);
    int32_t& slot = cellVert[cell];
    if (slot >= 0) return slot;
    touched->push_back(cell);

    const float* b = d + cx + kSY * cy + kSZ * cz;
    const float c[8] = {b[0],       b[1],           b[kSY],           b[kSY + 1],
                        b[kSZ],     b[kSZ + 1],     b[kSZ + kSY],     b[kSZ + kSY + 1]};

    float sx = 0.f, sy = 0.f, sz = 0.f;
    int n = 0;
    for (const auto& e : kEdges) {
      const float a = c[e[0]], bb = c[e[1]];
      if ((a < 0.f) == (bb < 0.f)) continue;
      const float t = a / (a - bb);  // a - bb != 0: exactly one of them is < 0
      const int i = e[0], j = e[1];
      sx += float(i & 1) + t * float((j & 1) - (i & 1));
      sy += float((i >> 1) & 1) + t * float(((j >> 1) & 1) - ((i >> 1) & 1));
      sz += float((i >> 2) & 1) + t * float(((j >> 2) & 1) - ((i >> 2) & 1));
      ++n;
    }
    // n > 0: the cell is only asked for around a surface edge, which is one of its own edges.
    const float inv = 1.f / float(n);
    const float u = sx * inv, v = sy * inv, w = sz * inv;

    // Trilinear gradient at (u, v, w); increasing value = outward.
    auto gradient = [&c](float u, float v, float w, float g[3]) {
      const float u0 = 1.f - u, v0 = 1.f - v, w0 = 1.f - w;
      g[0] = v0 * w0 * (c[1] - c[0]) + v * w0 * (c[3] - c[2]) + v0 * w * (c[5] - c[4]) + v * w * (c[7] - c[6]);
      g[1] = u0 * w0 * (c[2] - c[0]) + u * w0 * (c[3] - c[1]) + u0 * w * (c[6] - c[4]) + u * w * (c[7] - c[5]);
      g[2] = u0 * v0 * (c[4] - c[0]) + u * v0 * (c[5] - c[1]) + u0 * v * (c[6] - c[2]) + u * v * (c[7] - c[3]);
    };
    float g[3];
    if (wide) {
      // central differences at the 8 corners (wide index = dense index + 1), blended trilinearly
      constexpr int WY = kWide, WZ = kWide * kWide;
      const float u0 = 1.f - u, v0 = 1.f - v, w0 = 1.f - w;
      g[0] = g[1] = g[2] = 0.f;
      for (int k = 0; k < 8; ++k) {
        const int ix = cx + (k & 1) + 1, iy = cy + ((k >> 1) & 1) + 1, iz = cz + ((k >> 2) & 1) + 1;
        const float* q = wide + ix + WY * iy + WZ * iz;
        const float wt = ((k & 1) ? u : u0) * (((k >> 1) & 1) ? v : v0) * (((k >> 2) & 1) ? w : w0);
        g[0] += wt * (q[1] - q[-1]);
        g[1] += wt * (q[WY] - q[-WY]);
        g[2] += wt * (q[WZ] - q[-WZ]);
      }
    } else {
      gradient(u, v, w, g);
    }
    float len2 = g[0] * g[0] + g[1] * g[1] + g[2] * g[2];
    if (!(len2 > 1e-30f)) {  // saddle at the vertex: fall back to the cell's mean gradient
      gradient(0.5f, 0.5f, 0.5f, g);
      len2 = g[0] * g[0] + g[1] * g[1] + g[2] * g[2];
    }
    if (!(len2 > 1e-30f)) { g[0] = 0.f; g[1] = 0.f; g[2] = 1.f; len2 = 1.f; }
    const float il = 1.f / std::sqrt(len2);

    slot = int32_t(out->points.size() / 3);
    out->points.push_back((float(ox + cx) + u) * voxel);
    out->points.push_back((float(oy + cy) + v) * voxel);
    out->points.push_back((float(oz + cz) + w) * voxel);
    out->normals.push_back(g[0] * il);
    out->normals.push_back(g[1] * il);
    out->normals.push_back(g[2] * il);
    return slot;
  }

  float dist2(int32_t a, int32_t b) const {
    const float* p = out->points.data();
    const float dx = p[3 * a] - p[3 * b], dy = p[3 * a + 1] - p[3 * b + 1], dz = p[3 * a + 2] - p[3 * b + 2];
    return dx * dx + dy * dy + dz * dz;
  }

  // Cells around the edge in the order c00, c10, c11, c01 of the edge's (u, v) plane, u x v = edge axis:
  // counter-clockwise seen from +axis. `outPlus`: the outside lies at the edge's far end.
  void quad(int32_t a, int32_t b, int32_t c, int32_t e, bool outPlus) {
    if (!outPlus) std::swap(b, e);  // reverse the loop
    std::vector<int32_t>& ix = out->indices;
    const size_t n = ix.size();
    ix.resize(n + 6);
    int32_t* t = ix.data() + n;
    if (dist2(a, c) <= dist2(b, e)) {
      t[0] = a; t[1] = b; t[2] = c; t[3] = a; t[4] = c; t[5] = e;
    } else {
      t[0] = b; t[1] = c; t[2] = e; t[3] = b; t[4] = e; t[5] = a;
    }
  }
};

}  // namespace

void mesh_block(const float* dense, const float* wide, const BlockKey& key, float voxel, BlockMesh& out) {
  out.points.clear();
  out.normals.clear();
  out.indices.clear();

  // Inside bits per dense row (bit x = sample x < 0); the edge scan then only visits surface edges.
  static_assert(kDense <= 64, "a dense row must fit one 64-bit mask");
  uint64_t rows[kDense][kDense];  // [z][y]
  uint64_t any = 0, all = ~uint64_t(0);
  for (int z = 0; z < kDense; ++z) {
    for (int y = 0; y < kDense; ++y) {
      const float* r = dense + kSY * y + kSZ * z;
      uint64_t mask = 0;
      for (int x = 0; x < kDense; ++x) mask |= uint64_t(r[x] < 0.f) << x;
      rows[z][y] = mask;
      any |= mask;
      all &= mask;
    }
  }
  constexpr uint64_t kFull = (uint64_t(1) << kDense) - 1;
  if (any == 0 || all == kFull) return;

  // Cell -> vertex slots, reset after use (only the touched ones) instead of clearing all 33^3 each call.
  thread_local struct Slots {
    int32_t v[kCellCount];
    Slots() { std::memset(v, 0xff, sizeof(v)); }
  } slots;
  thread_local std::vector<int32_t> touched;
  touched.clear();

  Mesher m{dense, wide, voxel, key.x * kBlock - 1, key.y * kBlock - 1, key.z * kBlock - 1, slots.v, &out, &touched};

  // Owned edges start at relative voxels [0, kBlock), i.e. dense [1, kBlock].
  constexpr uint64_t kOwned = ((uint64_t(1) << kBlock) - 1) << 1;
  for (int z = 1; z <= kBlock; ++z) {
    for (int y = 1; y <= kBlock; ++y) {
      const uint64_t r = rows[z][y];
      const uint64_t ex = (r ^ (r >> 1)) & kOwned;
      const uint64_t ey = (r ^ rows[z][y + 1]) & kOwned;
      const uint64_t ez = (r ^ rows[z + 1][y]) & kOwned;
      uint64_t todo = ex | ey | ez;
      while (todo) {
        const int x = ctz64(todo);
        const uint64_t bit = uint64_t(1) << x;
        todo &= todo - 1;
        const bool in = (r & bit) != 0;
        if (ex & bit) {  // +x: (u, v) = (y, z)
          m.quad(m.vertex(x, y - 1, z - 1), m.vertex(x, y, z - 1), m.vertex(x, y, z), m.vertex(x, y - 1, z), in);
        }
        if (ey & bit) {  // +y: (u, v) = (z, x)
          m.quad(m.vertex(x - 1, y, z - 1), m.vertex(x - 1, y, z), m.vertex(x, y, z), m.vertex(x, y, z - 1), in);
        }
        if (ez & bit) {  // +z: (u, v) = (x, y)
          m.quad(m.vertex(x - 1, y - 1, z), m.vertex(x, y - 1, z), m.vertex(x, y, z), m.vertex(x - 1, y, z), in);
        }
      }
    }
  }
  for (int32_t c : touched) slots.v[c] = -1;
}

void append(BlockMesh& whole, const BlockMesh& b) {
  const int32_t base = int32_t(whole.points.size() / 3);
  whole.points.insert(whole.points.end(), b.points.begin(), b.points.end());
  whole.normals.insert(whole.normals.end(), b.normals.begin(), b.normals.end());
  for (int32_t i : b.indices) whole.indices.push_back(i + base);
}

}  // namespace clay

#ifdef CLAY_MESH_SELFTEST
// Self-check: mesh shapes across 2x2x2 blocks, weld by exact position, require a closed, consistently wound,
// outward surface. cl /O2 /EHsc /std:c++17 /DCLAY_MESH_SELFTEST mesh.cpp
#include <array>
#include <chrono>
#include <cstdio>
#include <functional>
#include <map>
#include <utility>

namespace {

using Field = std::function<float(float, float, float)>;  // in voxel units

bool check(const char* name, const Field& f, double expectVolume) {
  using namespace clay;
  std::vector<float> dense(kDense * kDense * kDense);
  BlockMesh whole, b;
  std::vector<std::vector<float>> denses;
  std::vector<BlockKey> keys;
  for (int bz = 0; bz < 2; ++bz)
    for (int by = 0; by < 2; ++by)
      for (int bx = 0; bx < 2; ++bx) {
        BlockKey k{bx, by, bz};
        for (int z = 0; z < kDense; ++z)
          for (int y = 0; y < kDense; ++y)
            for (int x = 0; x < kDense; ++x)
              dense[x + kDense * (y + kDense * z)] =
                  f(float(bx * kBlock - 1 + x), float(by * kBlock - 1 + y), float(bz * kBlock - 1 + z));
        mesh_block(dense.data(), nullptr, k, 1.f, b);
        // no unreferenced vertices
        std::vector<char> used(b.points.size() / 3, 0);
        for (int32_t i : b.indices) used[i] = 1;
        for (char u : used)
          if (!u) { std::printf("%s: unreferenced vertex\n", name); return false; }
        append(whole, b);
        denses.push_back(dense);
        keys.push_back(k);
      }

  // weld by exact position; normals of welded vertices must match exactly too
  std::map<std::array<float, 3>, int> weld;
  std::vector<int> id(whole.points.size() / 3);
  std::vector<std::array<float, 3>> wn;
  for (size_t i = 0; i < id.size(); ++i) {
    std::array<float, 3> p{whole.points[3 * i], whole.points[3 * i + 1], whole.points[3 * i + 2]};
    std::array<float, 3> n{whole.normals[3 * i], whole.normals[3 * i + 1], whole.normals[3 * i + 2]};
    auto it = weld.emplace(p, int(weld.size()));
    if (it.second) wn.push_back(n);
    else if (wn[it.first->second] != n) { std::printf("%s: seam normals differ\n", name); return false; }
    id[i] = it.first->second;
  }

  std::map<std::pair<int, int>, int> directed;
  double volume = 0.0;
  for (size_t t = 0; t < whole.indices.size(); t += 3) {
    const int a = id[whole.indices[t]], b2 = id[whole.indices[t + 1]], c = id[whole.indices[t + 2]];
    if (a == b2 || b2 == c || c == a) { std::printf("%s: degenerate triangle\n", name); return false; }
    ++directed[{a, b2}]; ++directed[{b2, c}]; ++directed[{c, a}];
    const float* P = whole.points.data();
    const int ia = whole.indices[t], ib = whole.indices[t + 1], ic = whole.indices[t + 2];
    const double ax = P[3 * ia], ay = P[3 * ia + 1], az = P[3 * ia + 2];
    const double bx = P[3 * ib], by = P[3 * ib + 1], bz = P[3 * ib + 2];
    const double cx = P[3 * ic], cy = P[3 * ic + 1], cz = P[3 * ic + 2];
    volume += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6.0;
  }
  // closed and consistently wound: every directed edge once, its reverse once
  for (const auto& e : directed) {
    auto r = directed.find({e.first.second, e.first.first});
    if (e.second != 1 || r == directed.end() || r->second != 1) {
      std::printf("%s: open or non-manifold edge %d-%d\n", name, e.first.first, e.first.second);
      return false;
    }
  }
  // normals outward: the field grows along them (checked with a small step)
  int bad = 0;
  for (size_t i = 0; i < whole.points.size() / 3; ++i) {
    const float* p = &whole.points[3 * i];
    const float* n = &whole.normals[3 * i];
    if (f(p[0] + 0.25f * n[0], p[1] + 0.25f * n[1], p[2] + 0.25f * n[2]) <=
        f(p[0] - 0.25f * n[0], p[1] - 0.25f * n[1], p[2] - 0.25f * n[2]))
      ++bad;
  }

  // timing: re-mesh the 8 blocks
  const int reps = 200;
  size_t sink = 0;
  auto t0 = std::chrono::steady_clock::now();
  for (int r = 0; r < reps; ++r)
    for (size_t k = 0; k < keys.size(); ++k) {
      mesh_block(denses[k].data(), nullptr, keys[k], 1.f, b);
      sink += b.indices.size();
    }
  auto t1 = std::chrono::steady_clock::now();
  const double ms = std::chrono::duration<double, std::milli>(t1 - t0).count() / double(reps * keys.size());

  std::printf("%s: %zu triangles, %zu welded vertices, closed yes, volume %.1f (expected %.1f), "
              "inward normals %d, %.4f ms per block (%zu)\n",
              name, whole.triangles(), weld.size(), volume, expectVolume, bad, ms, sink % 7);
  return volume > 0.0 && bad == 0;
}

}  // namespace

int main() {
  const double pi = 3.14159265358979;
  bool ok = true;
  ok &= check("sphere off-lattice", [](float x, float y, float z) {
    const float dx = x - 31.7f, dy = y - 32.3f, dz = z - 32.1f;
    return std::sqrt(dx * dx + dy * dy + dz * dz) - 20.4f;
  }, 4.0 / 3.0 * pi * 20.4 * 20.4 * 20.4);
  ok &= check("sphere on-lattice (exact zeros)", [](float x, float y, float z) {
    const float dx = x - 32.f, dy = y - 32.f, dz = z - 32.f;
    return std::sqrt(dx * dx + dy * dy + dz * dz) - 20.f;
  }, 4.0 / 3.0 * pi * 20.0 * 20.0 * 20.0);
  ok &= check("torus", [](float x, float y, float z) {
    const float dx = x - 32.f, dy = y - 31.5f, dz = z - 32.2f;
    const float q = std::sqrt(dx * dx + dz * dz) - 18.f;
    return std::sqrt(q * q + dy * dy) - 7.f;
  }, 2.0 * pi * pi * 18.0 * 7.0 * 7.0);
  std::printf(ok ? "PASS\n" : "FAIL\n");
  return ok ? 0 : 1;
}
#endif
