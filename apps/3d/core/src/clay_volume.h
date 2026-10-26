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
#pragma once
#include <openvdb/openvdb.h>

#include <cstdint>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <tuple>
#include <vector>

#include "clay_mesh.h"
#include "clay_step.h"

namespace r3d::clay {

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
  };
  bool on = false;
  const Chunk* find(const openvdb::Coord& o) const;
  void keep(const openvdb::FloatTree& t, const openvdb::Coord& o);  // first time only, while on
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

  std::set<BlockKey> take_dirty();  // and clears them
  void mesh(const BlockKey& k, BlockMesh& out) const;
  std::vector<BlockKey> all_blocks() const;  // every block that may hold surface

  // move p onto the surface along the field's gradient; false if no surface near
  bool snap(const V3& p, V3& on, V3& normal) const;
  // a ray from `origin` along unit `dir` (clay space) to the first surface hit within maxDist, then snapped onto it;
  // false when it starts inside the clay or misses
  bool cast(const V3& origin, const V3& dir, float maxDist, V3& on, V3& normal) const;
  float sample(const V3& p) const;  // clay-space point -> distance in voxels (trilinear)

  uint64_t hash() const;     // leaves (origin, values, active masks), in tree order
  size_t memory_bytes() const;
  size_t active_voxels() const;
  openvdb::FloatGrid::Ptr copy() const;  // a deep copy (the cache writer saves it on its own thread)
  static bool save(const openvdb::FloatGrid::ConstPtr& grid, const std::string& path, std::string* error);
  bool load(const std::string& path, std::string* error);  // a .vdb this class saved, of the same voxel size

 private:
  openvdb::FloatGrid::Ptr grid_;
  float voxel_;
  std::set<BlockKey> dirty_;
  ChunkRecord live_;            // a live stroke's put-back
  ChunkRecord* record_ = nullptr;  // the undo record being filled, if any
  StepTiming run(const Step* steps, size_t n);  // one piece, or dabs as one unit (clay_volume.cpp)
  void keep(const openvdb::Coord& o);           // before writing chunk o: into the live put-back and the record
  void put_back(const ChunkRecord& rec);        // write a record's chunks into the grid
  void mark_dirty(const int lo[3], const int hi[3]);  // the blocks reading voxels lo..hi (normals included)
};

}  // namespace r3d::clay
