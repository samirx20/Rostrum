#include "clay.h"

#include <openvdb/io/File.h>
#include <tbb/blocked_range.h>
#include <tbb/parallel_for.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <map>
#include <set>
#include <sstream>
#include <tuple>

namespace clay {

using openvdb::Coord;
using Tree = openvdb::FloatTree;
using Leaf = Tree::LeafNodeType;

namespace {

constexpr float kDispCap = 2.0f;  // a stamp moves the surface at most this far (voxels) per dab

int floor_div(int a, int b) { return (a >= 0) ? a / b : -((-a + b - 1) / b); }
int floor8(int a) { return floor_div(a, 8) * 8; }
int ceil8(int a) { return -floor8(-a); }

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
template <class F> void par(const std::vector<int>& list, F&& f) {
  if (list.size() <= 12) {
    for (int ci : list) f(ci);
    return;
  }
  tbb::parallel_for(tbb::blocked_range<size_t>(0, list.size(), 4), [&](const tbb::blocked_range<size_t>& r) {
    for (size_t k = r.begin(); k < r.end(); ++k) f(list[k]);
  });
}

// flags dilated by r chunks (Chebyshev), separably
std::vector<uint8_t> dilate(const std::vector<uint8_t>& in, int nx, int ny, int nz, int r) {
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

std::vector<int> listed(const std::vector<uint8_t>& f) {
  std::vector<int> l;
  for (int i = 0; i < int(f.size()); ++i)
    if (f[i]) l.push_back(i);
  return l;
}

// Copy voxels [lo, lo+n) of `tree` into `out` (x fastest), leaf by leaf; tiles and background as their value.
// `parallel` only from a caller that is not itself inside a parallel loop: a nested loop lets TBB run another of the
// caller's tasks on this thread while it waits, and that task would reuse this thread's buffers (a race that left
// holes at block seams, different on every run)
void read_region(const Tree& tree, const Coord& lo, int nx, int ny, int nz, float* out, bool parallel = false) {
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
void relevel(const Box& b, float*& v, float*& next, const uint8_t* fixed, float width, const std::vector<int>& init,
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

V3 mirror_x(V3 p) { return {-p.x, p.y, p.z}; }

std::once_flag g_init;

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
Buffers& buffers() {
  static Buffers B;
  return B;
}

double g_prof[10] = {};  // --profile: ms spent in each part of the steps (see profile_text)

constexpr float kBlendCap = 24.0f;   // a blend reads distances this far past the band at most (voxels; 15 mm here)
constexpr float kStrokeAcc = 12.0f;  // a stroke unit moves the surface at most this far (voxels): it stays in
                                     // the chunks found near the surface when the unit began (2 chunks)

inline float len3(V3 a) { return std::sqrt(a.x * a.x + a.y * a.y + a.z * a.z); }

// how far one dab can move the surface (voxels)
float dab_shift(const Step& s, float iv) {
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
float pile_up(const Step* d, size_t n, float iv) {
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

}  // namespace

// What a stroke changed while it was being drawn: each chunk's state before its first change, put back at its end.
struct Clay::Backup {
  struct Chunk {
    Coord o;
    bool leaf = false;
    float value = 0;  // the tile's value when not a leaf
    std::vector<float> values;
    Leaf::NodeMaskType mask;
  };
  std::vector<Chunk> chunks;
  std::map<std::tuple<int, int, int>, size_t> seen;  // origin -> chunks index
  bool on = false;
  const Chunk* find(const Coord& o) const {
    if (!on) return nullptr;
    const auto it = seen.find({o.x(), o.y(), o.z()});
    return it == seen.end() ? nullptr : &chunks[it->second];
  }
  void keep(const Tree& t, const Coord& o) {
    if (!on || !seen.emplace(std::make_tuple(o.x(), o.y(), o.z()), chunks.size()).second) return;
    Chunk c;
    c.o = o;
    if (const Leaf* l = t.probeConstLeaf(o)) {
      c.leaf = true;
      c.values.assign(l->buffer().data(), l->buffer().data() + Leaf::SIZE);
      c.mask = l->getValueMask();
    } else {
      c.value = t.getValue(o);
    }
    chunks.push_back(std::move(c));
  }
};

Clay::~Clay() = default;

Clay::Clay(float voxel) : voxel_(voxel), backup_(std::make_unique<Backup>()) {
  std::call_once(g_init, [] { openvdb::initialize(); });
  grid_ = openvdb::FloatGrid::create(kBand);
  grid_->setTransform(openvdb::math::Transform::createLinearTransform(voxel));
  grid_->setGridClass(openvdb::GRID_LEVEL_SET);
  grid_->setName("clay");
}

StepTiming Clay::apply(const Step& s) { return run(&s, 1); }

StepTiming Clay::apply_stroke(const std::vector<Step>& dabs) {
  // the stroke in units that each move the surface at most kStrokeAcc: one fill, one re-levelling, one write per unit
  StepTiming t;
  const float iv = 1.0f / voxel_;
  for (size_t start = 0; start < dabs.size();) {
    size_t end = start + 1;
    if (!dabs[start].accumulate) end = dabs.size();
    while (end < dabs.size() && pile_up(&dabs[start], end + 1 - start, iv) <= kStrokeAcc) ++end;
    const StepTiming u = run(&dabs[start], end - start);
    t.ms += u.ms;
    t.voxels += u.voxels;
    start = end;
  }
  return t;
}

void Clay::begin_stroke() {
  backup_->chunks.clear();
  backup_->seen.clear();
  backup_->on = true;
}

StepTiming Clay::dab(const Step& s) { return run(&s, 1); }

StepTiming Clay::end_stroke(const std::vector<Step>& dabs) {
  const auto t0 = std::chrono::steady_clock::now();
  Tree& tree = grid_->tree();
  backup_->on = false;
  for (const Backup::Chunk& c : backup_->chunks) {  // put the clay back as it was before the stroke
    if (c.leaf) {
      Leaf* l = tree.touchLeaf(c.o);
      std::memcpy(l->buffer().data(), c.values.data(), sizeof(float) * Leaf::SIZE);
      l->setValueMask(c.mask);
    } else {
      tree.addTile(1, c.o, c.value, false);
    }
  }
  backup_->chunks.clear();
  backup_->seen.clear();
  StepTiming t = apply_stroke(dabs);
  t.ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  return t;
}

StepTiming Clay::run(const Step* steps, size_t n) {
  const auto t0 = std::chrono::steady_clock::now();
  Buffers& S = buffers();
  const float iv = 1.0f / voxel_;
  auto vox = [&](V3 p) { return V3{p.x * iv, p.y * iv, p.z * iv}; };
  const bool piece = steps[0].kind == Kind::Piece;  // a piece is always alone (n == 1)
  const Step& s0 = steps[0];

  // the shapes (voxel units), mirrored copies included
  std::vector<Shape> pieceShapes;
  std::vector<std::vector<DabShape>> dabShapes(n);
  std::vector<float> shift(n, 0), reachOf(n, 0);
  float k = 0;
  if (piece) {
    const float r = s0.radius * iv;
    pieceShapes.push_back({vox(s0.a), vox(s0.b), r});
    if (s0.mirror) pieceShapes.push_back({vox(mirror_x(s0.a)), vox(mirror_x(s0.b)), r});
    k = s0.blend * iv;
  } else {
    for (size_t j = 0; j < n; ++j) {
      const Step& s = steps[j];
      const float r = s.radius * iv;
      V3 bvec = s.op == Op::Pull ? vox(s.b) : s.b;  // Pull: a vector in voxels (at most kDispCap); Crease: a direction
      if (s.op == Op::Pull && len3(bvec) > kDispCap) bvec = {bvec.x * kDispCap / len3(bvec), bvec.y * kDispCap / len3(bvec),
                                                               bvec.z * kDispCap / len3(bvec)};
      dabShapes[j].push_back({vox(s.a), s.n, bvec, r});
      if (s.mirror) dabShapes[j].push_back({vox(mirror_x(s.a)), mirror_x(s.n), mirror_x(bvec), r});
      shift[j] = dab_shift(s, iv);
      reachOf[j] = r + kBand + 1 + shift[j];
    }
  }
  // how wide the distances must be before the step: a blend reads them up to k past the band, a unit of dabs up to
  // its pile-up (a single small dab moves less than the trusted band and needs nothing wider)
  const float wpre = piece ? (k > 0 ? kBand + std::min(k, kBlendCap) + 1.5f : 0.0f)
                           : 0.0f;  // a dab moves the surface less than the trusted band
  const int rch = int(std::ceil(std::max(wpre, kBand) / 8.0f));
  const int nearR = (!piece && n > 1) ? 2 : 1;  // a unit of dabs can move the surface up to a chunk
  float lo[3] = {1e30f, 1e30f, 1e30f}, hi[3] = {-1e30f, -1e30f, -1e30f};
  auto grow = [&](V3 p, float r) {
    lo[0] = std::min(lo[0], p.x - r), lo[1] = std::min(lo[1], p.y - r), lo[2] = std::min(lo[2], p.z - r);
    hi[0] = std::max(hi[0], p.x + r), hi[1] = std::max(hi[1], p.y + r), hi[2] = std::max(hi[2], p.z + r);
  };
  if (piece) {
    for (const Shape& sh : pieceShapes) {
      grow(sh.a, sh.r + k + kBand + 1);
      grow(sh.b, sh.r + k + kBand + 1);
    }
  } else {
    for (size_t j = 0; j < n; ++j)
      for (const DabShape& d : dabShapes[j]) grow(d.c, reachOf[j]);
  }
  const int ring = 8 * (std::max(rch, nearR) + 1);
  const Coord ilo(floor8(int(std::floor(lo[0]))), floor8(int(std::floor(lo[1]))), floor8(int(std::floor(lo[2]))));
  const Coord ihi(ceil8(int(std::ceil(hi[0])) + 1), ceil8(int(std::ceil(hi[1])) + 1), ceil8(int(std::ceil(hi[2])) + 1));
  Box b;
  b.lo = ilo - Coord(ring);
  b.nx = ihi.x() - ilo.x() + 2 * ring;
  b.ny = ihi.y() - ilo.y() + 2 * ring;
  b.nz = ihi.z() - ilo.z() + 2 * ring;
  b.cnx = b.nx / 8;
  b.cny = b.ny / 8;
  b.cnz = b.nz / 8;
  S.fit(b.size());
  float* V = S.a.get();
  float* NX = S.b.get();
  float* O = S.orig.get();
  float* A = S.after.get();
  float* St = S.start.get();  // the clay where the stroke began (accumulate off)
  uint8_t* F = S.fixed.get();
  const int nch = b.chunks();
  Tree& tree = grid_->tree();

  // A. which chunks hold a leaf (the surface is only ever near one); the others are one value
  std::vector<uint8_t> leaf(nch);
  std::vector<float> uval(nch);
  tbb::parallel_for(0, nch, [&](int ci) {
    int x, y, z;
    b.corner(ci, x, y, z);
    const Coord o = b.lo + Coord(x, y, z);
    leaf[ci] = tree.probeConstLeaf(o) != nullptr;
    uval[ci] = leaf[ci] ? 0.0f : tree.getValue(o);
  });
  const std::vector<uint8_t> near = dilate(leaf, b.cnx, b.cny, b.cnz, nearR);

  // B. the chunks the step works on, and the ones a piece turns into one value (wholly inside it)
  const int rc = ring / 8;
  const float hd = 6.1f;  // a chunk's centre to its farthest voxel
  std::vector<uint8_t> work(nch, 0);
  std::vector<int8_t> whole(nch, 0);  // -1 / +1: becomes all inside / all outside
  auto centre = [&](int ci) {
    const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
    return V3{b.lo.x() + 8.0f * cx + 3.5f, b.lo.y() + 8.0f * cy + 3.5f, b.lo.z() + 8.0f * cz + 3.5f};
  };
  auto dab_reaches = [&](size_t j, V3 c, float margin) {
    for (const DabShape& d : dabShapes[j]) {
      const V3 e = vsub(c, d.c);
      const float lim = reachOf[j] + hd + margin;
      if (vdot(e, e) < lim * lim) return true;
    }
    return false;
  };
  tbb::parallel_for(0, nch, [&](int ci) {
    const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
    if (cx < rc || cy < rc || cz < rc || cx >= b.cnx - rc || cy >= b.cny - rc || cz >= b.cnz - rc) return;
    const V3 c = centre(ci);
    if (piece) {
      float d = 1e30f;
      for (const Shape& sh : pieceShapes) d = std::min(d, seg_dist(c, sh.a, sh.b) - sh.r);
      if (d < -(hd + kBand + 1)) {
        const float target = s0.op == Op::Add ? -kBand : kBand;
        if (leaf[ci] || uval[ci] != target) whole[ci] = s0.op == Op::Add ? -1 : 1;
      } else if (d < hd + k + kBand + 1) {
        work[ci] = 1;
      }
    } else if (near[ci]) {
      for (size_t j = 0; j < n && !work[ci]; ++j) work[ci] = dab_reaches(j, c, 0);
    }
  });
  const std::vector<int> workList = listed(work);
  const std::vector<uint8_t> pre = wpre > 0 ? dilate(work, b.cnx, b.cny, b.cnz, rch) : work;
  const std::vector<int> preList = listed(pre);
  const std::vector<int> extList = listed(dilate(pre, b.cnx, b.cny, b.cnz, 1));

  std::vector<uint8_t> touched(nch, 0);  // chunks a dab worked on (only they are written back)
  bool needStart = false;
  for (size_t j = 0; j < n && !piece; ++j) needStart |= !steps[j].accumulate;

  const auto tFill = std::chrono::steady_clock::now();
  // C. fill the listed chunks from the grid (and, for strokes without accumulate, where the stroke began: a live
  //    stroke's chunks as they were before its first dab, kept aside in the backup)
  par(extList, [&](int ci) {
    int x, y, z;
    b.corner(ci, x, y, z);
    if (leaf[ci]) {
      const float* d = tree.probeConstLeaf(b.lo + Coord(x, y, z))->buffer().data();
      b.each(ci, [&](int xx, int yy, int zz, size_t i) { V[i] = d[leaf_offset(xx, yy, zz)]; });
    } else {
      const float u = uval[ci];
      b.each(ci, [&](int, int, int, size_t i) { V[i] = u; });
    }
    if (needStart) {
      const Backup::Chunk* kept = backup_->find(b.lo + Coord(x, y, z));
      if (!kept) b.copy(ci, V, St);
      else if (kept->leaf) b.each(ci, [&](int xx, int yy, int zz, size_t i) { St[i] = kept->values[leaf_offset(xx, yy, zz)]; });
      else b.each(ci, [&](int, int, int, size_t i) { St[i] = kept->value; });
    }
  });

  // D. widen the distances to what the step reads (the stored band is trusted)
  if (wpre > 0) {
    par(extList, [&](int ci) { b.each(ci, [&](int, int, int, size_t i) { F[i] = std::fabs(V[i]) < kBand - 0.5f; }); });
    relevel(b, V, NX, F, wpre, extList, extList, preList);
  }

  const auto tWork = std::chrono::steady_clock::now();
  // E/F. the step, then back to the stored band: unchanged band voxels stay; changed ones next to the surface are
  //      re-scaled to a distance by their own gradient (value / |gradient|, central differences: smooth, no
  //      voxel-scale noise); the rest is re-levelled. A piece does this once over every listed chunk; dabs one after
  //      another, each over its own chunks (a stroke shares one fill and one write-back), so no dab needs the band
  //      wider than it is.
  const auto P = [&](int x, int y, int z) { return V3{float(b.lo.x() + x), float(b.lo.y() + y), float(b.lo.z() + z)}; };
  // seeds and fixed voxels over `list` (reading neighbours from A, a copy of V); O holds the values before the change
  auto settle = [&](const std::vector<int>& list) {
    par(list, [&](int ci) {
      b.each(ci, [&](int x, int y, int z, size_t i) {
        const float v = A[i];
        uint8_t f = 0;
        if (v == O[i]) {
          f = std::fabs(v) < kBand - 1.0f;
        } else if (x > 0 && y > 0 && z > 0 && x < b.nx - 1 && y < b.ny - 1 && z < b.nz - 1) {
          const float xm = A[b.at(x - 1, y, z)], xp = A[b.at(x + 1, y, z)];
          const float ym = A[b.at(x, y - 1, z)], yp = A[b.at(x, y + 1, z)];
          const float zm = A[b.at(x, y, z - 1)], zp = A[b.at(x, y, z + 1)];
          const bool crossing = (xm < 0) != (v < 0) || (xp < 0) != (v < 0) || (ym < 0) != (v < 0) ||
                                (yp < 0) != (v < 0) || (zm < 0) != (v < 0) || (zp < 0) != (v < 0);
          if (crossing) {
            const float gx = 0.5f * (xp - xm), gy = 0.5f * (yp - ym), gz = 0.5f * (zp - zm);
            const float g = std::min(2.0f, std::max(0.5f, std::sqrt(gx * gx + gy * gy + gz * gz)));
            V[i] = v / g;
            f = 2;
          }
        }
        F[i] = f;
      });
    });
  };
  if (piece) {
    par(extList, [&](int ci) { b.copy(ci, V, O); });
    par(extList, [&](int ci) {
      b.each(ci, [&](int x, int y, int z, size_t i) {
        const V3 p = P(x, y, z);
        float d = 1e30f;
        for (const Shape& sh : pieceShapes) d = std::min(d, seg_dist(p, sh.a, sh.b) - sh.r);
        if (s0.op == Op::Add) V[i] = smin(O[i], d, k);
        else if (s0.op == Op::Carve) V[i] = -smin(-O[i], d, k);
      });
    });
    par(extList, [&](int ci) { b.copy(ci, V, A); });
    settle(extList);
    relevel(b, V, NX, F, kBand, extList, extList, workList);
  } else {
    std::vector<uint8_t> hot = leaf, inExt(nch, 0);  // chunks holding the band (a leaf, at first); listed chunks
    for (int ci : extList) inExt[ci] = 1;
    std::vector<uint32_t> mark(nch, 0);
    uint32_t stamp = 0;
    struct Vox {  // one voxel of a dab's narrow band: its index in the buffers and its box position
      uint32_t i;
      int16_t x, y, z;
    };
    std::vector<std::vector<Vox>> perChunk;
    std::vector<Vox> L;
    std::vector<int32_t> slotOf(nch, -1), pool, nb;  // band index of a voxel, per listed chunk; neighbours
    std::vector<float> oldL, curL, nextL;
    std::vector<uint8_t> fixL;
    for (size_t j = 0; j < n; ++j) {
      const Step& s = steps[j];
      const auto qm = std::chrono::steady_clock::now();
      // the dab's chunks: in its reach and next to a chunk that holds the band now (the surface moves during a
      // stroke, so this follows it); and those plus their neighbours, for reading around a voxel
      std::vector<int> mine, around;
      for (int ci : extList) {
        if (!work[ci] || !dab_reaches(j, centre(ci), 0)) continue;
        const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
        bool nearBand = false;
        for (int dz = -1; dz <= 1 && !nearBand; ++dz)
          for (int dy = -1; dy <= 1 && !nearBand; ++dy)
            for (int dx = -1; dx <= 1 && !nearBand; ++dx) {
              const int x = cx + dx, y = cy + dy, z = cz + dz;
              if (x >= 0 && y >= 0 && z >= 0 && x < b.cnx && y < b.cny && z < b.cnz)
                nearBand = hot[x + b.cnx * (y + b.cny * z)];
            }
        if (nearBand) mine.push_back(ci);
      }
      if (mine.empty()) continue;
      ++stamp;
      for (int ci : mine) {
        touched[ci] = 1;
        const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
        for (int dz = -1; dz <= 1; ++dz)
          for (int dy = -1; dy <= 1; ++dy)
            for (int dx = -1; dx <= 1; ++dx) {
              const int x = cx + dx, y = cy + dy, z = cz + dz;
              if (x < 0 || y < 0 || z < 0 || x >= b.cnx || y >= b.cny || z >= b.cnz) continue;
              const int q = x + b.cnx * (y + b.cny * z);
              if (inExt[q] && mark[q] != stamp) mark[q] = stamp, around.push_back(q);
            }
      }
      using PC = std::chrono::steady_clock;
      const auto q0 = PC::now();
      // The narrow band the dab works on: voxels in its reach that are in the band (|v| < kBand) or within 2 voxels
      // of it (a dab moves the surface at most kDispCap = 2, so the band can only grow that far). Everything else
      // in reach is clamped clay far from the surface and stays as it is.
      const float reachSq = reachOf[j] * reachOf[j];
      perChunk.assign(mine.size(), {});
      tbb::parallel_for(size_t(0), mine.size(), [&](size_t k) {
        std::vector<Vox>& out = perChunk[k];
        const int ci = mine[k];
        int x0, y0, z0;
        b.corner(ci, x0, y0, z0);
        // the chunk's band flags with a 2-voxel halo on each face (12^3, z y x), read once; the axis stencil below
        // then only touches this small grid
        uint8_t g[12 * 12 * 12] = {};
        auto G = [](int x, int y, int z) { return (z + 2) * 144 + (y + 2) * 12 + (x + 2); };
        bool any = false;
        b.each(ci, [&](int x, int y, int z, size_t i) {
          const uint8_t f = std::fabs(V[i]) < kBand;
          g[G(x - x0, y - y0, z - z0)] = f;
          any |= f != 0;
        });
        // a face next to a chunk with no band (one value, far from the surface) has no flags to read
        const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
        auto banded = [&](int x, int y, int z) { return hot[x + b.cnx * (y + b.cny * z)] != 0; };
        const bool face[6] = {banded(cx - 1, cy, cz), banded(cx + 1, cy, cz), banded(cx, cy - 1, cz),
                              banded(cx, cy + 1, cz), banded(cx, cy, cz - 1), banded(cx, cy, cz + 1)};
        for (int d = 1; d <= 2; ++d)
          for (int u = 0; u < 8; ++u)
            for (int w = 0; w < 8; ++w) {
              auto flag = [&](bool on, int x, int y, int z) {
                return uint8_t(on && std::fabs(V[b.at(x, y, z)]) < kBand);
              };
              const uint8_t f[6] = {flag(face[0], x0 - d, y0 + u, z0 + w), flag(face[1], x0 + 7 + d, y0 + u, z0 + w),
                                    flag(face[2], x0 + u, y0 - d, z0 + w), flag(face[3], x0 + u, y0 + 7 + d, z0 + w),
                                    flag(face[4], x0 + u, y0 + w, z0 - d), flag(face[5], x0 + u, y0 + w, z0 + 7 + d)};
              g[G(-d, u, w)] = f[0], g[G(7 + d, u, w)] = f[1], g[G(u, -d, w)] = f[2], g[G(u, 7 + d, w)] = f[3];
              g[G(u, w, -d)] = f[4], g[G(u, w, 7 + d)] = f[5];
              any |= (f[0] | f[1] | f[2] | f[3] | f[4] | f[5]) != 0;
            }
        if (!any) return;
        b.each(ci, [&](int x, int y, int z, size_t i) {
          const int c = G(x - x0, y - y0, z - z0);
          if (!(g[c] | g[c - 1] | g[c + 1] | g[c - 2] | g[c + 2] | g[c - 12] | g[c + 12] | g[c - 24] | g[c + 24] |
                g[c - 144] | g[c + 144] | g[c - 288] | g[c + 288]))
            return;
          const V3 p = P(x, y, z);
          bool in = false;
          for (const DabShape& d : dabShapes[j]) {
            const V3 e = vsub(p, d.c);
            in |= vdot(e, e) < reachSq;
          }
          if (in) out.push_back({uint32_t(i), int16_t(x), int16_t(y), int16_t(z)});
        });
      });
      L.clear();
      for (const auto& v : perChunk) L.insert(L.end(), v.begin(), v.end());  // in chunk order: the same every run
      if (L.empty()) continue;
      const size_t K = L.size();
      const auto q1 = PC::now();
      auto overK = [&](auto&& f) {  // f(k) over the band, in parallel blocks (alone when small)
        if (K < 16384) {  // a small dab: one thread beats waking the others for every pass
          for (size_t k = 0; k < K; ++k) f(k);
          return;
        }
        tbb::parallel_for(tbb::blocked_range<size_t>(0, K, 2048), [&](const tbb::blocked_range<size_t>& r) {
          for (size_t k = r.begin(); k < r.end(); ++k) f(k);
        });
      };
      // each band voxel's 6 neighbours, found once: an index into the band (>= 0), or -(box index + 1) for a voxel
      // off the band, whose value doesn't change during the dab. The passes then only gather from small arrays.
      // (band voxels are only ever in the dab's own chunks, so only those get a table)
      for (size_t a = 0; a < mine.size(); ++a) slotOf[mine[a]] = int32_t(a);
      pool.resize(mine.size() * 512);
      tbb::parallel_for(size_t(0), mine.size(), [&](size_t a) { std::fill_n(pool.begin() + a * 512, 512, -1); });
      overK([&](size_t k) { pool[size_t(slotOf[L[k].i / 512]) * 512 + L[k].i % 512] = int32_t(k); });
      nb.resize(K * 6);
      overK([&](size_t k) {
        const Vox& q = L[k];
        const size_t idx[6] = {b.at(q.x - 1, q.y, q.z), b.at(q.x + 1, q.y, q.z), b.at(q.x, q.y - 1, q.z),
                               b.at(q.x, q.y + 1, q.z), b.at(q.x, q.y, q.z - 1), b.at(q.x, q.y, q.z + 1)};
        for (int m = 0; m < 6; ++m) {
          const int32_t s32 = slotOf[idx[m] / 512];
          const int32_t kk = s32 < 0 ? -1 : pool[size_t(s32) * 512 + idx[m] % 512];
          nb[k * 6 + m] = kk >= 0 ? kk : -int32_t(idx[m]) - 1;
        }
      });
      for (int ci : mine) slotOf[ci] = -1;
      const auto q2 = PC::now();
      const bool reads = s.op == Op::Smooth || s.op == Op::Pull || s.op == Op::Crease;
      if (reads) par(around, [&](int ci) { b.copy(ci, V, NX); });  // the values as the dab before left them
      oldL.resize(K);
      overK([&](size_t k) { oldL[k] = V[L[k].i]; });
      const float disp = shift[j];
      overK([&](size_t k) {
        const Vox& q = L[k];
        const size_t i = q.i;
        const int x = q.x, y = q.y, z = q.z;
        const V3 p = P(x, y, z);
        // the shape (or its mirrored copy) that weighs most here
        float w = 0;
        const DabShape* best = nullptr;
        for (const DabShape& d : dabShapes[j]) {
          const V3 e = vsub(p, d.c);
          const float wd = falloff(std::sqrt(vdot(e, e)) / d.r);
          if (wd > w) w = wd, best = &d;
        }
        if (w <= 0) return;
        const float old = V[i];
        const float bx = float(x), by = float(y), bz = float(z);
        switch (s.op) {
          case Op::Add:  // without accumulate, a stroke raises the surface at most one dab above where it began
            V[i] = old - disp * w;
            if (!s.accumulate) V[i] = std::max(V[i], St[i] - disp * w);
            break;
          case Op::Carve:
            V[i] = old + disp * w;
            if (!s.accumulate) V[i] = std::min(V[i], St[i] + disp * w);
            break;
          case Op::Smooth: {
            const float avg = (NX[b.at(x - 1, y, z)] + NX[b.at(x + 1, y, z)] + NX[b.at(x, y - 1, z)] +
                               NX[b.at(x, y + 1, z)] + NX[b.at(x, y, z - 1)] + NX[b.at(x, y, z + 1)]) / 6.0f;
            V[i] = old + 0.6f * s.strength * w * (avg - old);
            break;
          }
          case Op::Flatten: {  // towards the plane through the dab point, across the brush
            const float plane = vdot(vsub(p, best->c), best->n);
            V[i] = old + std::max(-kDispCap, std::min(kDispCap, 0.35f * s.strength * w * (plane - old)));
            break;
          }
          case Op::Pull: {  // the clay under the brush moves by b (falling off): read where it comes from
            V[i] = b.sample(NX, bx - best->b.x * w, by - best->b.y * w, bz - best->b.z * w);
            break;
          }
          case Op::Crease: {  // pinch towards the line (in the surface, across the stroke), then dig a narrow groove
            const V3 e = vsub(p, best->c);
            const float along = vdot(e, best->b), up = vdot(e, best->n);
            const V3 across{e.x - best->b.x * along - best->n.x * up, e.y - best->b.y * along - best->n.y * up,
                            e.z - best->b.z * along - best->n.z * up};
            const float pinch = std::min(0.4f * s.strength, 0.5f) * w;
            float mx = across.x * pinch, my = across.y * pinch, mz = across.z * pinch;
            const float ml = std::sqrt(mx * mx + my * my + mz * mz);
            if (ml > kDispCap) mx *= kDispCap / ml, my *= kDispCap / ml, mz *= kDispCap / ml;
            const float pinched = b.sample(NX, bx + mx, by + my, bz + mz);  // material from farther out
            const float dl = std::sqrt(std::max(0.0f, vdot(e, e) - along * along - up * up)) / best->r;
            const float g = std::max(0.0f, 1.0f - dl / 0.3f);
            const float depth = std::min(s.strength * best->r * 0.2f, kDispCap);
            V[i] = pinched + depth * g * g * falloff(std::fabs(along) / best->r);
            break;
          }
        }
      });
      const auto q3 = PC::now();
      // back to the stored band, on the narrow band only: unchanged band voxels stay; changed ones next to the
      // surface are re-scaled by their own gradient; the rest of the band is re-levelled from them
      auto val = [&](int32_t m, const std::vector<float>& band) { return m >= 0 ? band[m] : V[size_t(-m - 1)]; };
      curL.resize(K);
      overK([&](size_t k) { curL[k] = V[L[k].i]; });  // after the dab
      fixL.resize(K);
      nextL.resize(K);
      overK([&](size_t k) {
        const float v = curL[k];
        const int32_t* m = &nb[k * 6];
        uint8_t f = 0;
        float out = v;
        if (v == oldL[k]) {
          f = std::fabs(v) < kBand - 1.0f;
        } else {
          const float xm = val(m[0], curL), xp = val(m[1], curL), ym = val(m[2], curL), yp = val(m[3], curL);
          const float zm = val(m[4], curL), zp = val(m[5], curL);
          const bool crossing = (xm < 0) != (v < 0) || (xp < 0) != (v < 0) || (ym < 0) != (v < 0) ||
                                (yp < 0) != (v < 0) || (zm < 0) != (v < 0) || (zp < 0) != (v < 0);
          if (crossing) {
            const float gx = 0.5f * (xp - xm), gy = 0.5f * (yp - ym), gz = 0.5f * (zp - zm);
            const float g = std::min(2.0f, std::max(0.5f, std::sqrt(gx * gx + gy * gy + gz * gz)));
            out = v / g;
            f = 2;
          }
        }
        fixL[k] = f;
        nextL[k] = f ? out : sgn(v) * kBand;  // unknown: starts at the band's edge
      });
      curL.swap(nextL);
      nextL = curL;
      // Jacobi upwind eikonal over the band only: seeds are within a voxel of the surface and the band is kBand wide,
      // so kBand passes reach its edge
      for (int pass = 0; pass < int(kBand); ++pass) {
        overK([&](size_t k) {
          if (fixL[k]) return;
          const int32_t* m = &nb[k * 6];
          const float ax = std::min(std::fabs(val(m[0], curL)), std::fabs(val(m[1], curL)));
          const float ay = std::min(std::fabs(val(m[2], curL)), std::fabs(val(m[3], curL)));
          const float az = std::min(std::fabs(val(m[4], curL)), std::fabs(val(m[5], curL)));
          nextL[k] = sgn(curL[k]) * std::min(std::min(eikonal(ax, ay, az), std::fabs(curL[k])), kBand);
        });
        curL.swap(nextL);  // fixed voxels are the same in both
      }
      const auto q4 = PC::now();
      overK([&](size_t k) { V[L[k].i] = curL[k]; });
      for (size_t k = 0; k < K; ++k)  // which chunks hold the band now (a hint for the next dab: it only grows)
        if (std::fabs(curL[k]) < kBand) hot[L[k].i / 512] = 1;
      {
        auto ms = [](auto a, auto b) { return std::chrono::duration<double, std::milli>(b - a).count(); };
        g_prof[0] += ms(qm, q0), g_prof[1] += ms(q0, q1), g_prof[2] += ms(q1, q2), g_prof[3] += ms(q2, q3);
        g_prof[4] += ms(q3, q4), g_prof[5] += ms(q4, PC::now());
      }
      static const bool kProfile = std::getenv("CLAY_PROFILE") != nullptr;
      if (kProfile && K > 50000) {
        auto ms = [](auto a, auto b) { return std::chrono::duration<double, std::milli>(b - a).count(); };
        std::printf("    dab: mine %zu chunks, band %zu voxels: scan %.1f, neighbours %.1f, op %.1f, re-level %.1f, "
                    "back %.1f ms\n", mine.size(), K, ms(q0, q1), ms(q1, q2), ms(q2, q3), ms(q3, q4), ms(q4, PC::now()));
      }
    }
  }

  const auto tWrite = std::chrono::steady_clock::now();
  // G. write back: worked chunks (uniform ones become tiles), and the chunks a piece filled or emptied
  std::vector<int8_t> cls(nch, 2);  // +1 all outside, -1 all inside, 0 mixed, 2 not written
  std::vector<int> writeList;
  if (piece) writeList = workList;
  else
    for (int ci : workList)
      if (touched[ci]) writeList.push_back(ci);
  par(writeList, [&](int ci) {
    bool allOut = true, allIn = true;
    b.each(ci, [&](int, int, int, size_t i) {
      allOut &= V[i] >= kBand;
      allIn &= V[i] <= -kBand;
    });
    cls[ci] = allOut ? 1 : allIn ? -1 : 0;
  });
  for (int ci = 0; ci < nch; ++ci)
    if (whole[ci]) cls[ci] = whole[ci];
  std::vector<Leaf*> leaves(nch, nullptr);
  std::vector<int> mixed;
  int wlo[3] = {1 << 30, 1 << 30, 1 << 30}, whi[3] = {-(1 << 30), -(1 << 30), -(1 << 30)};
  for (int ci = 0; ci < nch; ++ci) {
    if (cls[ci] == 2) continue;
    int x, y, z;
    b.corner(ci, x, y, z);
    const Coord o = b.lo + Coord(x, y, z);
    if (cls[ci] == 0) {
      backup_->keep(tree, o);
      leaves[ci] = tree.touchLeaf(o);
      mixed.push_back(ci);
    } else {
      const float val = cls[ci] * kBand;
      if (!leaf[ci] && uval[ci] == val) continue;  // already that tile: nothing changed here
      backup_->keep(tree, o);
      tree.addTile(1, o, val, false);
    }
    wlo[0] = std::min(wlo[0], o.x());
    wlo[1] = std::min(wlo[1], o.y());
    wlo[2] = std::min(wlo[2], o.z());
    whi[0] = std::max(whi[0], o.x() + 7);
    whi[1] = std::max(whi[1], o.y() + 7);
    whi[2] = std::max(whi[2], o.z() + 7);
  }
  par(mixed, [&](int ci) {
    Leaf* lf = leaves[ci];
    b.each(ci, [&](int x, int y, int z, size_t i) {
      const float v = V[i];
      const int off = leaf_offset(x, y, z);
      if (std::fabs(v) < kBand) lf->setValueOn(off, v);
      else lf->setValueOff(off, sgn(v) * kBand);
    });
  });

  // H. the blocks whose surface may have changed: block b reads voxels [32b - 2, 32b + 33] (normals included)
  if (wlo[0] <= whi[0])
    for (int bz = floor_div(wlo[2] - 2, kBlock); bz <= floor_div(whi[2] + 2, kBlock); ++bz)
      for (int by = floor_div(wlo[1] - 2, kBlock); by <= floor_div(whi[1] + 2, kBlock); ++by)
        for (int bx = floor_div(wlo[0] - 2, kBlock); bx <= floor_div(whi[0] + 2, kBlock); ++bx)
          dirty_.insert(BlockKey{bx, by, bz});

  // a piece's buffers (a big box, wide blends) can be hundreds of MB: give them back rather than keep them for the dabs
  if (piece || b.size() > (size_t(16) << 20)) S.release();

  const auto tEnd = std::chrono::steady_clock::now();
  StepTiming t;
  t.voxels = writeList.size() * 512;
  auto msd = [](auto a, auto b) { return std::chrono::duration<double, std::milli>(b - a).count(); };
  g_prof[6] += msd(t0, tFill), g_prof[7] += msd(tFill, tWork), g_prof[8] += msd(tWrite, tEnd), g_prof[9] += 1;
  t.prepMs = msd(t0, tFill);
  t.fillMs = msd(tFill, tWork);
  t.workMs = msd(tWork, tWrite);
  t.writeMs = msd(tWrite, tEnd);
  t.ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  return t;
}

std::string profile_text() {
  char b[512];
  std::snprintf(b, sizeof b, "units %.0f | per unit: find %.0f fill %.0f write %.0f ms total | per dab: chunks %.0f scan %.0f "
                "neighbours %.0f op %.0f re-level %.0f back %.0f ms total",
                g_prof[9], g_prof[6], g_prof[7], g_prof[8], g_prof[0], g_prof[1], g_prof[2], g_prof[3], g_prof[4],
                g_prof[5]);
  return b;
}

std::set<BlockKey> Clay::take_dirty() {
  std::set<BlockKey> d;
  d.swap(dirty_);
  return d;
}

void Clay::mesh(const BlockKey& k, BlockMesh& out) const {
  thread_local std::vector<float> wide(size_t(kWide) * kWide * kWide), dense(size_t(kDense) * kDense * kDense);
  read_region(grid_->tree(), Coord(k.x * kBlock - 2, k.y * kBlock - 2, k.z * kBlock - 2), kWide, kWide, kWide,
              wide.data());
  for (int z = 0; z < kDense; ++z)
    for (int y = 0; y < kDense; ++y)
      std::memcpy(&dense[size_t(kDense) * (y + size_t(kDense) * z)],
                  &wide[1 + size_t(kWide) * ((y + 1) + size_t(kWide) * (z + 1))], kDense * sizeof(float));
  mesh_block(dense.data(), wide.data(), k, voxel_, out);
}

std::vector<BlockKey> Clay::all_blocks() const {
  std::set<BlockKey> s;
  for (auto it = grid_->tree().cbeginLeaf(); it; ++it) {
    if (it->isEmpty()) continue;  // no active voxel: no surface
    // the leaf's block, and the blocks just below it on each axis: an edge into this leaf can start one voxel
    // before it, and the block of an edge's start owns its quad (mesh.h)
    const Coord o = it->origin();
    const int bx = floor_div(o.x(), kBlock), by = floor_div(o.y(), kBlock), bz = floor_div(o.z(), kBlock);
    s.insert(BlockKey{bx, by, bz});
    s.insert(BlockKey{floor_div(o.x() - 1, kBlock), by, bz});
    s.insert(BlockKey{bx, floor_div(o.y() - 1, kBlock), bz});
    s.insert(BlockKey{bx, by, floor_div(o.z() - 1, kBlock)});
  }
  return {s.begin(), s.end()};
}

void Clay::mesh_all(std::vector<std::pair<BlockKey, BlockMesh>>& out) const {
  const auto keys = all_blocks();
  out.assign(keys.size(), {});
  tbb::parallel_for(size_t(0), keys.size(), [&](size_t i) {
    out[i].first = keys[i];
    mesh(keys[i], out[i].second);
  });
}

float Clay::sample(const V3& p) const {
  const float x = p.x / voxel_, y = p.y / voxel_, z = p.z / voxel_;
  const int ix = int(std::floor(x)), iy = int(std::floor(y)), iz = int(std::floor(z));
  const float fx = x - ix, fy = y - iy, fz = z - iz;
  float c[8];
  read_region(grid_->tree(), Coord(ix, iy, iz), 2, 2, 2, c);
  const float c00 = c[0] + (c[1] - c[0]) * fx, c10 = c[2] + (c[3] - c[2]) * fx;
  const float c01 = c[4] + (c[5] - c[4]) * fx, c11 = c[6] + (c[7] - c[6]) * fx;
  const float c0 = c00 + (c10 - c00) * fy, c1 = c01 + (c11 - c01) * fy;
  return c0 + (c1 - c0) * fz;
}

bool Clay::snap(const V3& p, V3& on, V3& normal) const {
  // march along the field towards the surface: distance steps while far, then Newton steps along the gradient
  V3 q = p;
  const float h = 0.5f * voxel_;
  for (int it = 0; it < 400; ++it) {
    const float v = sample(q);
    const float gx = (sample({q.x + h, q.y, q.z}) - sample({q.x - h, q.y, q.z}));
    const float gy = (sample({q.x, q.y + h, q.z}) - sample({q.x, q.y - h, q.z}));
    const float gz = (sample({q.x, q.y, q.z + h}) - sample({q.x, q.y, q.z - h}));
    const float gl = std::sqrt(gx * gx + gy * gy + gz * gz);
    if (gl < 1e-6f) return false;  // far from any surface (the field is flat out there)
    normal = {gx / gl, gy / gl, gz / gl};
    if (std::fabs(v) < 0.02f) {
      on = q;
      return true;
    }
    const float step = std::max(-kBand + 0.5f, std::min(kBand - 0.5f, v)) * voxel_;
    q = {q.x - normal.x * step, q.y - normal.y * step, q.z - normal.z * step};
  }
  return false;
}

bool Clay::cast(const V3& o, const V3& d, float maxDist, V3& on, V3& normal) const {
  float t = 0;
  float prev = sample(o);
  if (prev <= 0) return false;  // starts inside the clay
  while (t < maxDist) {
    const float step = std::max(0.5f, 0.9f * std::fabs(prev)) * voxel_;
    const float tn = t + step;
    const V3 q{o.x + d.x * tn, o.y + d.y * tn, o.z + d.z * tn};
    const float v = sample(q);
    if (v <= 0) {  // crossed: the zero between t and tn, linearly, then onto the surface
      const float th = t + step * prev / (prev - v);
      return snap({o.x + d.x * th, o.y + d.y * th, o.z + d.z * th}, on, normal);
    }
    t = tn;
    prev = v;
  }
  return false;
}

void Clay::probe(int x, int y, int z0, int z1) const {
  const Tree& t = grid_->tree();
  for (int z = z0; z <= z1; ++z) {
    const Coord c(x, y, z);
    std::printf("    (%d %d %d) v %.3f on %d leaf %d\n", x, y, z, t.getValue(c), int(t.isValueOn(c)),
                int(t.probeConstLeaf(c) != nullptr));
  }
}

uint64_t Clay::hash() const {
  uint64_t h = 1469598103934665603ull;
  auto mix = [&](const void* p, size_t n) {
    const auto* c = static_cast<const unsigned char*>(p);
    for (size_t i = 0; i < n; ++i) {
      h ^= c[i];
      h *= 1099511628211ull;
    }
  };
  for (auto it = grid_->tree().cbeginLeaf(); it; ++it) {
    const Coord o = it->origin();
    mix(o.data(), sizeof(int) * 3);
    mix(it->buffer().data(), sizeof(float) * Leaf::SIZE);
    const auto& m = it->getValueMask();
    for (openvdb::Index w = 0; w < Leaf::NodeMaskType::WORD_COUNT; ++w) {
      const auto word = m.template getWord<openvdb::Index64>(w);
      mix(&word, sizeof(word));
    }
  }
  return h;
}

size_t Clay::memory_bytes() const { return size_t(grid_->memUsage()); }
size_t Clay::active_voxels() const { return size_t(grid_->activeVoxelCount()); }

bool Clay::save(const std::string& path) const {
  try {
    openvdb::io::File f(path);
    f.setCompression(openvdb::io::COMPRESS_NONE);
    f.write({grid_});
    f.close();
    return true;
  } catch (const std::exception& e) {
    std::fprintf(stderr, "clay: save %s failed: %s\n", path.c_str(), e.what());
    return false;
  }
}

bool Clay::load(const std::string& path) {
  try {
    openvdb::io::File f(path);
    f.open(false);
    auto g = openvdb::gridPtrCast<openvdb::FloatGrid>(f.readGrid("clay"));
    f.close();
    if (!g) return false;
    grid_ = g;
    voxel_ = float(grid_->voxelSize()[0]);
    dirty_.clear();
    return true;
  } catch (const std::exception& e) {
    std::fprintf(stderr, "clay: load %s failed: %s\n", path.c_str(), e.what());
    return false;
  }
}

namespace {
const char* kOpNames[] = {"add", "carve", "smooth", "pull", "flatten", "crease"};
}

std::string to_line(const Step& s) {
  const char* op = kOpNames[int(s.op)];
  char buf[640];
  if (s.kind == Kind::Piece)
    std::snprintf(buf, sizeof buf, "piece %s %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d", op, s.a.x, s.a.y, s.a.z,
                  s.b.x, s.b.y, s.b.z, s.radius, s.blend, int(s.mirror));
  else
    std::snprintf(buf, sizeof buf, "stamp %s %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d %.9g %.9g %.9g %u %d", op,
                  s.a.x, s.a.y, s.a.z, s.n.x, s.n.y, s.n.z, s.radius, s.strength, int(s.mirror), s.b.x, s.b.y, s.b.z,
                  s.stroke, int(s.accumulate));
  return buf;
}

bool from_line(const std::string& line, Step& s) {
  std::istringstream in(line);
  std::string kind, op;
  float f[8];
  int m = 0;
  if (!(in >> kind >> op)) return false;
  for (float& x : f) {
    std::string t;
    if (!(in >> t)) return false;
    x = std::strtof(t.c_str(), nullptr);
  }
  if (!(in >> m)) return false;
  s = Step{};
  if (kind == "piece") s.kind = Kind::Piece;
  else if (kind == "stamp") s.kind = Kind::Stamp;
  else return false;
  int found = -1;
  for (int i = 0; i < 6; ++i)
    if (op == kOpNames[i]) found = i;
  if (found < 0) return false;
  s.op = Op(found);
  s.a = {f[0], f[1], f[2]};
  if (s.kind == Kind::Piece) {
    s.b = {f[3], f[4], f[5]};
    s.blend = f[7];
  } else {
    s.n = {f[3], f[4], f[5]};
    s.strength = f[7];
  }
  s.radius = f[6];
  s.mirror = m != 0;
  if (s.kind == Kind::Stamp) {  // b and the stroke id (absent in part 1's files)
    float bb[3];
    unsigned id = 0;
    if (in >> bb[0] >> bb[1] >> bb[2] >> id) {
      s.b = {bb[0], bb[1], bb[2]};
      s.stroke = id;
      int acc = 1;
      if (in >> acc) s.accumulate = acc != 0;
    }
  }
  return true;
}

}  // namespace clay
