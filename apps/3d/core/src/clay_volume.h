// Clay: the volume. A narrow-band signed distance field in an OpenVDB grid (values in VOXELS, negative inside;
// inactive values are +-kBand), changed only by steps. Moved from proofs/3d-clay (clay.h / clay.cpp).
//
// A step changes a box of the grid: the box is copied out chunk by chunk, the step is applied, the band is
// re-levelled (a dab: over its own narrow band only), and the changed chunks are written back (uniform 8^3 chunks
// become tiles). Everything is per voxel and order free, so the same steps give the same grid bit for bit, on any
// number of threads.
//
// What a step replaced can be kept: a ChunkRecord holds each chunk's state before its first change while recording
// is on, and restore() puts them back (the store's undo; a live stroke's put-back before its unit is applied).
//
// The mask (CL2) is a second float grid, 0..1 (0 = free, the background), painted by Mask dabs and read by every other
// dab. It is part of the clay's state like the distances: chunk records keep its chunks, the hash covers it, the
// cache file holds it as a second grid ("mask"), and live = replay holds for it too.
#pragma once
#include <openvdb/openvdb.h>

#include <cstdint>
#include <map>
#include <memory>
#include <set>
#include <shared_mutex>
#include <string>
#include <tuple>
#include <vector>

#include "clay_mesh.h"
#include "clay_step.h"

namespace r3d::clay {

namespace detail {
struct Buffers;  // clay_box.h
}

struct StepTiming {
  double ms = 0;       // the whole step
  size_t voxels = 0;   // voxels written back
};

// Chunks as they were before their first change (8^3 leaf or one tile value each).
class ChunkRecord {
 public:
  struct Chunk {
    openvdb::Coord o;
    bool leaf = false;
    float value = 0;  // the tile's value when not a leaf
    std::vector<float> values;
    openvdb::FloatTree::LeafNodeType::NodeMaskType mask;
    bool maskKept = false;          // the clay's mask chunk is kept too (else restore leaves the mask alone)
    std::vector<float> maskValues;  // its leaf's values, or empty: no leaf (all 0)
  };
  bool on = false;
  const Chunk* find(const openvdb::Coord& o) const;
  // first time only, while on; with `maskTree`, that chunk of the clay's mask too
  void keep(const openvdb::FloatTree& t, const openvdb::Coord& o) { keep(t, nullptr, o); }
  void keep(const openvdb::FloatTree& t, const openvdb::FloatTree* maskTree, const openvdb::Coord& o);
  void clear();
  size_t bytes() const;
  const std::vector<Chunk>& chunks() const { return chunks_; }

 private:
  std::vector<Chunk> chunks_;
  std::map<std::tuple<int, int, int>, size_t> seen_;  // origin -> chunks_ index
};

class Volume {
 public:
  explicit Volume(float voxel);  // voxel = metres per grain (the clay's `detail`)
  ~Volume();
  float voxel() const { return voxel_; }

  StepTiming apply(const Step& s);  // a piece or a lone dab; marks the changed blocks dirty
  // A stroke as one unit: its dabs in units that move the surface at most a little each (what replay does).
  StepTiming apply_stroke(const std::vector<Step>& dabs);
  // The same from one of several threads at once (the parallel replay, clay_replay.cpp): step buffers of the caller's,
  // the grid read under a shared `lock` and written under the unique one. The caller makes sure no two strokes running
  // together touch the same chunks, and that no live stroke or undo record is on.
  StepTiming apply_stroke_shared(const std::vector<Step>& dabs, detail::Buffers& bufs, std::shared_mutex& lock);
  // Big dabs work on a 2x coarser copy of the band (clay_coarse.h). Off only to measure the fine path (the bench).
  void allow_coarse(bool on) { coarse_ = on; }
  // Live: begin_stroke, then dab() per dab (shown at once, the old chunks kept aside), then end_stroke puts the kept
  // chunks back and applies the stroke as one unit, so the clay equals a replay of the same steps. cancel_stroke only
  // puts them back.
  void begin_stroke();
  StepTiming dab(const Step& s);
  StepTiming end_stroke(const std::vector<Step>& dabs);
  void cancel_stroke();
  bool in_stroke() const { return live_.on; }

  // Undo: while recording, every chunk a step writes is kept (as it was before) in `rec`. restore() puts a record's
  // chunks back and marks their blocks dirty. Records are restored newest first.
  void record_into(ChunkRecord* rec);  // null = stop
  void restore(const ChunkRecord& rec);

