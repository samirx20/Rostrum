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
#include <array>
#include <cstdint>
#include <functional>
#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include <pxr/base/gf/vec3d.h>
#include <pxr/usd/sdf/path.h>
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
  double applyMs = 0, meshMs = 0, usdMs = 0;  // where `ms` went: the dabs, meshing the changed blocks, writing them
  int blocks = 0;                             // blocks changed by this event
  std::string file;     // end: "clay/<hash>.dabs", or "" when no dab landed
};

struct ClayInfo {
  std::string hash;  // 16 hex
  size_t steps = 0, voxels = 0, blocks = 0;
  double memoryMb = 0;
};

// CL5, clay_pose: blocks re-posed, and the time it took
struct PoseReply {
  int blocks = 0;
  double ms = 0;
  double skinMs = 0, usdMs = 0;  // of ms: the bending (parallel), the Sdf writes (serial, one change block)
};

// CL5, clay_grid: the rest clay sampled at cell centres. Cell (i, j, k) has its centre at origin + (i+0.5, j+0.5,
// k+0.5) × cell; `inside` holds one byte per cell (1 inside, 0 outside), x fastest, then y, then z.
struct GridReply {
  double origin[3] = {0, 0, 0};  // the grid's low corner, clay space
  double cell = 0;               // metres
  int dims[3] = {0, 0, 0};
  std::vector<uint8_t> inside;
  double ms = 0;
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
  // 3d-v4: a brush of kPreviewFrom grains or more (clay_preview.h) is shown on a coarse preview while it is drawn, and
  // the clay itself catches up on a thread of the store's own; the end puts the clay's own blocks back.
  // `preview` false (3d-cl4: the Final look or a render is shown): never the coarse preview, so Cycles never draws it.
  void sculpt_begin(const std::string& item, const Brush& brush, bool preview = true);
  // A dab event in two parts (3d-v4), so its work can run off the thread that owns the stage:
  //  - sculpt_compute: resamples px (x, y and the pen pressure 0..1), applies the dabs, and meshes the changed blocks
  //    into meshes the store keeps. It never reads or writes the stage; `ray` and `ppm` must not either. Fills dabs,
  //    hit, point, normal, applyMs, meshMs, blocks and ms.
  //  - sculpt_publish: writes the kept meshes to the stage (the thread that owns it); fills usdMs and adds it to ms.
  // Thread rules: compute may run on any thread while the stage is read elsewhere (Hydra drawing), but no other call
  // on this Store may run during it (publish included): the caller runs compute, then publish, one after the other.
  // Meshes not yet published when the stroke ends or is cancelled are written by sculpt_end / sculpt_cancel (or
  // dropped where they are no longer right).
  SculptReply sculpt_compute(const std::vector<std::array<float, 3>>& px, const RayFn& ray,
                             const PixelsPerMetreFn& ppm);
  void sculpt_publish(SculptReply& r);
  // compute then publish
  SculptReply sculpt_points(const std::vector<std::array<float, 3>>& px, const RayFn& ray,
                            const PixelsPerMetreFn& ppm);
  // applies the stroke as one unit and writes its dab file into <folder>/clay/; the stroke waits to be adopted. With a
  // preview: waits for the catch-up, then the clay's blocks replace the preview's. Writes the stage.
  SculptReply sculpt_end(const std::string& folder, const std::string& where);
  void sculpt_cancel();
  bool sculpting() const;
  bool previewing() const;  // 3d-cl4: a live stroke shown on its coarse preview (its prims are on the stage)
  std::string sculpt_item() const;

  ClayInfo info(const std::string& item) const;

  // CL5, a clay with bones (clay_skin.h). Every skinned clay's blocks posed for `frame` (its pose table at frame -
  // start, clamped; a clay_pose's moves instead until the next scene): before a view, render or pick draws or picks
  // it, and before a stroke's rays. Only the blocks whose bones moved are written. Writes the stage. How many.
  int pose_frame(int frame);
  // CL6: before Cycles draws (a cycles render's frame, the Final look's view, after pose_frame): every clay whose
  // blocks changed since gets its welded whole again (clay_whole.h); ms spent (0: nothing to weld). Writes the stage.
  double whole_for_cycles();
  // clay_pose: the clay drawn with these bone moves until the next sync (or the next pose). Loud when the clay has no
  // bones or the count differs. Writes the stage.
  PoseReply pose(const std::string& item, const std::vector<BoneMove>& moves);
  // clay_grid: the rest clay's inside, `cells` (8..128) along the longest side of its bounds padded by one cell
  GridReply grid(const std::string& item, int cells) const;
  bool skinned(const std::string& item) const;
  // a picked spot on block prim `prim`, triangle `face`, at `local` (drawn, clay space) -> the same spot at rest;
  // none when the clay has no bones or the prim is none of its blocks
  std::optional<PXR_NS::GfVec3d> rest_spot(const std::string& item, const PXR_NS::SdfPath& prim, int face,
                                           const PXR_NS::GfVec3d& local) const;

 private:
  struct Impl;
  std::unique_ptr<Impl> p_;
};

}  // namespace r3d::clay
