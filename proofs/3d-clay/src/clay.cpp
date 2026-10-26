#include "clay.h"

#include <openvdb/io/File.h>
#include <tbb/blocked_range.h>
#include <tbb/parallel_for.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <sstream>

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

// A box of the grid seen as 8^3 chunks (x fastest inside the buffers). lo is 8-aligned, sizes are multiples of 8.
// Only the chunks a step lists are ever filled or read; the buffers are kept between steps and never cleared.
struct Box {
  Coord lo;
  int nx = 0, ny = 0, nz = 0, cnx = 0, cny = 0, cnz = 0;
  size_t size() const { return size_t(nx) * ny * nz; }
  int chunks() const { return cnx * cny * cnz; }
  size_t at(int x, int y, int z) const { return size_t(x) + size_t(nx) * (size_t(y) + size_t(ny) * z); }
  void corner(int ci, int& x, int& y, int& z) const {
    x = 8 * (ci % cnx);
    y = 8 * ((ci / cnx) % cny);
    z = 8 * (ci / (cnx * cny));
  }
  template <class F> void each(int ci, F&& f) const {  // f(x, y, z, index) over the chunk's voxels
    int x0, y0, z0;
    corner(ci, x0, y0, z0);
    for (int z = z0; z < z0 + 8; ++z)
      for (int y = y0; y < y0 + 8; ++y) {
        size_t i = at(x0, y, z);
        for (int x = x0; x < x0 + 8; ++x, ++i) f(x, y, z, i);
      }
  }
  void copy(int ci, const float* src, float* dst) const {
    int x0, y0, z0;
    corner(ci, x0, y0, z0);
    for (int z = z0; z < z0 + 8; ++z)
      for (int y = y0; y < y0 + 8; ++y) std::memcpy(dst + at(x0, y, z), src + at(x0, y, z), 8 * sizeof(float));
  }
};

