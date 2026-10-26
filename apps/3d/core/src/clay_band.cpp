// Clay: one unit of dabs over the narrow band (clay_box.h DabUnit). Each dab works on a list: the band voxels in its
// reach plus the 2 voxels the band can grow by; their 6 neighbours are found once, and the re-levelling passes run on
// compact arrays. Moved from proofs/3d-clay (clay.cpp, Clay::run's stroke part, part 3).
#include <algorithm>
#include <cmath>
#include <vector>

#include "clay_box.h"

namespace r3d::clay::detail {

void run_dabs(const DabUnit& du) {
  const Box& b = *du.b;
  float* V = du.V;
  float* NX = du.NX;
  const float* St = du.St;
  const Step* steps = du.steps;
  const size_t n = du.n;
  const auto& dabShapes = *du.shapes;
  const auto& reachOf = *du.reach;
  const auto& shift = *du.shift;
  const auto& leaf = *du.leaf;
  const auto& work = *du.work;
  const auto& extList = *du.extList;
  auto& touched = *du.touched;
  const int nch = b.chunks();
  const float hd = 6.1f;  // a chunk's centre to its farthest voxel
  auto centre = [&](int ci) {
    const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
    return V3{b.lo.x() + 8.0f * cx + 3.5f, b.lo.y() + 8.0f * cy + 3.5f, b.lo.z() + 8.0f * cz + 3.5f};
  };
  auto dab_reaches = [&](size_t j, V3 c) {
    for (const DabShape& d : dabShapes[j]) {
      const V3 e = vsub(c, d.c);
      const float lim = reachOf[j] + hd;
      if (vdot(e, e) < lim * lim) return true;
    }
    return false;
  };
  const auto P = [&](int x, int y, int z) { return V3{float(b.lo.x() + x), float(b.lo.y() + y), float(b.lo.z() + z)}; };

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
    // the dab's chunks: in its reach and next to a chunk that holds the band now (the surface moves during a
    // stroke, so this follows it); and those plus their neighbours, for reading around a voxel
    std::vector<int> mine, around;
    for (int ci : extList) {
      if (!work[ci] || !dab_reaches(j, centre(ci))) continue;
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
    overK([&](size_t k) { V[L[k].i] = curL[k]; });
    for (size_t k = 0; k < K; ++k)  // which chunks hold the band now (a hint for the next dab: it only grows)
      if (std::fabs(curL[k]) < kBand) hot[L[k].i / 512] = 1;
  }
}

}  // namespace r3d::clay::detail
