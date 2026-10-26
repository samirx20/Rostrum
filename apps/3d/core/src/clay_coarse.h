// Clay: big brushes on a coarser copy of the band (CL2). A dab whose radius is at least kCoarseFrom grains works on a
// copy of the clay at twice the grain, and only its change is brought back to the fine grains:
//  - the copy: coarse grain X holds the fine grain at 2X, halved (distances in coarse grains), or +-kBand ("far") where
//    the fine grain is off the band; the mask, where the clay has one there, the same way (unhalved);
//  - the dab and its re-levelling run on the copy exactly as a fine dab does (clay_band.cpp, run_dabs), over about
//    1/6 as many band grains (a quarter-of-the-clay dab: ~200,000 -> ~35,000);
//  - each fine grain then gains twice the coarse change, interpolated (trilinear), both sides clamped to the fine band's
//    edge (+-kBand / 2 coarse), and is clamped to the band. Fine detail under the brush stays; the big shape moves.
// Chosen by the step alone (its radius in grains = the step's radius and the clay's detail; Mask dabs never), never
// by timing or by the clay's state, so a live stroke and its replay (serial or parallel) take the same path: live =
// replay, bit for bit. Every part is per grain and in a fixed order: the same on any number of threads.
#pragma once
#include <functional>
#include <shared_mutex>
#include <vector>

#include "clay_box.h"
#include "clay_volume.h"

namespace r3d::clay::detail {

// A dab this many grains across its radius or more goes coarse. 1/8 of a clay about 400 grains across (the bench
// clay is 530: its quarter-size dab, radius 66, goes coarse; its random strokes, radius 5-24, never). Grains, not the
// clay's size: the size changes as it is sculpted and a parallel replay's stroke doesn't see the whole clay.
constexpr float kCoarseFrom = 48.0f;

inline bool coarse_dab(const Step& s, float iv) {
  return s.kind == Kind::Stamp && s.op != Op::Mask && s.radius * iv >= kCoarseFrom;
}

// What a coarse unit may touch, for the parallel replay's footprint (clay_replay.cpp), in fine grains. It writes only
// fine chunks whose centre is within this of a dab's (or its mirrored copy's) centre: coarse chunks worked on have
// their centre within the coarse reach + 6.1 of the coarse dab, their grains 6.06 more, a fine grain reads coarse
// grains within sqrt(3); doubled, then a fine chunk's centre to its farthest grain (6.1) and one grain to spare.
// r = the dab's radius, shift = dab_shift (both fine grains).
inline float coarse_write_reach(float r, float shift) {
  return 2.0f * (0.5f * r + kBand + 1.0f + 0.5f * shift + 6.1f + 6.06f + 1.74f) + 6.1f + 1.0f;
}
// and reads the fine chunks within this many chunks of those (2 coarse chunks: the leaf flags a unit of dabs looks at)
constexpr int kCoarseReadRing = 4;

// A lock taken only when there is one (the parallel replay's grid lock: shared to read the grid, unique to write it)
template <bool Shared> class GridLock {
 public:
  explicit GridLock(std::shared_mutex* m) : m_(m) {
    if (!m_) return;
    if (Shared) m_->lock_shared();
    else m_->lock();
  }
  ~GridLock() { unlock(); }
  void unlock() {
    if (!m_) return;
    if (Shared) m_->unlock_shared();
    else m_->unlock();
    m_ = nullptr;
  }
  GridLock(const GridLock&) = delete;
  GridLock& operator=(const GridLock&) = delete;

 private:
  std::shared_mutex* m_;
};

// One unit of coarse dabs, from Volume::run (its shapes already worked out, fine grains).
struct CoarseUnit {
  Tree* tree = nullptr;
  const Tree* mask = nullptr;          // the clay's mask (leaves only where some mask is)
  Buffers* bufs = nullptr;             // step buffers for the coarse box
  const ChunkRecord* start = nullptr;  // a live stroke's chunks as they were before it (off: none kept)
  std::shared_mutex* lock = nullptr;   // a parallel replay's grid lock, or null
  const Step* steps = nullptr;
  size_t n = 0;
  const std::vector<std::vector<DabShape>>* shapes = nullptr;  // per dab, fine grains
  const std::vector<float>* shift = nullptr;                   // per dab, fine grains
  std::function<void(const Coord&)> keep;                      // before a fine chunk is written (undo, live put-back)
  std::function<void(const int lo[3], const int hi[3])> dirty;  // the fine grains written (called under the lock)
  size_t written = 0;                                          // out: fine chunks written
};
void run_coarse(CoarseUnit& u);

}  // namespace r3d::clay::detail
