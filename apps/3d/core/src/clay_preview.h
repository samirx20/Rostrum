// Clay: the live stroke's coarse preview (3d-v4). At a fine grain a dab is costly to work, to mesh and to draw (1 mm,
// a 25 mm brush: Add ~8 ms, Pull ~24 ms, then Storm ~10 ms for the dense surface). A stroke whose brush is at least
// kPreviewFrom grains across its radius is shown on a copy of the clay at twice the grain while it is drawn:
//  - the copy is kept per clay between strokes, brought up to date behind after every change from the chunks that
//    changed (Volume::take_changes, refresh_coarse; the store's coarse job); the first preview stroke on a clay, or
//    one after a cache load, makes it at its begin (Volume::coarse_copy, on the catch-up thread, ~15 ms at 1 mm);
//  - each sample's ray meets the copy, and the dab is applied to the copy (a Pull drag is cut by the copy's grain);
//  - the copy's changed blocks are meshed at its grain (a quarter of the triangles) into preview prims of their own
//    (preview_key), with skirts (add_skirts) so no crack shows where they meet the fine blocks, and the 8 fine blocks
//    under each are taken down;
//  - the dabs found are the stroke (what is stored, cut by the clay's own grain): the catch-up thread applies them to
//    the clay itself, one after another, as the stroke goes (Catchup). Volume::dab on the clay from the stroke's start,
//    in order: exactly what a replay does, so live = replay still holds bit for bit (ROSTRUM3D_CLAY_VERIFY=1 checks).
//  - at the end the thread finishes the dabs left, and the fine blocks (changed or taken down) replace the preview:
//    the surface sharpens, and moves by at most the coarse grain's rounding.
// The stored clay never sees coarse work (3d-v3 tried coarse work in the clay: ripples, dda74c0a reverted).
#pragma once
#include <tbb/task_arena.h>

#include <chrono>
#include <condition_variable>
#include <deque>
#include <exception>
#include <functional>
#include <mutex>
#include <thread>

#include "clay_mesh.h"
#include "clay_step.h"
#include "clay_volume.h"

namespace r3d::clay {

// A brush this many grains across its radius or more gets the preview: a 25 mm brush at 1 mm (25), not at 2 mm
// (12.5, where a dab already costs ~5 ms: 3d-v3). Below it the preview's own copy and the fine blocks' swap at the end
// cost more than they save. Mask dabs never (they don't move the surface; the mask is shown on the fine blocks).
// ROSTRUM3D_CLAY_PREVIEW=0 turns it off (to measure), =1 on for every brush but Mask.
constexpr float kPreviewFrom = 16.0f;
// A clay this fine or finer (metres a grain) usually previews (a 25 mm brush is 16 grains at 1.56 mm): it keeps its
// coarse copy from the first scene on (Store::sync) and the preview's empty prims ready (3d-cl4, Store reserve_ring)
constexpr float kKeepCopyGrain = 0.0016f;
bool preview_stroke(const Brush& b, float grain);

// The preview's prims sit beside the fine blocks under the clay's prim, named by their coarse block moved by this on x
// (clay_1048576_…): a name no fine block reaches (that would be 33 km from the origin at 1 mm).
constexpr int kPreviewKey = 1 << 20;
inline BlockKey preview_key(const BlockKey& coarse) { return {coarse.x + kPreviewKey, coarse.y, coarse.z}; }
inline bool is_preview_key(const BlockKey& k) { return k.x >= kPreviewKey / 2; }
// a preview block's skirt depth, in its own grains
constexpr float kSkirtGrains = 1.5f;

// The clay's own dabs, applied on a thread of its own while the stroke is drawn (in an arena of its own, so the
// window's thread never runs a catch-up task while it waits in a loop of its own). First `first()` runs there (the
// preview's copy, read from the clay before any dab writes it). Thread rules: the clay is the thread's from the
// construction until finish() or cancel() returns; only these members may be called meanwhile, from one thread.
// The arena is of low priority, and of half the cores (ROSTRUM3D_CLAY_CATCHUP_THREADS sets its threads).
// 3d-cl4: while the brush moves and the clay keeps up, a dab runs in a narrow arena instead (1 thread,
// ROSTRUM3D_CLAY_CATCHUP_MOVING_THREADS sets it; the thread itself below normal OS priority), so the preview's dab and
// meshing get the cores. It goes wide when its dabs waiting would take more than kWidenMs at the wide pace, when no dab
// came for kRestMs (the pointer rests) and from finish() on (the release waits for it). A dab is the same clay on any
// number of threads (clay_coarse.h), so live = replay still holds.
class Catchup {
 public:
  Catchup(Volume& clay, std::function<void()> first);
  ~Catchup();  // cancel()
  Catchup(const Catchup&) = delete;
  Catchup& operator=(const Catchup&) = delete;

  void wait_ready();                   // until first() has run; rethrows what it or a dab threw
  void push(const Step* dabs, size_t n);
  void finish();                       // until every dab pushed is applied; joins; rethrows
  void cancel();                       // the dabs not applied yet are dropped; joins (never throws)
  // one dab on the clay at the wide pace, a running average (0: none yet; the first dab runs wide). The event budget
  // (Store::sculpt_compute) reads it: what the clay can catch up with when it needs to
  double dab_ms() const;
  double backlog_ms() const;           // the dabs waiting, at that average
  int narrow_dabs() const;             // dabs run narrow so far (ROSTRUM3D_CLAY_PROFILE)

  static constexpr double kWidenMs = 10.0;  // the dabs waiting (at the wide pace) over this: wide
  static constexpr double kRestMs = 40.0;   // no dab pushed for this long: wide

 private:
  void loop();
  double est_ms_locked() const;  // dab_ms() under m_
  Volume& vol_;
  std::function<void()> first_;
  tbb::task_arena wide_, narrow_;
  bool narrowOn_ = true;  // ROSTRUM3D_CLAY_CATCHUP_MOVING_THREADS=0: always wide
  mutable std::mutex m_;
  std::condition_variable work_, ready_;
  std::deque<Step> q_;
  bool isReady_ = false, stop_ = false, cancel_ = false;
  std::exception_ptr err_;
  double wideMs_ = 0, narrowMs_ = 0;
  int narrowDabs_ = 0;
  std::chrono::steady_clock::time_point lastPush_;
  std::thread th_;  // last: started once the rest is set
};

}  // namespace r3d::clay