template <class F> void par(const std::vector<int>& list, F&& f) {
  tbb::parallel_for(tbb::blocked_range<size_t>(0, list.size(), 2), [&](const tbb::blocked_range<size_t>& r) {
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
// eikonal), up to `width`, keeping their sign. Unknown voxels of `ext` start at the width; only `work` is updated
// (work is inside ext, and ext reaches one chunk past work, so every neighbour read is a filled voxel).
void relevel(const Box& b, std::vector<float>& v, std::vector<float>& next, const std::vector<uint8_t>& fixed,
             float width, const std::vector<int>& ext, const std::vector<int>& work) {
  par(ext, [&](int ci) {
    b.each(ci, [&](int, int, int, size_t i) {
      if (!fixed[i]) v[i] = sgn(v[i]) * width;
    });
    b.copy(ci, v.data(), next.data());
  });
  if (work.empty()) return;
  const size_t sy = size_t(b.nx), sz = size_t(b.nx) * b.ny;
  const int passes = int(std::ceil(width)) + 1;
  for (int pass = 0; pass < passes; ++pass) {
    const float* cur = v.data();
    float* out = next.data();
    par(work, [&](int ci) {
      b.each(ci, [&](int x, int y, int z, size_t i) {
        if (fixed[i]) return;
        const float big = width;
        const float ax = std::min(x > 0 ? std::fabs(cur[i - 1]) : big, x < b.nx - 1 ? std::fabs(cur[i + 1]) : big);
        const float ay = std::min(y > 0 ? std::fabs(cur[i - sy]) : big, y < b.ny - 1 ? std::fabs(cur[i + sy]) : big);
        const float az = std::min(z > 0 ? std::fabs(cur[i - sz]) : big, z < b.nz - 1 ? std::fabs(cur[i + sz]) : big);
        const float u = std::min(eikonal(ax, ay, az), std::fabs(cur[i]));
        out[i] = sgn(cur[i]) * std::min(u, width);
      });
    });
    // fixed voxels and chunks not in `work` never change, so after the swap both buffers agree on them
    v.swap(next);
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

}  // namespace

struct Clay::Scratch {
  std::vector<float> v, before, after, next;
  std::vector<uint8_t> fixed;
  void fit(size_t n) {
    if (v.size() >= n) return;
    v.resize(n);
    before.resize(n);
    after.resize(n);
    next.resize(n);
    fixed.resize(n);
  }
};

Clay::~Clay() = default;

Clay::Clay(float voxel) : voxel_(voxel), scratch_(std::make_unique<Scratch>()) {
  std::call_once(g_init, [] { openvdb::initialize(); });
  grid_ = openvdb::FloatGrid::create(kBand);
  grid_->setTransform(openvdb::math::Transform::createLinearTransform(voxel));
  grid_->setGridClass(openvdb::GRID_LEVEL_SET);
  grid_->setName("clay");
}


StepTiming Clay::apply(const Step& s) {
  const auto t0 = std::chrono::steady_clock::now();
  Scratch& S = *scratch_;
  const float iv = 1.0f / voxel_;
  auto vox = [&](V3 p) { return V3{p.x * iv, p.y * iv, p.z * iv}; };

  // the shapes (voxel units), mirrored copy included
  std::vector<Shape> shapes;
  const float r = s.radius * iv;
  const bool piece = s.kind == Kind::Piece;
  shapes.push_back({vox(s.a), piece ? vox(s.b) : vox(s.a), r});
  if (s.mirror) shapes.push_back({vox(mirror_x(s.a)), piece ? vox(mirror_x(s.b)) : vox(mirror_x(s.a)), r});
  const float k = s.blend * iv;
  const float disp = std::min(s.strength * r * 0.15f, kDispCap);
  // how far the step reaches, and how wide the distances must be before it (a blend reads them up to k past the band;
  // a dab moves the surface less than the trusted band, so it needs nothing wider)
  const float reach = piece ? r + k + kBand + 1 : r + kBand + 1;
  const float wpre = (piece && k > 0) ? kBand + k + 1.5f : 0.0f;
  const int rch = int(std::ceil(std::max(wpre, kBand) / 8.0f));  // chunks the re-levelling reaches
  float lo[3] = {1e30f, 1e30f, 1e30f}, hi[3] = {-1e30f, -1e30f, -1e30f};
  for (const Shape& sh : shapes) {
    lo[0] = std::min({lo[0], sh.a.x - reach, sh.b.x - reach});
    lo[1] = std::min({lo[1], sh.a.y - reach, sh.b.y - reach});
    lo[2] = std::min({lo[2], sh.a.z - reach, sh.b.z - reach});
    hi[0] = std::max({hi[0], sh.a.x + reach, sh.b.x + reach});
    hi[1] = std::max({hi[1], sh.a.y + reach, sh.b.y + reach});
    hi[2] = std::max({hi[2], sh.a.z + reach, sh.b.z + reach});
  }
  const int ring = 8 * (rch + 1);
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
  const std::vector<uint8_t> near = dilate(leaf, b.cnx, b.cny, b.cnz, 1);

  // B. the chunks the step works on, and the ones it turns into one value (wholly inside a piece)
  const int rc = ring / 8;
  const float hd = 6.1f;  // a chunk's centre to its farthest voxel
  std::vector<uint8_t> work(nch, 0);
  std::vector<int8_t> whole(nch, 0);  // -1 / +1: becomes all inside / all outside
  tbb::parallel_for(0, nch, [&](int ci) {
    const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
    if (cx < rc || cy < rc || cz < rc || cx >= b.cnx - rc || cy >= b.cny - rc || cz >= b.cnz - rc) return;
    const V3 c{b.lo.x() + 8.0f * cx + 3.5f, b.lo.y() + 8.0f * cy + 3.5f, b.lo.z() + 8.0f * cz + 3.5f};
    if (piece) {
      float d = 1e30f;
      for (const Shape& sh : shapes) d = std::min(d, seg_dist(c, sh.a, sh.b) - sh.r);
      if (d < -(hd + kBand + 1)) {
        const float target = s.op == Op::Add ? -kBand : kBand;
        if (leaf[ci] || uval[ci] != target) whole[ci] = s.op == Op::Add ? -1 : 1;
      } else if (d < hd + k + kBand + 1) {
        work[ci] = 1;
      }
    } else {
      float d = 1e30f;
      for (const Shape& sh : shapes) d = std::min(d, seg_dist(c, sh.a, sh.a));
      if (near[ci] && d < r + hd + kBand + 1) work[ci] = 1;
    }
  });
  const std::vector<int> workList = listed(work);
  const std::vector<uint8_t> pre = wpre > 0 ? dilate(work, b.cnx, b.cny, b.cnz, rch) : work;
  const std::vector<int> preList = listed(pre);
  const std::vector<int> extList = listed(dilate(pre, b.cnx, b.cny, b.cnz, 1));

  // C. fill the listed chunks from the grid
  std::vector<float>& V = S.v;
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
  });

  // D. widen the distances to what a blend reads (the stored band is trusted)
  if (wpre > 0) {
    par(extList, [&](int ci) {
      b.each(ci, [&](int, int, int, size_t i) { S.fixed[i] = std::fabs(S.v[i]) < kBand - 0.5f; });
    });
    relevel(b, S.v, S.next, S.fixed, wpre, extList, preList);
  }

  // E. the step
  par(extList, [&](int ci) { b.copy(ci, S.v.data(), S.before.data()); });
  const std::vector<float>& before = S.before;
  const size_t sy = size_t(b.nx), sz = size_t(b.nx) * b.ny;
  par(extList, [&](int ci) {
    b.each(ci, [&](int x, int y, int z, size_t i) {
      const V3 p{float(b.lo.x() + x), float(b.lo.y() + y), float(b.lo.z() + z)};
      const float old = before[i];
      if (piece) {
        float d = 1e30f;
        for (const Shape& sh : shapes) d = std::min(d, seg_dist(p, sh.a, sh.b) - sh.r);
        if (s.op == Op::Add) S.v[i] = smin(old, d, k);
        else if (s.op == Op::Carve) S.v[i] = -smin(-old, d, k);
        return;
      }
      float w = 0;
      for (const Shape& sh : shapes) {
        const float dx = p.x - sh.a.x, dy = p.y - sh.a.y, dz = p.z - sh.a.z;
        w = std::max(w, falloff(std::sqrt(dx * dx + dy * dy + dz * dz) / sh.r));
      }
      if (w <= 0) return;
      if (s.op == Op::Add) S.v[i] = old - disp * w;
      else if (s.op == Op::Carve) S.v[i] = old + disp * w;
      else {
        const float avg =
            (before[i - 1] + before[i + 1] + before[i - sy] + before[i + sy] + before[i - sz] + before[i + sz]) / 6.0f;
        S.v[i] = old + 0.6f * s.strength * w * (avg - old);
      }
    });
  });

  // F. back to the stored band: unchanged band voxels stay, changed ones next to the surface are seeded from where
  //    the surface crosses their edges (1/d^2 = sum of 1/d_axis^2), the rest is re-levelled
  par(extList, [&](int ci) { b.copy(ci, S.v.data(), S.after.data()); });
  const std::vector<float>& after = S.after;
  par(extList, [&](int ci) {
    b.each(ci, [&](int x, int y, int z, size_t i) {
      const float v = after[i];
      uint8_t f = 0;
      if (v == before[i]) {
        f = std::fabs(v) < kBand - 1.0f;
      } else if (x > 0 && y > 0 && z > 0 && x < b.nx - 1 && y < b.ny - 1 && z < b.nz - 1) {
        if (v == 0.0f) {
          f = 1;
        } else {
          float inv = 0;
          const size_t st[3] = {1, sy, sz};
          for (int ax = 0; ax < 3; ++ax) {
            float best = 2.0f;
            for (int sg = -1; sg <= 1; sg += 2) {
              const float nb = after[sg < 0 ? i - st[ax] : i + st[ax]];
              if ((nb < 0) != (v < 0)) best = std::min(best, std::fabs(v) / (std::fabs(v) + std::fabs(nb)));
            }
            if (best < 2.0f) inv += 1.0f / std::max(best * best, 1e-12f);
          }
          if (inv > 0) {
            S.v[i] = sgn(v) * (1.0f / std::sqrt(inv));
            f = 2;
          }
        }
      }
      S.fixed[i] = f;
    });
  });
  relevel(b, S.v, S.next, S.fixed, kBand, extList, workList);

  // G. write back: worked chunks (uniform ones become tiles), and the chunks a piece filled or emptied
  std::vector<int8_t> cls(nch, 2);  // +1 all outside, -1 all inside, 0 mixed, 2 not written
  par(workList, [&](int ci) {
    bool allOut = true, allIn = true;
    b.each(ci, [&](int, int, int, size_t i) {
      allOut &= S.v[i] >= kBand;
      allIn &= S.v[i] <= -kBand;
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
      leaves[ci] = tree.touchLeaf(o);
      mixed.push_back(ci);
    } else {
      const float val = cls[ci] * kBand;
      if (!leaf[ci] && uval[ci] == val) continue;  // already that tile: nothing changed here
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
      const float v = S.v[i];
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

  // a big piece's box can be hundreds of MB: give it back rather than keep it for the next dab
  if (b.size() > (size_t(16) << 20)) *scratch_ = Scratch{};

  StepTiming t;
  t.voxels = workList.size() * 512;
  t.ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  return t;
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
  for (auto it = grid_->tree().cbeginValueAll(); it; ++it) {
    if (!it.isTileValue()) continue;
    const Coord c = it.getCoord();
    const float v = *it;
    const uint8_t on = it.isValueOn();
    mix(c.data(), sizeof(int) * 3);
    mix(&v, sizeof(v));
    mix(&on, 1);
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

std::string to_line(const Step& s) {
  const char* op = s.op == Op::Add ? "add" : s.op == Op::Carve ? "carve" : "smooth";
  char buf[512];
  if (s.kind == Kind::Piece)
    std::snprintf(buf, sizeof buf, "piece %s %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d", op, s.a.x, s.a.y, s.a.z,
                  s.b.x, s.b.y, s.b.z, s.radius, s.blend, int(s.mirror));
  else
    std::snprintf(buf, sizeof buf, "stamp %s %.9g %.9g %.9g %.9g %.9g %.9g %.9g %.9g %d", op, s.a.x, s.a.y, s.a.z,
                  s.n.x, s.n.y, s.n.z, s.radius, s.strength, int(s.mirror));
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
  if (op == "add") s.op = Op::Add;
  else if (op == "carve") s.op = Op::Carve;
  else if (op == "smooth") s.op = Op::Smooth;
  else return false;
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
  return true;
}

}  // namespace clay