  std::set<BlockKey> take_dirty();  // and clears them (the parts' too)
  // 3d-leftovers: the changed blocks' parts (clay_mesh.h kPart; keys in parts), and clears them (the blocks' too)
  std::set<BlockKey> take_dirty_parts();
  void mesh(const BlockKey& k, BlockMesh& out) const;
  void mesh_part(const BlockKey& part, BlockMesh& out) const;  // one part (its key in parts) of block part / 2
  std::vector<BlockKey> all_blocks() const;  // every block that may hold surface

  // move p onto the surface along the field's gradient; false if no surface near
  bool snap(const V3& p, V3& on, V3& normal) const;
  // a ray from `origin` along unit `dir` (clay space) to the first surface hit within maxDist, then snapped onto it;
  // false when it starts inside the clay or misses
  bool cast(const V3& origin, const V3& dir, float maxDist, V3& on, V3& normal) const;
  float sample(const V3& p) const;  // clay-space point -> distance in voxels (trilinear)

  // A private volume of a parallel replay (clay_replay.cpp): step buffers of its own instead of the ones every clay
  // shares, so several volumes can run steps at the same time on different threads.
  void own_buffers();
  const openvdb::FloatTree& tree() const { return grid_->tree(); }
  const openvdb::FloatTree& mask_tree() const { return mask_->tree(); }  // leaves only where some mask is (0 elsewhere)
  bool has_mask() const { return mask_->tree().leafCount() > 0; }

  uint64_t hash() const;     // leaves (origin, values, active masks), in tree order
  size_t memory_bytes() const;
  size_t active_voxels() const;
  openvdb::FloatGrid::Ptr copy() const;  // a deep copy (the cache writer saves it on its own thread)
  openvdb::FloatGrid::Ptr copy_mask() const;  // the mask's deep copy, or null when the clay has no mask
  // 3d-v4: the clay at twice the grain (a live stroke's preview, clay_preview.h), with step buffers of its own; only
  // reads this one, so it may run on another thread while nothing writes this volume
  std::unique_ptr<Volume> coarse_copy() const;
  // this coarse copy brought up to date with `fine` (its coarse_copy source) in the chunks over `fineChunks` (fine
  // chunk origins) and `coarseChunks` (its own, e.g. written by preview dabs); the result equals a new coarse_copy
  void refresh_coarse(const Volume& fine, const std::vector<openvdb::Coord>& fineChunks,
                      const std::vector<openvdb::Coord>& coarseChunks);
  // The chunks written since the last call (origins, maybe repeated; every step, restore and put-back), so a coarse
  // copy can be refreshed instead of made again. False: too many to list, or a load (anything may differ).
  bool take_changes(std::vector<openvdb::Coord>& out);
  // ends a live stroke keeping what its dabs did (a preview's: it is no stroke of the clay's own)
  void forget_stroke() {
    live_.on = false;
    live_.clear();
  }
  // `mask` (or null: no mask) is written beside the clay as the grid "mask"
  static bool save(const openvdb::FloatGrid::ConstPtr& grid, const std::string& path, std::string* error,
                   const openvdb::FloatGrid::ConstPtr& mask = nullptr);
  bool load(const std::string& path, std::string* error);  // a .vdb this class saved, of the same voxel size

 private:
  openvdb::FloatGrid::Ptr grid_;
  openvdb::FloatGrid::Ptr mask_;  // 0..1, background 0; a chunk is a leaf or nothing (an all-0 leaf is removed)
  float voxel_;
  std::set<BlockKey> dirty_, dirtyParts_;
  ChunkRecord live_;            // a live stroke's put-back
  ChunkRecord* record_ = nullptr;  // the undo record being filled, if any
  std::unique_ptr<detail::Buffers> bufs_;  // own step buffers (own_buffers), or null: the shared ones
  bool coarse_ = true;
  std::vector<openvdb::Coord> changes_;  // take_changes
  bool changesAll_ = false;
  void note_change(const openvdb::Coord& o);
  // one piece, or dabs as one unit (clay_volume.cpp); bufs / lock: a parallel replay's (else the volume's own)
  StepTiming run(const Step* steps, size_t n, detail::Buffers* bufs = nullptr, std::shared_mutex* lock = nullptr);
  StepTiming units(const std::vector<Step>& dabs, detail::Buffers* bufs, std::shared_mutex* lock);  // a stroke's
  void keep(const openvdb::Coord& o);           // before writing chunk o: into the live put-back and the record
  void put_back(const ChunkRecord& rec);        // write a record's chunks into the grid
  void mark_dirty(const int lo[3], const int hi[3]);  // the blocks reading voxels lo..hi (normals included)
};

}  // namespace r3d::clay
