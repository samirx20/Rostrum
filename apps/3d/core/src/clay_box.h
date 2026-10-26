// Clay: the volume's internal helpers (only clay_volume*.cpp and clay_band.cpp include this). A step works on a box
// of the grid copied out chunk by chunk; the distances are re-levelled with a Jacobi upwind eikonal. Moved from
// proofs/3d-clay (clay.cpp), unchanged in what it computes.
#pragma once
#include <openvdb/openvdb.h>
#include <tbb/blocked_range.h>
#include <tbb/parallel_for.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <memory>
#include <vector>

#include "clay_step.h"

namespace r3d::clay::detail {

using openvdb::Coord;
using Tree = openvdb::FloatTree;
using Leaf = Tree::LeafNodeType;

constexpr float kDispCap = 2.0f;  // a stamp moves the surface at most this far (voxels) per dab

inline int floor_div(int a, int b) { return (a >= 0) ? a / b : -((-a + b - 1) / b); }
inline int floor8(int a) { return floor_div(a, 8) * 8; }
inline int ceil8(int a) { return -floor8(-a); }

inline int leaf_offset(int x, int y, int z) { return ((x & 7) << 6) | ((y & 7) << 3) | (z & 7); }

// A box of the grid seen as 8^3 chunks, stored chunk by chunk (512 floats each, x fastest inside a chunk), so a
// step's buffers only ever touch the chunks it lists: the rest of a big box is never written and costs no memory
// (the buffers are allocated without being cleared). lo is 8-aligned, sizes are multiples of 8.
struct Box {
  Coord lo;
  int nx = 0, ny = 0, nz = 0, cnx = 0, cny = 0, cnz = 0;
  size_t size() const { return size_t(chunks()) * 512; }
  int chunks() const { return cnx * cny * cnz; }
  size_t at(int x, int y, int z) const {
    return (size_t((z >> 3) * cny + (y >> 3)) * cnx + (x >> 3)) * 512 + (((z & 7) << 6) | ((y & 7) << 3) | (x & 7));
  }
  void corner(int ci, int& x, int& y, int& z) const {
    x = 8 * (ci % cnx);
    y = 8 * ((ci / cnx) % cny);
    z = 8 * (ci / (cnx * cny));
  }
  template <class F> void each(int ci, F&& f) const {  // f(x, y, z, index) over the chunk's voxels
    int x0, y0, z0;
    corner(ci, x0, y0, z0);
    size_t i = size_t(ci) * 512;
    for (int z = z0; z < z0 + 8; ++z)
      for (int y = y0; y < y0 + 8; ++y)
        for (int x = x0; x < x0 + 8; ++x, ++i) f(x, y, z, i);
  }
  void copy(int ci, const float* src, float* dst) const {
    std::memcpy(dst + size_t(ci) * 512, src + size_t(ci) * 512, 512 * sizeof(float));
  }
  // trilinear sample of `buf` at box-local voxel position (x, y, z), clamped into the box
  float sample(const float* buf, float x, float y, float z) const {
    x = std::min(std::max(x, 0.0f), float(nx) - 1.001f);
    y = std::min(std::max(y, 0.0f), float(ny) - 1.001f);
    z = std::min(std::max(z, 0.0f), float(nz) - 1.001f);
    const int ix = int(x), iy = int(y), iz = int(z);
    const float fx = x - ix, fy = y - iy, fz = z - iz;
    auto v = [&](int a, int b, int c) { return buf[at(ix + a, iy + b, iz + c)]; };
    const float c00 = v(0, 0, 0) + (v(1, 0, 0) - v(0, 0, 0)) * fx, c10 = v(0, 1, 0) + (v(1, 1, 0) - v(0, 1, 0)) * fx;
    const float c01 = v(0, 0, 1) + (v(1, 0, 1) - v(0, 0, 1)) * fx, c11 = v(0, 1, 1) + (v(1, 1, 1) - v(0, 1, 1)) * fx;
    const float c0 = c00 + (c10 - c00) * fy, c1 = c01 + (c11 - c01) * fy;
    return c0 + (c1 - c0) * fz;
  }
};

// a few chunks run on this thread: a parallel loop over them costs more in waking threads than it saves
template <class F> inline void par(const std::vector<int>& list, F&& f) {
  if (list.size() <= 12) {
    for (int ci : list) f(ci);
    return;
  }
  tbb::parallel_for(tbb::blocked_range<size_t>(0, list.size(), 4), [&](const tbb::blocked_range<size_t>& r) {
    for (size_t k = r.begin(); k < r.end(); ++k) f(list[k]);
  });
}

// flags dilated by r chunks (Chebyshev), separably
inline std::vector<uint8_t> dilate(const std::vector<uint8_t>& in, int nx, int ny, int nz, int r) {
  std::vector<uint8_t> a = in, b(in.size());
  const int n[3] = {nx, ny, nz};
  const ptrdiff_t st[3] = {1, ptrdiff_t(nx), ptrdiff_t(nx) * ny};
  for (int ax = 0; ax < 3; ++ax) {
    for (int z = 0; z < nz; ++z)
      for (int y = 0; y < ny; ++y)
        for (int x = 0; x < nx; ++x) {
          const int c[3] = {x, y, z};
          const ptrdiff_t i = x + st[1] * y + st[2] * z;
          uint8_t m = 0;
          for (int d = -r; d <= r && !m; ++d) {
            const int q = c[ax] + d;
            if (q >= 0 && q < n[ax]) m = a[i + d * st[ax]];
          }
          b[i] = m;
        }
    a.swap(b);
  }
  return a;
}

inline std::vector<int> listed(const std::vector<uint8_t>& f) {
  std::vector<int> l;
  for (int i = 0; i < int(f.size()); ++i)
    if (f[i]) l.push_back(i);
  return l;
}

// Copy voxels [lo, lo+n) of `tree` into `out` (x fastest), leaf by leaf; tiles and background as their value.
// `parallel` only from a caller that is not itself inside a parallel loop: a nested loop lets TBB run another of the
// caller's tasks on this thread while it waits, and that task would reuse this thread's buffers (a race that left
// holes at block seams, different on every run)
inline void read_region(const Tree& tree, const Coord& lo, int nx, int ny, int nz, float* out, bool parallel = false) {
  const int cx0 = floor8(lo.x()), cy0 = floor8(lo.y()), cz0 = floor8(lo.z());
  const int cx1 = floor8(lo.x() + nx - 1), cy1 = floor8(lo.y() + ny - 1), cz1 = floor8(lo.z() + nz - 1);
  const int ncx = (cx1 - cx0) / 8 + 1, ncy = (cy1 - cy0) / 8 + 1, ncz = (cz1 - cz0) / 8 + 1;
  const int chunks = ncx * ncy * ncz;
  auto body = [&](int ci) {
    const int ox = cx0 + 8 * (ci % ncx), oy = cy0 + 8 * ((ci / ncx) % ncy), oz = cz0 + 8 * (ci / (ncx * ncy));
    const int x0 = std::max(ox, lo.x()), x1 = std::min(ox + 8, lo.x() + nx);
    const int y0 = std::max(oy, lo.y()), y1 = std::min(oy + 8, lo.y() + ny);
    const int z0 = std::max(oz, lo.z()), z1 = std::min(oz + 8, lo.z() + nz);
    const Coord origin(ox, oy, oz);
    if (const Leaf* leaf = tree.probeConstLeaf(origin)) {
      const float* d = leaf->buffer().data();
      for (int z = z0; z < z1; ++z)
        for (int y = y0; y < y1; ++y) {
          float* row = out + (size_t(x0 - lo.x()) + size_t(nx) * (size_t(y - lo.y()) + size_t(ny) * (z - lo.z())));
          for (int x = x0; x < x1; ++x) *row++ = d[leaf_offset(x, y, z)];
        }
    } else {
      const float val = tree.getValue(origin);
      for (int z = z0; z < z1; ++z)
        for (int y = y0; y < y1; ++y) {
          float* row = out + (size_t(x0 - lo.x()) + size_t(nx) * (size_t(y - lo.y()) + size_t(ny) * (z - lo.z())));
          std::fill(row, row + (x1 - x0), val);
        }
    }
  };
  if (!parallel || chunks < 16) {
    for (int i = 0; i < chunks; ++i) body(i);
  } else {
    tbb::parallel_for(tbb::blocked_range<int>(0, chunks, 8), [&](const tbb::blocked_range<int>& r) {
      for (int i = r.begin(); i < r.end(); ++i) body(i);
    });
  }
}

inline float sgn(float v) { return v < 0 ? -1.0f : 1.0f; }

// Godunov upwind update of |u| from the per-axis smallest neighbours (unit spacing)
inline float eikonal(float a, float b, float c) {
  if (a > b) std::swap(a, b);
  if (b > c) std::swap(b, c);
  if (a > b) std::swap(a, b);
  float u = a + 1.0f;
  if (u > b) {
    const float d = a - b;
    u = 0.5f * (a + b + std::sqrt(std::max(0.0f, 2.0f - d * d)));
    if (u > c) {
      const float s = a + b + c, q = a * a + b * b + c * c;
      u = (s + std::sqrt(std::max(0.0f, s * s - 3.0f * (q - 1.0f)))) / 3.0f;
    }
  }
  return u;
}

// Re-level: voxels with fixed[i] keep their value; the others get the distance from the fixed ones (Jacobi upwind
// eikonal), up to `width`, keeping their sign. Unknown voxels of `init` start at the width; only `work` is updated
// (work is inside ext, and ext reaches one chunk past work, so every neighbour read is a filled voxel; the rest of
// ext is read as it is).
inline void relevel(const Box& b, float*& v, float*& next, const uint8_t* fixed, float width, const std::vector<int>& init,
             const std::vector<int>& ext, const std::vector<int>& work) {
  par(init, [&](int ci) {
    b.each(ci, [&](int, int, int, size_t i) {
      if (!fixed[i]) v[i] = sgn(v[i]) * width;
    });
  });
  par(ext, [&](int ci) { b.copy(ci, v, next); });
  if (work.empty()) return;
  const int passes = int(std::ceil(width)) + 1;
  for (int pass = 0; pass < passes; ++pass) {
    const float* cur = v;
    float* out = next;
    par(work, [&](int ci) {
      b.each(ci, [&](int x, int y, int z, size_t i) {
        if (fixed[i]) return;
        const float big = width;
        // inside the chunk the neighbours are at fixed offsets; across its faces, look them up
        const int lx = x & 7, ly = y & 7, lz = z & 7;
        auto nb = [&](bool inside, ptrdiff_t off, bool exists, int xx, int yy, int zz) {
          return !exists ? big : std::fabs(cur[inside ? i + off : b.at(xx, yy, zz)]);
        };
        const float ax = std::min(nb(lx > 0, -1, x > 0, x - 1, y, z), nb(lx < 7, 1, x < b.nx - 1, x + 1, y, z));
        const float ay = std::min(nb(ly > 0, -8, y > 0, x, y - 1, z), nb(ly < 7, 8, y < b.ny - 1, x, y + 1, z));
        const float az = std::min(nb(lz > 0, -64, z > 0, x, y, z - 1), nb(lz < 7, 64, z < b.nz - 1, x, y, z + 1));
        const float u = std::min(eikonal(ax, ay, az), std::fabs(cur[i]));
        out[i] = sgn(cur[i]) * std::min(u, width);
      });
    });
    // fixed voxels and chunks not in `work` never change, so after the swap both buffers agree on them
    std::swap(v, next);
  }
}

struct Shape {  // one capsule (a == b: sphere), voxel units
  V3 a, b;
  float r;
};

inline float seg_dist(const V3& p, const V3& a, const V3& b) {
  const float bax = b.x - a.x, bay = b.y - a.y, baz = b.z - a.z;
  const float pax = p.x - a.x, pay = p.y - a.y, paz = p.z - a.z;
  const float bb = bax * bax + bay * bay + baz * baz;
  float h = bb > 0 ? (pax * bax + pay * bay + paz * baz) / bb : 0.0f;
  h = std::min(1.0f, std::max(0.0f, h));
  const float dx = pax - bax * h, dy = pay - bay * h, dz = paz - baz * h;
  return std::sqrt(dx * dx + dy * dy + dz * dz);
}

inline float smin(float a, float b, float k) {
  if (k <= 0) return std::min(a, b);
  const float h = std::max(k - std::fabs(a - b), 0.0f) / k;
  return std::min(a, b) - h * h * k * 0.25f;
}

inline float falloff(float t) {  // 1 at the centre, 0 at the rim, smooth
  if (t >= 1.0f) return 0.0f;
  const float u = 1.0f - t * t;
  return u * u;
}

inline V3 mirror_x(V3 p) { return {-p.x, p.y, p.z}; }


// A step's buffers, shared by every clay (steps run one at a time). Allocated without clearing: only the chunks a
// step lists are touched, so only they take memory. A big piece's buffers are given back after it.
struct Buffers {
  std::unique_ptr<float[]> a, b, orig, after, start;
  std::unique_ptr<uint8_t[]> fixed;
  size_t cap = 0;
  void fit(size_t n) {
    if (cap >= n) return;
    a.reset(new float[n]);
    b.reset(new float[n]);
    orig.reset(new float[n]);
    after.reset(new float[n]);
    start.reset(new float[n]);
    fixed.reset(new uint8_t[n]);
    cap = n;
  }
  void release() {
    a.reset();
    b.reset();
    orig.reset();
    after.reset();
    start.reset();
    fixed.reset();
    cap = 0;
  }
};
inline Buffers& buffers() {
  static Buffers B;
  return B;
}


constexpr float kBlendCap = 24.0f;   // a blend reads distances this far past the band at most (voxels; 15 mm here)
constexpr float kStrokeAcc = 12.0f;  // a stroke unit moves the surface at most this far (voxels): it stays in
                                     // the chunks found near the surface when the unit began (2 chunks)

inline float len3(V3 a) { return std::sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }

// how far one dab can move the surface (voxels)
inline float dab_shift(const Step& s, float iv) {
  const float r = s.radius * iv;
  switch (s.op) {
    case Op::Add:
    case Op::Carve: return std::min(s.strength * r * 0.15f, kDispCap);
    case Op::Smooth: return 0.5f;
    case Op::Flatten: return kDispCap;
    case Op::Pull: return std::min(len3(s.b) * iv, kDispCap);
    case Op::Crease: return kDispCap;
  }
  return kDispCap;
}

// the most the dabs [0, n) pile up on any one spot: for each dab, the shifts of all dabs that overlap it
inline float pile_up(const Step* d, size_t n, float iv) {
  float most = 0;
  for (size_t i = 0; i < n; ++i) {
    float sum = 0;
    for (size_t j = 0; j < n; ++j) {
      const float dx = d[i].a.x - d[j].a.x, dy = d[i].a.y - d[j].a.y, dz = d[i].a.z - d[j].a.z;
      const float rr = d[i].radius + d[j].radius;
      if (dx * dx + dy * dy + dz * dz < rr * rr) sum += dab_shift(d[j], iv);
      if (d[j].mirror) {  // its mirrored copy may land here too
        const float mx = d[i].a.x + d[j].a.x;
        if (mx * mx + dy * dy + dz * dz < rr * rr) sum += dab_shift(d[j], iv);
      }
    }
    most = std::max(most, sum);
  }
  return most;
}

struct DabShape {  // one dab or its mirrored copy, voxel units
  V3 c, n, b;
  float r;
};

inline V3 vsub(V3 a, V3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline float vdot(V3 a, V3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }


}  // namespace r3d::clay::detail

namespace r3d::clay::detail {

// One unit of dabs, handed from Volume::run (clay_volume.cpp) to the narrow-band dab pass (clay_band.cpp): the box
// and its buffers, filled; the dabs and their shapes; which chunks hold a leaf and which the unit works on.
struct DabUnit {
  const Box* b = nullptr;
  float* V = nullptr;         // the values, changed in place
  float* NX = nullptr;        // scratch: the values as the dab before left them (Smooth, Pull, Crease read these)
  const float* St = nullptr;  // where the stroke began (accumulate off)
  const Step* steps = nullptr;
  size_t n = 0;
  const std::vector<std::vector<DabShape>>* shapes = nullptr;
  const std::vector<float>* reach = nullptr;  // per dab: how far it reaches (voxels)
  const std::vector<float>* shift = nullptr;  // per dab: how far it moves the surface (voxels)
  const std::vector<uint8_t>* leaf = nullptr;
  const std::vector<uint8_t>* work = nullptr;
  const std::vector<int>* extList = nullptr;
  std::vector<uint8_t>* touched = nullptr;    // out: the chunks a dab worked on (only they are written back)
};
void run_dabs(const DabUnit& u);

}  // namespace r3d::clay::detail
