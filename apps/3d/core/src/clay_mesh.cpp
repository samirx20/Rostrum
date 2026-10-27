// Clay: surface nets mesher for one block (clay_mesh.h). Moved from proofs/3d-clay (mesh.cpp).
//
// One vertex per cell that a surface edge touches, made lazily the first time an owned quad uses it, so the
// output has no unused vertices. Inside = value < 0 everywhere (an exact 0 counts as outside).
// A vertex depends only on its cell's 8 corners and the cell's global index, computed in one fixed order, so
// neighbouring blocks give the same floats for a shared cell (keep /fp:precise; /fp:fast may reorder).
#include "clay_mesh.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <unordered_map>
#include <utility>
#ifdef _MSC_VER
#include <intrin.h>
#endif

namespace r3d::clay {

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
  const float* mask;  // kDense^3, the same lattice as d's, or null
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
    float u = sx * inv, v = sy * inv, w = sz * inv;

    // Trilinear gradient at (u, v, w); increasing value = outward.
    auto gradient = [&c](float u, float v, float w, float g[3]) {
      const float u0 = 1.f - u, v0 = 1.f - v, w0 = 1.f - w;
      g[0] = v0 * w0 * (c[1] - c[0]) + v * w0 * (c[3] - c[2]) + v0 * w * (c[5] - c[4]) + v * w * (c[7] - c[6]);
      g[1] = u0 * w0 * (c[2] - c[0]) + u * w0 * (c[3] - c[1]) + u0 * w * (c[6] - c[4]) + u * w * (c[7] - c[5]);
      g[2] = u0 * v0 * (c[4] - c[0]) + u * v0 * (c[5] - c[1]) + u0 * v * (c[6] - c[2]) + u * v * (c[7] - c[3]);
    };
    // The mean of the crossings lies off the surface wherever it bends inside the cell, by up to a voxel, and in a
    // pattern that repeats with the lattice (terraces on gentle slopes). Two Newton steps put the vertex on the
    // cell's own (trilinear) zero surface, kept inside the cell; still from the cell's 8 corners only.
    constexpr bool kProject = true;
    for (int it = 0; kProject && it < 2; ++it) {
      const float u0 = 1.f - u, v0 = 1.f - v, w0 = 1.f - w;
      const float f = w0 * (v0 * (u0 * c[0] + u * c[1]) + v * (u0 * c[2] + u * c[3])) +
                      w * (v0 * (u0 * c[4] + u * c[5]) + v * (u0 * c[6] + u * c[7]));
      float gn[3];
      gradient(u, v, w, gn);
      const float l2 = gn[0] * gn[0] + gn[1] * gn[1] + gn[2] * gn[2];
      if (!(l2 > 1e-12f)) break;
      const float k = f / l2;
      u = std::min(1.f, std::max(0.f, u - k * gn[0]));
      v = std::min(1.f, std::max(0.f, v - k * gn[1]));
      w = std::min(1.f, std::max(0.f, w - k * gn[2]));
    }
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
    if (mask) {
      const float* q = mask + cx + kSY * cy + kSZ * cz;
      const float u0 = 1.f - u, v0 = 1.f - v, w0 = 1.f - w;
      out->mask.push_back(w0 * (v0 * (u0 * q[0] + u * q[1]) + v * (u0 * q[kSY] + u * q[kSY + 1])) +
                          w * (v0 * (u0 * q[kSZ] + u * q[kSZ + 1]) + v * (u0 * q[kSZ + kSY] + u * q[kSZ + kSY + 1])));
    }
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

void mesh_block(const float* dense, const float* wide, const BlockKey& key, float voxel, BlockMesh& out,
                const float* mask) {
  out.points.clear();
  out.normals.clear();
  out.indices.clear();
  out.mask.clear();

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

  Mesher m{dense, wide, mask, voxel, key.x * kBlock - 1, key.y * kBlock - 1, key.z * kBlock - 1, slots.v, &out, &touched};

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
  if (!b.mask.empty() || !whole.mask.empty()) {
    whole.mask.resize(size_t(base), 0.f);
    if (b.mask.empty()) whole.mask.resize(size_t(base) + b.points.size() / 3, 0.f);
    else whole.mask.insert(whole.mask.end(), b.mask.begin(), b.mask.end());
  }
  whole.points.insert(whole.points.end(), b.points.begin(), b.points.end());
  whole.normals.insert(whole.normals.end(), b.normals.begin(), b.normals.end());
  for (int32_t i : b.indices) whole.indices.push_back(i + base);
}

void add_skirts(BlockMesh& m, float depth) {
  // the edges used by one triangle only, each kept with the direction its triangle walks it (a -> b)
  std::unordered_map<uint64_t, int> uses;  // undirected edge -> uses, + 2 x (the triangle walks it low -> high)
  const size_t nt = m.triangles();
  uses.reserve(nt * 3);
  auto key = [](int32_t a, int32_t b) { return (uint64_t(uint32_t(std::min(a, b))) << 32) | uint32_t(std::max(a, b)); };
  for (size_t t = 0; t < nt; ++t)
    for (int e = 0; e < 3; ++e) {
      const int32_t a = m.indices[3 * t + e], b = m.indices[3 * t + (e + 1) % 3];
      int& u = uses[key(a, b)];
      u += 1 + (a < b ? 2 : 0);
    }
  std::unordered_map<int32_t, int32_t> below;  // a rim vertex -> its copy `depth` into the clay
  auto lowered = [&](int32_t v) {
    auto it = below.find(v);
    if (it != below.end()) return it->second;
    const int32_t c = int32_t(m.points.size() / 3);
    for (int i = 0; i < 3; ++i) m.points.push_back(m.points[3 * size_t(v) + i] - depth * m.normals[3 * size_t(v) + i]);
    for (int i = 0; i < 3; ++i) m.normals.push_back(m.normals[3 * size_t(v) + i]);
    if (!m.mask.empty()) m.mask.push_back(m.mask[size_t(v)]);
    below.emplace(v, c);
    return c;
  };
  std::vector<int32_t> add;
  for (const auto& kv : uses) {
    if ((kv.second & 1) == 0 || kv.second > 3) continue;  // used twice (or more): inside the patch
    const int32_t lo = int32_t(kv.first >> 32), hi = int32_t(kv.first & 0xffffffffu);
    const int32_t a = kv.second == 3 ? lo : hi, b = kv.second == 3 ? hi : lo;  // as its triangle walks it
    const int32_t a2 = lowered(a), b2 = lowered(b);
    // the wall under a -> b, facing away from the triangle (counter-clockwise seen from outside the patch)
    add.insert(add.end(), {a, a2, b2, a, b2, b});
  }
  m.indices.insert(m.indices.end(), add.begin(), add.end());
}

}  // namespace r3d::clay

