// Clay: replaying many strokes at once (clay_replay.h).
#include "clay_replay.h"

#include <tbb/concurrent_priority_queue.h>
#include <tbb/parallel_for.h>
#include <tbb/task_arena.h>
#include <tbb/task_group.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <climits>
#include <cmath>
#include <functional>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <thread>
#include <unordered_map>
#include <utility>

#include "clay_box.h"
#include "clay_coarse.h"

namespace r3d::clay {

using namespace detail;

namespace {

constexpr int kKeyOff = 1 << 20;  // chunk indices -2^20 .. 2^20 (a clay 8.4 million grains across)

// a chunk by its index (origin / 8), packed into one number
uint64_t chunk_key(int x, int y, int z) {
  return (uint64_t(uint32_t(x + kKeyOff)) << 42) | (uint64_t(uint32_t(y + kKeyOff)) << 21) |
         uint64_t(uint32_t(z + kKeyOff));
}

// The chunks a stroke may write and the ones it may read, by key. Volume::run writes only chunks whose centre is
// within (a dab's reach + 6.1, a chunk's centre to its farthest voxel) of a dab or its mirrored copy; it reads those
// and the chunks within 2 of them (nearLeaf looks 2 chunks out for a unit of several dabs, the fill and the band 1).
// One voxel to spare on the reach, so float rounding never leaves a chunk out.
struct Footprint {
  std::vector<uint64_t> write, read;
};

// A stroke with a big dab (clay_coarse.h) may run some units on the coarse copy: then every dab is given the coarse
// reach and read ring, which hold the fine ones (more than it needs, never less).
Footprint footprint(const std::vector<Step>& dabs, float iv) {
  struct Ball {
    V3 c;
    float lim;
  };
  bool coarse = false;
  for (const Step& s : dabs) coarse |= coarse_dab(s, iv);
  const int ringR = coarse ? kCoarseReadRing : 2;
  std::vector<Ball> balls;
  for (const Step& s : dabs) {
    const float r = s.radius * iv, sh = dab_shift(s, iv);
    const float lim = coarse ? coarse_write_reach(r, sh) : r + kBand + 1 + sh + 6.1f + 1.0f;
    const V3 c{s.a.x * iv, s.a.y * iv, s.a.z * iv};
    balls.push_back({c, lim});
    if (s.mirror) balls.push_back({V3{-c.x, c.y, c.z}, lim});
  }
  Footprint f;
  if (balls.empty()) return f;
  auto range = [](float c, float lim, int& lo, int& hi) {  // chunk indices that may hold a centre within lim of c
    lo = floor_div(int(std::floor(c - lim)), 8);
    hi = floor_div(int(std::floor(c + lim)), 8);
  };
  int lo[3] = {INT_MAX, INT_MAX, INT_MAX}, hi[3] = {INT_MIN, INT_MIN, INT_MIN};
  for (const Ball& b : balls) {
    const float c[3] = {b.c.x, b.c.y, b.c.z};
    for (int a = 0; a < 3; ++a) {
      int l, h;
      range(c[a], b.lim, l, h);
      lo[a] = std::min(lo[a], l - ringR);  // room for the read ring
      hi[a] = std::max(hi[a], h + ringR);
    }
  }
  const int nx = hi[0] - lo[0] + 1, ny = hi[1] - lo[1] + 1, nz = hi[2] - lo[2] + 1;
  std::vector<uint8_t> w(size_t(nx) * ny * nz, 0);
  for (const Ball& b : balls) {
    int x0, x1, y0, y1, z0, z1;
    range(b.c.x, b.lim, x0, x1);
    range(b.c.y, b.lim, y0, y1);
    range(b.c.z, b.lim, z0, z1);
    const float ll = b.lim * b.lim;
    for (int z = z0; z <= z1; ++z)
      for (int y = y0; y <= y1; ++y)
        for (int x = x0; x <= x1; ++x) {
          const V3 e = vsub(V3{8.0f * x + 3.5f, 8.0f * y + 3.5f, 8.0f * z + 3.5f}, b.c);
          if (vdot(e, e) < ll) w[size_t(x - lo[0]) + size_t(nx) * (size_t(y - lo[1]) + size_t(ny) * (z - lo[2]))] = 1;
        }
  }
  const std::vector<uint8_t> r = dilate(w, nx, ny, nz, ringR);
  for (int z = 0; z < nz; ++z)
    for (int y = 0; y < ny; ++y)
      for (int x = 0; x < nx; ++x) {
        const size_t i = size_t(x) + size_t(nx) * (size_t(y) + size_t(ny) * z);
        if (!r[i]) continue;
        const uint64_t k = chunk_key(x + lo[0], y + lo[1], z + lo[2]);
        f.read.push_back(k);
        // a coarse stroke counts all it reads as written: a later stroke writing a chunk in its wide ring then waits
        // for it (that later stroke's own, narrower ring might not reach back to the coarse stroke's writes)
        if (w[i] || coarse) f.write.push_back(k);
      }
  return f;
}

double ms_since(std::chrono::steady_clock::time_point t0) {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

}  // namespace

ReplayStats replay_strokes(Volume& v, const std::vector<std::vector<Step>>& strokes) {
  const auto t0 = std::chrono::steady_clock::now();
  const size_t n = strokes.size();
  const float iv = 1.0f / v.voxel();
  ReplayStats st;
  st.strokes = n;
  for (const auto& s : strokes) st.dabs += s.size();
  if (n == 0) return st;

  std::vector<Footprint> fp(n);
  tbb::parallel_for(size_t(0), n, [&](size_t j) { fp[j] = footprint(strokes[j], iv); });

  // Who waits for whom: a stroke waits for the last earlier stroke that wrote each chunk it reads. That covers every
  // earlier stroke it touches: an earlier writer of the same chunk is itself waited for by the last one, and a stroke
  // that reads what this one writes wrote a chunk within 2 of it, which this one reads (a coarse stroke, whose ring is
  // 4, counts its whole ring as written, so the stroke writing in it reads one of those).
  std::vector<std::vector<uint32_t>> next(n);
  std::unique_ptr<std::atomic<int>[]> waiting(new std::atomic<int>[n]);
  std::vector<uint32_t> roots, depth(n, 1);
  {
    std::unordered_map<uint64_t, uint32_t> last;
    std::vector<uint32_t> before;
    for (size_t j = 0; j < n; ++j) {
      before.clear();
      for (uint64_t k : fp[j].read) {
        const auto it = last.find(k);
        if (it != last.end()) before.push_back(it->second);
      }
      std::sort(before.begin(), before.end());
      before.erase(std::unique(before.begin(), before.end()), before.end());
      waiting[j].store(int(before.size()));
      for (uint32_t i : before) {
        next[i].push_back(uint32_t(j));
        depth[j] = std::max(depth[j], depth[i] + 1);
      }
      if (before.empty()) roots.push_back(uint32_t(j));
      for (uint64_t k : fp[j].write) last[k] = uint32_t(j);
      std::vector<uint64_t>().swap(fp[j].write);
    }
  }
  st.chain = *std::max_element(depth.begin(), depth.end());
  for (auto& f : fp) std::vector<uint64_t>().swap(f.read);

  // Longest chain first: each stroke's weight is its work (dabs, twice when mirrored) plus the heaviest chain of
  // strokes waiting on it. Ready strokes run heaviest first, so the strokes everything else waits for never sit
  // behind ones nothing waits for.
  std::vector<double> chainW(n, 0);
  for (size_t j = n; j-- > 0;) {
    double after = 0;
    for (uint32_t k : next[j]) after = std::max(after, chainW[k]);
    const Step* first = strokes[j].empty() ? nullptr : &strokes[j][0];
    chainW[j] = double(strokes[j].size()) * (first && first->mirror ? 2.0 : 1.0) + after;
  }

  // Strokes write straight into `v`: the grid is read under a shared lock and written under the unique one (a
  // stroke's chunks are never touched by a stroke running at the same time, so it reads them as a serial replay
  // would). Mask chunks go with them (they are in the same grid's volume, under the same lock). Step buffers come
  // from a pool, so a stroke doesn't allocate and fault in fresh ones. Each stroke runs isolated: while its own
  // parallel loops wait, its thread never starts another stroke (which would take the lock it holds).
  std::shared_mutex gridLock;
  std::mutex poolLock;
  std::vector<std::unique_ptr<Buffers>> pool;
  auto take = [&] {
    std::lock_guard<std::mutex> g(poolLock);
    if (pool.empty()) return std::make_unique<Buffers>();
    std::unique_ptr<Buffers> b = std::move(pool.back());
    pool.pop_back();
    return b;
  };
  auto give = [&](std::unique_ptr<Buffers> b) {
    std::lock_guard<std::mutex> g(poolLock);
    pool.push_back(std::move(b));
  };
  tbb::concurrent_priority_queue<std::pair<double, int64_t>> ready;  // (weight, -index): heaviest, then earliest
  tbb::task_group tg;
  std::function<void()> runOne;
  auto push = [&](uint32_t j) {
    ready.push({chainW[j], -int64_t(j)});
    tg.run([&runOne] { runOne(); });  // one task per ready stroke; it runs the heaviest ready one
  };
  runOne = [&] {
    std::pair<double, int64_t> top;
    while (!ready.try_pop(top)) std::this_thread::yield();  // (never empty here: one task per push)
    const uint32_t j = uint32_t(-top.second);
    std::unique_ptr<Buffers> bufs = take();
    tbb::this_task_arena::isolate([&] { v.apply_stroke_shared(strokes[j], *bufs, gridLock); });
    give(std::move(bufs));
    for (uint32_t k : next[j])
      if (waiting[k].fetch_sub(1) == 1) push(k);
  };
  for (uint32_t j : roots) push(j);
  tg.wait();
  st.ms = ms_since(t0);
  return st;
}

}  // namespace r3d::clay
