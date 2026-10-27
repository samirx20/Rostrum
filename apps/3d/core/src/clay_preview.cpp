// Clay: the live stroke's coarse preview (clay_preview.h): the coarse copy, and the catch-up thread.
#include "clay_preview.h"

#include <tbb/blocked_range.h>
#include <tbb/parallel_for.h>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <string>
#include <tuple>
#include <vector>

#include "clay_box.h"

#ifdef _WIN32
#include <windows.h>  // SetThreadPriority (NOMINMAX, WIN32_LEAN_AND_MEAN: CMakeLists.txt)
#endif

namespace r3d::clay {

using namespace detail;

bool preview_stroke(const Brush& b, float grain) {
  static const char* env = std::getenv("ROSTRUM3D_CLAY_PREVIEW");
  if (b.op == Op::Mask || grain <= 0) return false;
  if (env && std::strcmp(env, "0") == 0) return false;
  if (env && std::strcmp(env, "1") == 0) return true;
  return b.radius / grain >= kPreviewFrom;
}

namespace {

// a fine grain's distance as the coarse copy holds it: halved on the band, "far" off it (as clay_coarse.cpp)
inline float to_coarse(float v) { return std::fabs(v) < kBand ? 0.5f * v : sgn(v) * kBand; }
inline int sub_of(int lx, int ly, int lz) { return (lx >> 2) | ((ly >> 2) << 1) | ((lz >> 2) << 2); }
inline Coord sub_origin(const Coord& fine, int s) { return fine + Coord(8 * (s & 1), 8 * ((s >> 1) & 1), 8 * (s >> 2)); }
inline Coord coarse_chunk(const Coord& fine) {  // the coarse chunk over a fine one
  return Coord(floor8(floor_div(fine.x(), 2)), floor8(floor_div(fine.y(), 2)), floor8(floor_div(fine.z(), 2)));
}
inline bool coord_less(const Coord& a, const Coord& b) {
  return std::make_tuple(a.x(), a.y(), a.z()) < std::make_tuple(b.x(), b.y(), b.z());
}

// Coarse chunk `c` worked out from `fine`: grain X holds fine grain 2X (`sdf`: as to_coarse; the mask: as it is). Reads
// only the 8 fine chunks under it (leaves, or tiles of any level, or the background).
void coarse_values(const Tree& fine, const Coord& c, float* v, bool sdf) {
  const Coord f(2 * c.x(), 2 * c.y(), 2 * c.z());
  const float* d[8];
  float val[8];
  for (int s = 0; s < 8; ++s) {
    const Coord o = sub_origin(f, s);
    const Leaf* l = fine.probeConstLeaf(o);
    d[s] = l ? l->buffer().data() : nullptr;
    val[s] = l ? 0.0f : fine.getValue(o);
  }
  for (int lx = 0; lx < 8; ++lx)
    for (int ly = 0; ly < 8; ++ly)
      for (int lz = 0; lz < 8; ++lz) {
        const int s = sub_of(lx, ly, lz);
        const float x = d[s] ? d[s][leaf_offset(2 * lx, 2 * ly, 2 * lz)] : val[s];
        v[leaf_offset(lx, ly, lz)] = sdf ? to_coarse(x) : x;
      }
}

// The distances of coarse chunk `c` on the full band. Halved, the fine band (+-kBand fine grains) is only +-kBand / 2
// coarse grains wide: past it every grain read "far" (+-kBand), and the dabs, which trust distances up to the band's
// edge (the Build up off cap above all: it is measured from where the stroke began), stopped and stepped at that
// line: terraces like contour lines in the preview (3d-v4 round 3). So the grains past it get their distance from the
// trusted ones by kHaloPasses Jacobi upwind eikonal passes (as clay_band.cpp re-levels), over the chunk and a halo
// of kHaloPasses grains: the chunk's grains come out the same however the copy was made (whole, or refreshed), and
// depend only on the fine chunks under it and its 26 neighbours.
constexpr int kHaloPasses = 3;
constexpr int kHaloN = 8 + 2 * kHaloPasses;  // the chunk and its halo, grains a side
inline int halo_at(int x, int y, int z) { return x + kHaloN * (y + kHaloN * z); }
void coarse_band(const Tree::ConstAccessor& acc, const Coord& c, float* v) {
  constexpr int H = kHaloPasses, N = kHaloN;
  constexpr float kTrusted = 0.5f * kBand;
  float raw[N * N * N], cur[N * N * N], next[N * N * N];
  const auto at = halo_at;
  for (int z = 0; z < N; ++z)
    for (int y = 0; y < N; ++y)
      for (int x = 0; x < N; ++x) {
        const Coord f(2 * (c.x() - H + x), 2 * (c.y() - H + y), 2 * (c.z() - H + z));
        raw[at(x, y, z)] = to_coarse(acc.getValue(f));
      }
  std::memcpy(cur, raw, sizeof raw);
  std::memcpy(next, raw, sizeof raw);
  for (int pass = 0; pass < H; ++pass) {
    for (int z = 1; z < N - 1; ++z)
      for (int y = 1; y < N - 1; ++y)
        for (int x = 1; x < N - 1; ++x) {
          const int i = at(x, y, z);
          if (std::fabs(raw[i]) < kTrusted) continue;  // on the fine band: as it is
          const float ax = std::min(std::fabs(cur[i - 1]), std::fabs(cur[i + 1]));
          const float ay = std::min(std::fabs(cur[i - N]), std::fabs(cur[i + N]));
          const float az = std::min(std::fabs(cur[i - N * N]), std::fabs(cur[i + N * N]));
          next[i] = sgn(raw[i]) * std::min(std::min(eikonal(ax, ay, az), std::fabs(cur[i])), kBand);
        }
    std::memcpy(cur, next, sizeof cur);
  }
  for (int lz = 0; lz < 8; ++lz)
    for (int ly = 0; ly < 8; ++ly)
      for (int lx = 0; lx < 8; ++lx) v[leaf_offset(lx, ly, lz)] = cur[at(lx + H, ly + H, lz + H)];
}

// `at` and its 26 neighbours (chunk origins), sorted, unique: the chunks a coarse_band reads the fine under
void with_neighbours(std::vector<Coord>& at) {
  const size_t n = at.size();
  at.reserve(n * 27);
  for (size_t i = 0; i < n; ++i)
    for (int dz = -8; dz <= 8; dz += 8)
      for (int dy = -8; dy <= 8; dy += 8)
        for (int dx = -8; dx <= 8; dx += 8)
          if (dx || dy || dz) at.push_back(at[i] + Coord(dx, dy, dz));
}

// chunk `c` of `out` made `v`, whatever it held: the background (all outside / all 0), an inside tile, or a leaf
void put_coarse(Tree& out, const Coord& c, const float* v, bool sdf) {
  if (sdf) {
    bool allOut = true, allIn = true;
    for (openvdb::Index k = 0; k < Leaf::SIZE; ++k) {
      allOut = allOut && v[k] >= kBand;
      allIn = allIn && v[k] <= -kBand;
    }
    if (allOut || allIn) {
      const float t = allOut ? kBand : -kBand;
      if (out.probeConstLeaf(c) || out.getValue(c) != t) out.addTile(1, c, t, false);
      return;
    }
    Leaf* l = out.touchLeaf(c);
    for (openvdb::Index k = 0; k < Leaf::SIZE; ++k) {
      if (std::fabs(v[k]) < kBand) l->setValueOn(k, v[k]);
      else l->setValueOff(k, sgn(v[k]) * kBand);
    }
    return;
  }
  if (std::all_of(v, v + Leaf::SIZE, [](float x) { return x == 0.0f; })) {
    if (out.probeConstLeaf(c)) out.addTile(1, c, 0.0f, false);
    return;
  }
  Leaf* l = out.touchLeaf(c);
  for (openvdb::Index k = 0; k < Leaf::SIZE; ++k) l->setValueOn(k, v[k]);
}

// chunks `at` (sorted, unique) of `out` worked out from `fine` (in parallel), then written (in order)
void put_chunks(const Tree& fine, Tree& out, const std::vector<Coord>& at, bool sdf) {
  std::vector<float> vals(at.size() * Leaf::SIZE);
  tbb::parallel_for(tbb::blocked_range<size_t>(0, at.size(), 16), [&](const tbb::blocked_range<size_t>& r) {
    const Tree::ConstAccessor acc(fine);
    for (size_t i = r.begin(); i < r.end(); ++i) {
      if (sdf) coarse_band(acc, at[i], &vals[i * Leaf::SIZE]);
      else coarse_values(fine, at[i], &vals[i * Leaf::SIZE], false);
    }
  });
  for (size_t i = 0; i < at.size(); ++i) put_coarse(out, at[i], &vals[i * Leaf::SIZE], sdf);
}

void sort_unique(std::vector<Coord>& v) {
  std::sort(v.begin(), v.end(), coord_less);
  v.erase(std::unique(v.begin(), v.end()), v.end());
}

// `fine` at twice the grain into the empty `out`: the chunks over a fine leaf worked out grain by grain; for the
// distances, the chunks under a fine inside tile and over no leaf become inside tiles.
void copy_down(const Tree& fine, Tree& out, bool sdf) {
  std::vector<Coord> at;
  at.reserve(fine.leafCount());
  for (auto it = fine.cbeginLeaf(); it; ++it) at.push_back(coarse_chunk(it->origin()));
  if (sdf) with_neighbours(at);  // the band reaches past the chunks over a fine leaf
  sort_unique(at);
  put_chunks(fine, out, at, sdf);
  if (!sdf) return;
  // inside tiles (of any level) with no leaf over them
  Tree::ValueOffCIter it = fine.cbeginValueOff();
  it.setMaxDepth(Tree::ValueOffCIter::LEAF_DEPTH - 1);
  for (; it; ++it) {
    if (it.getValue() >= 0) continue;
    openvdb::CoordBBox bb;
    it.getBoundingBox(bb);
    const Coord lo = coarse_chunk(bb.min()), hi = coarse_chunk(bb.max());
    for (int z = lo.z(); z <= hi.z(); z += 8)
      for (int y = lo.y(); y <= hi.y(); y += 8)
        for (int x = lo.x(); x <= hi.x(); x += 8) {
          const Coord c(x, y, z);
          if (!std::binary_search(at.begin(), at.end(), c, coord_less)) out.addTile(1, c, -kBand, false);
        }
  }
}

double ms_since(std::chrono::steady_clock::time_point t0) {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

int catchup_threads() {
  if (const char* env = std::getenv("ROSTRUM3D_CLAY_CATCHUP_THREADS")) {
    const int n = std::atoi(env);
    if (n > 0) return n;
  }
  // half the cores (the physical ones, with two threads a core): the stroke's own dab and meshing loops run on the
  // other half while the catch-up works (3d-v4 round 1, all but one: the preview's meshing took 4-7 ms, not ~1.5)
  return std::max(2, int(std::thread::hardware_concurrency()) / 2);
}

// 3d-cl4: the catch-up's width while the brush moves and the clay keeps up (Catchup); 0: always wide (as 3d-v4, for an
// A/B on one build)
int catchup_moving_threads() {
  if (const char* env = std::getenv("ROSTRUM3D_CLAY_CATCHUP_MOVING_THREADS")) {
    const int n = std::atoi(env);
    if (n >= 0) return n;
  }
  return 1;
}

// the calling thread below normal OS priority (the catch-up's own thread: the window's and the stroke's threads first)
void lower_this_thread() {
#ifdef _WIN32
  SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL);
#endif
}

}  // namespace

void Volume::refresh_coarse(const Volume& fine, const std::vector<Coord>& fineChunks,
                            const std::vector<Coord>& coarseChunks) {
  std::vector<Coord> at = coarseChunks;
  for (const Coord& o : fineChunks) at.push_back(coarse_chunk(o));
  sort_unique(at);
  if (at.empty()) return;
  if (fine.has_mask() || has_mask()) put_chunks(fine.mask_->tree(), mask_->tree(), at, false);
  with_neighbours(at);  // a chunk's band reads the fine under its neighbours too (coarse_band)
  sort_unique(at);
  put_chunks(fine.grid_->tree(), grid_->tree(), at, true);
  dirty_.clear();
  changes_.clear();
  changesAll_ = false;
}

std::unique_ptr<Volume> Volume::coarse_copy() const {
  auto c = std::make_unique<Volume>(2.0f * voxel_);
  c->own_buffers();  // its dabs run while the catch-up thread's run on the shared buffers
  c->coarse_ = coarse_;
  copy_down(grid_->tree(), c->grid_->tree(), true);
  if (has_mask()) copy_down(mask_->tree(), c->mask_->tree(), false);
  return c;
}

Catchup::Catchup(Volume& clay, std::function<void()> first)
    // low priority: TBB's worker threads go to the stroke's own loops first whenever those have work
    : vol_(clay),
      first_(std::move(first)),
      wide_(catchup_threads(), 1, tbb::task_arena::priority::low),
      narrow_(std::max(1, catchup_moving_threads()), 1, tbb::task_arena::priority::low),
      narrowOn_(catchup_moving_threads() > 0),
      lastPush_(std::chrono::steady_clock::now()) {
  th_ = std::thread([this] { loop(); });
}

Catchup::~Catchup() { cancel(); }

double Catchup::est_ms_locked() const { return wideMs_ > 0 ? wideMs_ : narrowMs_; }

void Catchup::loop() {
  if (narrowOn_) lower_this_thread();  // (off: as 3d-v4)
  try {
    if (first_) wide_.execute([&] { first_(); });  // the first event waits for it
  } catch (...) {
    std::lock_guard<std::mutex> lk(m_);
    err_ = std::current_exception();
  }
  {
    std::lock_guard<std::mutex> lk(m_);
    isReady_ = true;
  }
  ready_.notify_all();
  for (;;) {
    Step s;
    bool wide = true;
    {
      std::unique_lock<std::mutex> lk(m_);
      work_.wait(lk, [&] { return cancel_ || stop_ || !q_.empty(); });
      if (cancel_ || err_ || q_.empty()) return;  // cancelled, failed, or finished with every dab applied
      s = q_.front();
      q_.pop_front();
      busy_ = true;
      // narrow while the brush moves and the clay keeps up (the dab just taken counts as waiting). The first dab runs
      // wide: the wide pace is what the waiting dabs and the event budget are measured in
      const double rest = ms_since(lastPush_);
      wide = !narrowOn_ || stop_ || wideMs_ <= 0 || rest >= kRestMs || wideMs_ * double(q_.size() + 1) > kWidenMs;
    }
    const auto t0 = std::chrono::steady_clock::now();
    try {
      (wide ? wide_ : narrow_).execute([&] { vol_.dab(s); });
    } catch (...) {
      {
        std::lock_guard<std::mutex> lk(m_);
        err_ = std::current_exception();
        q_.clear();
        busy_ = false;
      }
      idle_.notify_all();
      return;
    }
    const double ms = ms_since(t0);
    {
      std::lock_guard<std::mutex> lk(m_);
      double& avg = wide ? wideMs_ : narrowMs_;
      avg = avg > 0 ? 0.8 * avg + 0.2 * ms : ms;
      if (!wide) ++narrowDabs_;
      busy_ = false;
    }
    idle_.notify_all();
  }
}

void Catchup::wait_ready() {
  std::unique_lock<std::mutex> lk(m_);
  ready_.wait(lk, [&] { return isReady_; });
  if (err_) std::rethrow_exception(err_);
}

void Catchup::push(const Step* dabs, size_t n) {
  if (n == 0) return;
  {
    std::lock_guard<std::mutex> lk(m_);
    if (err_) std::rethrow_exception(err_);
    q_.insert(q_.end(), dabs, dabs + n);
    lastPush_ = std::chrono::steady_clock::now();
  }
  work_.notify_one();
}

void Catchup::drain() {
  {
    std::unique_lock<std::mutex> lk(m_);
    lastPush_ = std::chrono::steady_clock::time_point{};  // nothing moving: what is left runs wide
    idle_.wait(lk, [&] { return err_ || cancel_ || (q_.empty() && !busy_); });
  }
  if (err_) std::rethrow_exception(err_);
}

void Catchup::finish() {
  {
    std::lock_guard<std::mutex> lk(m_);
    stop_ = true;
  }
  work_.notify_all();
  if (th_.joinable()) th_.join();
  if (err_) std::rethrow_exception(err_);
}

void Catchup::cancel() {
  {
    std::lock_guard<std::mutex> lk(m_);
    cancel_ = true;
  }
  work_.notify_all();
  if (th_.joinable()) th_.join();
}

double Catchup::dab_ms() const {
  std::lock_guard<std::mutex> lk(m_);
  return est_ms_locked();
}

double Catchup::backlog_ms() const {
  std::lock_guard<std::mutex> lk(m_);
  return est_ms_locked() * double(q_.size());
}

int Catchup::narrow_dabs() const {
  std::lock_guard<std::mutex> lk(m_);
  return narrowDabs_;
}

}  // namespace r3d::clay
