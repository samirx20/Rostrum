// Clay: big brushes on a coarser copy of the band (clay_coarse.h).
#include "clay_coarse.h"

#include <tbb/parallel_for.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <vector>

namespace r3d::clay::detail {

namespace {

constexpr float kEdge = 0.5f * kBand;  // the fine band's edge, in coarse grains

// a fine grain's distance as the coarse copy holds it: halved on the band, "far" off it
inline float to_coarse(float v) { return std::fabs(v) < kBand ? 0.5f * v : sgn(v) * kBand; }
inline float to_edge(float c) { return std::min(kEdge, std::max(-kEdge, c)); }

// The 8 fine chunks under one coarse chunk (sub = bit 0 x, bit 1 y, bit 2 z): a leaf's values, or one value
struct Under {
  const float* d[8];
  float val[8];
};
inline int sub_of(int lx, int ly, int lz) { return (lx >> 2) | ((ly >> 2) << 1) | ((lz >> 2) << 2); }
inline Coord twice(const Coord& c) { return Coord(2 * c.x(), 2 * c.y(), 2 * c.z()); }
inline Coord sub_origin(const Coord& fine, int s) { return fine + Coord(8 * (s & 1), 8 * ((s >> 1) & 1), 8 * (s >> 2)); }

}  // namespace

void run_coarse(CoarseUnit& u) {
  const size_t n = u.n;
  const Step* steps = u.steps;
  Buffers& S = *u.bufs;
  Tree& tree = *u.tree;

  // the shapes at the coarse grain (positions, radii, shifts and Pull's vector halved; normals and Crease's direction
  // as they are)
  std::vector<std::vector<DabShape>> shapes(n);
  std::vector<float> shift(n, 0), reach(n, 0);
  for (size_t j = 0; j < n; ++j) {
    for (const DabShape& d : (*u.shapes)[j])
      shapes[j].push_back({mul(d.c, 0.5f), d.n, steps[j].op == Op::Pull ? mul(d.b, 0.5f) : d.b, 0.5f * d.r});
    shift[j] = 0.5f * (*u.shift)[j];
    reach[j] = shapes[j][0].r + kBand + 1 + shift[j];
  }

  // the coarse box, as Volume::run makes a fine one
  const int nearR = n > 1 ? 2 : 1;
  float lo[3] = {1e30f, 1e30f, 1e30f}, hi[3] = {-1e30f, -1e30f, -1e30f};
  for (size_t j = 0; j < n; ++j)
    for (const DabShape& d : shapes[j]) {
      const float r = reach[j];
      lo[0] = std::min(lo[0], d.c.x - r), lo[1] = std::min(lo[1], d.c.y - r), lo[2] = std::min(lo[2], d.c.z - r);
      hi[0] = std::max(hi[0], d.c.x + r), hi[1] = std::max(hi[1], d.c.y + r), hi[2] = std::max(hi[2], d.c.z + r);
    }
  const int ring = 8 * (std::max(1, nearR) + 1);
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
  float* O = S.orig.get();   // the copy before the dabs
  float* D = S.after.get();  // the change (touched chunks only)
  float* St = S.start.get();
  const int nch = b.chunks();
  auto origin = [&](int ci) {
    int x, y, z;
    b.corner(ci, x, y, z);
    return b.lo + Coord(x, y, z);
  };
  bool needStart = false;
  for (size_t j = 0; j < n; ++j) needStart |= !steps[j].accumulate;

  std::vector<uint8_t> leaf(nch), work(nch, 0), touched(nch, 0), maskTouched(nch, 0);
  std::vector<int> extList;
  float* M = nullptr;
  {
    GridLock<true> rl(u.lock);
    // A. the fine chunks under each coarse chunk; a coarse chunk "holds a leaf" when one of them does (or they differ)
    std::vector<Under> under(nch);
    tbb::parallel_for(0, nch, [&](int ci) {
      const Coord f = twice(origin(ci));
      Under& w = under[ci];
      bool any = false;
      for (int s = 0; s < 8; ++s) {
        const Coord o = sub_origin(f, s);
        const Leaf* l = tree.probeConstLeaf(o);
        w.d[s] = l ? l->buffer().data() : nullptr;
        w.val[s] = l ? 0.0f : tree.getValue(o);
        any |= l != nullptr || w.val[s] != w.val[0];
      }
      leaf[ci] = any;
    });
    const std::vector<uint8_t> nearLeaf = dilate(leaf, b.cnx, b.cny, b.cnz, nearR);

    // B. the coarse chunks the dabs work on
    const int rc = ring / 8;
    const float hd = 6.1f;
    tbb::parallel_for(0, nch, [&](int ci) {
      const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
      if (cx < rc || cy < rc || cz < rc || cx >= b.cnx - rc || cy >= b.cny - rc || cz >= b.cnz - rc) return;
      if (!nearLeaf[ci]) return;
      const V3 c{b.lo.x() + 8.0f * cx + 3.5f, b.lo.y() + 8.0f * cy + 3.5f, b.lo.z() + 8.0f * cz + 3.5f};
      for (size_t j = 0; j < n && !work[ci]; ++j)
        for (const DabShape& d : shapes[j]) {
          const V3 e = vsub(c, d.c);
          const float lim = reach[j] + hd;
          if (vdot(e, e) < lim * lim) work[ci] = 1;
        }
    });
    extList = listed(dilate(work, b.cnx, b.cny, b.cnz, 1));

    // C. the copy: values (and where the stroke began, for strokes without accumulate)
    par(extList, [&](int ci) {
      const Under& w = under[ci];
      b.each(ci, [&](int x, int y, int z, size_t i) {
        const int lx = x & 7, ly = y & 7, lz = z & 7, s = sub_of(lx, ly, lz);
        V[i] = to_coarse(w.d[s] ? w.d[s][leaf_offset(2 * lx, 2 * ly, 2 * lz)] : w.val[s]);
      });
      if (!needStart) return;
      const Coord f = twice(origin(ci));
      const ChunkRecord::Chunk* kept[8];
      for (int s = 0; s < 8; ++s) kept[s] = u.start ? u.start->find(sub_origin(f, s)) : nullptr;
      b.each(ci, [&](int x, int y, int z, size_t i) {
        const int lx = x & 7, ly = y & 7, lz = z & 7, s = sub_of(lx, ly, lz);
        const ChunkRecord::Chunk* k = kept[s];
        if (!k) St[i] = V[i];
        else St[i] = to_coarse(k->leaf ? k->values[leaf_offset(2 * lx, 2 * ly, 2 * lz)] : k->value);
      });
    });

    // the mask, where there is some in the copy (decided from these chunks alone: the same in a live stroke and in
    // any replay; with none, the dabs run as on a clay without a mask, which gives the same values)
    if (u.mask) {
      std::vector<uint8_t> has(extList.size(), 0);
      tbb::parallel_for(size_t(0), extList.size(), [&](size_t k) {
        const Coord f = twice(origin(extList[k]));
        for (int s = 0; s < 8 && !has[k]; ++s) has[k] = u.mask->probeConstLeaf(sub_origin(f, s)) != nullptr;
      });
      if (std::find(has.begin(), has.end(), uint8_t(1)) != has.end()) {
        M = S.mask.get();
        par(extList, [&](int ci) {
          const Coord f = twice(origin(ci));
          const float* md[8];
          for (int s = 0; s < 8; ++s) {
            const Leaf* l = u.mask->probeConstLeaf(sub_origin(f, s));
            md[s] = l ? l->buffer().data() : nullptr;
          }
          b.each(ci, [&](int x, int y, int z, size_t i) {
            const int lx = x & 7, ly = y & 7, lz = z & 7, s = sub_of(lx, ly, lz);
            M[i] = md[s] ? md[s][leaf_offset(2 * lx, 2 * ly, 2 * lz)] : 0.0f;
          });
        });
      }
    }
  }

  // E. the dabs on the copy, exactly as fine dabs run (clay_band.cpp)
  par(extList, [&](int ci) { b.copy(ci, V, O); });
  DabUnit du;
  du.b = &b;
  du.V = V;
  du.NX = NX;
  du.St = St;
  du.steps = steps;
  du.n = n;
  du.shapes = &shapes;
  du.reach = &reach;
  du.shift = &shift;
  du.leaf = &leaf;
  du.work = &work;
  du.extList = &extList;
  du.touched = &touched;
  du.M = M;
  du.maskTouched = &maskTouched;
  run_dabs(du);

  // F. the change, clamped to the fine band's edge on both sides (beyond it the fine grains are "far" either way)
  const std::vector<int> touchedList = listed(touched);
  par(touchedList, [&](int ci) {
    b.each(ci, [&](int, int, int, size_t i) { D[i] = to_edge(V[i]) - to_edge(O[i]); });
  });
  auto dval = [&](int X, int Y, int Z) -> float {  // the change at coarse grain (X, Y, Z); 0 where there is none
    const int x = X - b.lo.x(), y = Y - b.lo.y(), z = Z - b.lo.z();
    if (x < 0 || y < 0 || z < 0 || x >= b.nx || y >= b.ny || z >= b.nz) return 0.0f;
    if (!touched[(x >> 3) + b.cnx * ((y >> 3) + b.cny * (z >> 3))]) return 0.0f;
    return D[b.at(x, y, z)];
  };
  std::vector<uint8_t> inCopy(nch, 0);  // the coarse chunks the copy holds (their values, re-levelled by the dabs)
  for (int ci : extList) inCopy[ci] = 1;
  auto cval = [&](int X, int Y, int Z, float& v) {  // the coarse distance after the dabs at (X, Y, Z), if the copy has it
    const int x = X - b.lo.x(), y = Y - b.lo.y(), z = Z - b.lo.z();
    if (x < 0 || y < 0 || z < 0 || x >= b.nx || y >= b.ny || z >= b.nz) return false;
    if (!inCopy[(x >> 3) + b.cnx * ((y >> 3) + b.cny * (z >> 3))]) return false;
    v = V[b.at(x, y, z)];
    return true;
  };

  // the fine chunks that read a change: a fine grain x reads coarse grains floor(x / 2) and the next one, so a coarse
  // chunk's change reaches its own 2x2x2 fine chunks and one grain into the chunks below. Fine chunk (i, j, k) of
  // this grid has origin 2 * b.lo + 8 * (i - 1, j - 1, k - 1).
  const int fnx = 2 * b.cnx + 2, fny = 2 * b.cny + 2, fnz = 2 * b.cnz + 2;
  std::vector<uint32_t> reachBits(touchedList.size(), 0);  // per touched coarse chunk: which of its 3^3 fine chunks
  tbb::parallel_for(size_t(0), touchedList.size(), [&](size_t t) {
    const int ci = touchedList[t];
    uint32_t bits = 0;
    b.each(ci, [&](int x, int y, int z, size_t i) {
      if (D[i] == 0.0f) return;
      const int l[3] = {x & 7, y & 7, z & 7};
      int a0[3], a1[3];
      for (int a = 0; a < 3; ++a) a0[a] = floor_div(2 * l[a] - 1, 8), a1[a] = floor_div(2 * l[a] + 1, 8);
      for (int dz = a0[2]; dz <= a1[2]; ++dz)
        for (int dy = a0[1]; dy <= a1[1]; ++dy)
          for (int dx = a0[0]; dx <= a1[0]; ++dx) bits |= 1u << ((dx + 1) + 3 * (dy + 1) + 9 * (dz + 1));
    });
    reachBits[t] = bits;
  });
  std::vector<uint8_t> fineFlag(size_t(fnx) * fny * fnz, 0);
  for (size_t t = 0; t < touchedList.size(); ++t) {
    const int ci = touchedList[t];
    const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
    for (int bit = 0; bit < 27; ++bit)
      if (reachBits[t] & (1u << bit)) {
        const int fx = 2 * cx + 1 + (bit % 3 - 1), fy = 2 * cy + 1 + ((bit / 3) % 3 - 1), fz = 2 * cz + 1 + (bit / 9 - 1);
        fineFlag[size_t(fx) + size_t(fnx) * (size_t(fy) + size_t(fny) * fz)] = 1;
      }
  }
  const std::vector<int> fineList = listed(fineFlag);
  const Coord flo = twice(b.lo) - Coord(8);
  auto fine_origin = [&](int fi) {
    return flo + Coord(8 * (fi % fnx), 8 * ((fi / fnx) % fny), 8 * (fi / (fnx * fny)));
  };

  // G. the fine grains: + twice the interpolated change, clamped to the band
  const size_t nf = fineList.size();
  std::vector<float> out(nf * 512);
  std::vector<int8_t> cls(nf, 2);  // +1 all outside, -1 all inside, 0 mixed, 2 unchanged (not written)
  {
    GridLock<true> rl(u.lock);
    tbb::parallel_for(size_t(0), nf, [&](size_t k) {
      const Coord o = fine_origin(fineList[k]);
      const Leaf* l = tree.probeConstLeaf(o);
      const float* d = l ? l->buffer().data() : nullptr;
      const float tile = l ? 0.0f : tree.getValue(o);
      float* w = &out[k * 512];
      bool changed = false, allOut = true, allIn = true;
      for (int lz = 0; lz < 8; ++lz)
        for (int ly = 0; ly < 8; ++ly)
          for (int lx = 0; lx < 8; ++lx) {
            const int g[3] = {o.x() + lx, o.y() + ly, o.z() + lz};
            int c[3];
            float f[3];
            for (int a = 0; a < 3; ++a) c[a] = floor_div(g[a], 2), f[a] = (g[a] & 1) ? 0.5f : 0.0f;
            float acc = 0.0f, after = 0.0f;
            bool known = true;
            for (int cz = 0; cz < 2; ++cz) {
              const float wz = cz ? f[2] : 1.0f - f[2];
              if (wz == 0.0f) continue;
              for (int cy = 0; cy < 2; ++cy) {
                const float wy = cy ? f[1] : 1.0f - f[1];
                if (wy == 0.0f) continue;
                for (int cx = 0; cx < 2; ++cx) {
                  const float wx = cx ? f[0] : 1.0f - f[0];
                  if (wx == 0.0f) continue;
                  acc += wx * wy * wz * dval(c[0] + cx, c[1] + cy, c[2] + cz);
                  float cv;
                  if (cval(c[0] + cx, c[1] + cy, c[2] + cz, cv)) after += wx * wy * wz * cv;
                  else known = false;
                }
              }
            }
            const int off = leaf_offset(lx, ly, lz);
            const float v = d ? d[off] : tile;
            // a grain near the surface keeps its own detail and moves by the change; one at the band's edge holds no
            // true distance (it was clamped there, "far"), so moving it by the change left a flat shelf of equal
            // values that the next dabs pushed the surface onto, where tiny differences decided it: rough, furry
            // patches under big Add / Carve strokes (CL7). It takes the copy's re-levelled distance instead.
            float nv = v + 2.0f * acc;
            if (acc != 0.0f && std::fabs(v) >= kBand - 1.0f && known) nv = 2.0f * after;
            nv = std::min(kBand, std::max(-kBand, nv));
            w[off] = nv;
            changed |= nv != v;
            allOut &= nv >= kBand;
            allIn &= nv <= -kBand;
          }
      if (changed) cls[k] = allOut ? 1 : allIn ? -1 : 0;
    });
  }

  // H. written back (uniform chunks become tiles), kept first; then the blocks marked
  std::vector<Leaf*> leaves(nf, nullptr);
  std::vector<int> mixed;
  {
    GridLock<false> wl(u.lock);
    for (size_t k = 0; k < nf; ++k) {
      if (cls[k] == 2) continue;
      const Coord o = fine_origin(fineList[k]);
      u.keep(o);
      if (cls[k] == 0) {
        leaves[k] = tree.touchLeaf(o);
        mixed.push_back(int(k));
      } else {
        tree.addTile(1, o, cls[k] * kBand, false);
      }
      ++u.written;
      const int lo[3] = {o[0], o[1], o[2]}, hi[3] = {o[0] + 7, o[1] + 7, o[2] + 7};
      u.dirty(lo, hi);  // per chunk: a mirrored dab's two sides, not the whole box between them (3d-v3)
    }
    par(mixed, [&](int k) {
      Leaf* lf = leaves[k];
      const float* w = &out[size_t(k) * 512];
      for (int off = 0; off < 512; ++off) {
        const float v = w[off];
        if (std::fabs(v) < kBand) lf->setValueOn(off, v);
        else lf->setValueOff(off, sgn(v) * kBand);
      }
    });
  }
}

}  // namespace r3d::clay::detail
