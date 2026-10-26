// Clay: replaying many strokes at once (the store's replay from scratch, and the `clay_bench` check request).
//
// Each stroke may write only the chunks near its dabs and read only those and the chunks within 2 of them (4 for a
// stroke with a big, coarse dab: clay_coarse.h) (what Volume::run reaches). A stroke waits for every earlier stroke
// whose written chunks it reads (or that reads its own); strokes that don't touch each other run at the same time,
// heaviest waited-on chain first, straight on the clay (read under a shared lock, written under the unique one; the
// mask with it), with pooled step buffers. Strokes that don't touch commute, so the clay is bit for bit the clay of
// applying the strokes one after another (the same hash). Live strokes keep the serial path (Volume::apply_stroke).
#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>

#include "clay_step.h"
#include "clay_volume.h"

namespace r3d::clay {

struct ReplayStats {
  size_t strokes = 0, dabs = 0;
  size_t chain = 0;  // the longest chain of strokes that had to wait for each other (1 = all at once)
  double ms = 0;
};

// Applies the strokes (each a stroke's dabs, in step order) to `v` exactly as v.apply_stroke on each in turn would.
// No undo records and no live stroke may be on `v` (the store replays only steps older than its last 64).
ReplayStats replay_strokes(Volume& v, const std::vector<std::vector<Step>>& strokes);

// The `clay_bench` check (clay_bench.cpp): the proof's bench clay (proofs/3d-clay, bench mode: a scripted head, then
// `strokes` random strokes over it from a fixed seed, every brush) sculpted live, then its strokes replayed into new
// clay one after another and with replay_strokes, on at most `threads` threads (0 = all).
struct BenchResult {
  int strokes = 0, threads = 0;
  size_t dabs = 0, chain = 0;
  double liveMs = 0, serialMs = 0, parallelMs = 0;  // the strokes only (the head is replayed first, untimed)
  uint64_t live = 0, serial = 0, parallel = 0;      // hashes
  // CL2, the big brush: a quarter-size dab (radius 1/8 of the head, 66 grains) of each of the 6 brushes, 24 dabs
  // round the cranium each, each its own live stroke, on the head as it is after the strokes. The dab's own time
  // (Volume::dab, no picture), median and 90th percentile, on the coarse copy and with it turned off (fine).
  double bigCoarseMs = 0, bigCoarseP90 = 0, bigFineMs = 0, bigFineP90 = 0;
  size_t bigDabs = 0;
  // its strokes (coarse) sculpted live, then replayed one after another and in parallel into the head again
  uint64_t bigLive = 0, bigSerial = 0, bigParallel = 0;
};
BenchResult bench(int strokes, int threads);

}  // namespace r3d::clay
