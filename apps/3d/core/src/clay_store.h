// Clay: the store, one per serve process. Per clay item: its volume, the step keys applied to it, and for the last
// 64 applied steps the chunks each replaced (undo = put them back, no replay). Its surfaces are block Mesh prims in a
// layer of its own (clay_usd.h), so a scene reload leaves them alone and a dab re-sends only the blocks it changed.
//
// After every scene build, sync() brings each clay to its steps (CL1 contract § 4):
//   same keys -> nothing; held keys a prefix of the new -> apply the rest; new keys a prefix of the held -> put the
//   chunks back (else rebuild); otherwise the cache file if it exists, else undo to the shared start and apply the
//   rest, else replay all. Live strokes not yet in the steps (sculpt end before the scene that holds them) are adopted
//   when the scene's next stroke names the same dab file; otherwise they are put back first.
// The cache .vdb for the current steps is written on a thread of its own after a change (the newest wins).
#pragma once
#include <functional>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <pxr/usd/usd/stage.h>

#include "clay_scene.h"

namespace r3d::clay {

// a pixel's ray in the clay's own space (origin, unit direction); false when the pixel has none
using RayFn = std::function<bool(float px, float py, V3& origin, V3& dir)>;
// how many pixels a clay-space length of 1 m covers at `depth` (clay space) from the camera
using PixelsPerMetreFn = std::function<float(float depth)>;

struct SculptReply {
  int dabs = 0;         // dabs of this stroke so far (end: in the stroke)
  bool hit = false;     // the last point's ray met the clay
  V3 point, normal;     // where, clay space (when hit)
  double ms = 0;
  std::string file;     // end: "clay/<hash>.dabs", or "" when no dab landed
};

struct ClayInfo {
  std::string hash;  // 16 hex
  size_t steps = 0, voxels = 0, blocks = 0;
  double memoryMb = 0;
};

class Store {
 public:
  explicit Store(PXR_NS::UsdStageRefPtr stage);
  ~Store();
  Store(const Store&) = delete;
  Store& operator=(const Store&) = delete;

  // after build_stage: every clay of the scene brought to its steps; clays no longer in it are dropped. Throws
  // r3d::Error naming "<item>.steps[i]" when a step can't be applied (the clay keeps the steps before it).
  void sync(const std::vector<Node>& clays);
  bool has(const std::string& item) const;

  // A live stroke on `item` (begin, points…, end or cancel). Points are pixels; `ray` turns them into clay-space rays.
  void sculpt_begin(const std::string& item, const Brush& brush);
  SculptReply sculpt_points(const std::vector<std::pair<float, float>>& px, const RayFn& ray,
                            const PixelsPerMetreFn& ppm);
  // applies the stroke as one unit and writes its dab file into <folder>/clay/; the stroke waits to be adopted
  SculptReply sculpt_end(const std::string& folder, const std::string& where);
  void sculpt_cancel();
  bool sculpting() const;
  std::string sculpt_item() const;

  ClayInfo info(const std::string& item) const;

 private:
  struct Impl;
  std::unique_ptr<Impl> p_;
};

}  // namespace r3d::clay
