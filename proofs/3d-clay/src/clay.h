// P-Clay proof: the clay. A narrow-band signed distance field in an OpenVDB grid (values in VOXELS, negative
// inside; inactive values are +-kBand), changed only by steps. Throwaway proof code.
//
// A step changes a box of the grid: the box is copied out into a dense buffer, the distances are re-levelled wide
// enough for the step (Jacobi upwind eikonal from the zero crossings), the step is applied, the band is re-levelled,
// and the box is written back (uniform 8^3 chunks become tiles). Everything is per voxel and order free, so the same
// steps give the same grid bit for bit, on any number of threads.
#pragma once
#include <openvdb/openvdb.h>

#include <cstdint>
#include <memory>
#include <set>
#include <string>
#include <vector>

#include "mesh.h"

namespace clay {

constexpr float kBand = 4.0f;  // half width of the stored band, voxels

struct V3 {
  float x = 0, y = 0, z = 0;
};

// Add / Carve: raise or dig (pieces and dabs). Smooth: even out. Pull: move the clay under the brush along `b` (the
// drag). Flatten: towards the plane through `a` with normal `n`. Crease: a sharp line, dug and pinched in along `b`.
enum class Op : uint8_t { Add, Carve, Smooth, Pull, Flatten, Crease };
enum class Kind : uint8_t { Piece, Stamp };  // a shape put in (sphere / capsule, with blend), or one brush dab

struct Step {
  Kind kind = Kind::Piece;
  Op op = Op::Add;
  V3 a, b;               // piece: sphere centre a, or capsule a..b (a == b: sphere). stamp: a = point on the surface;
                         // b = Pull's vector (world) or Crease's line direction (unit)
  V3 n;                  // stamp: surface normal at a (out of the clay)
  float radius = 0.1f;   // world
  float blend = 0.0f;    // piece: smooth join distance, world
  float strength = 0.5f; // stamp: 0..1
  bool mirror = false;   // also at x -> -x (the same step, mirrored, in the same pass)
  uint32_t stroke = 0;   // stamp: the stroke it belongs to (dabs of one stroke are applied as one unit); 0 = alone
  bool accumulate = true;  // Add / Carve: off = a stroke raises (digs) at most one dab's height from where it began
};

std::string profile_text();  // where the steps' time went so far (totals)
std::string to_line(const Step& s);  // one text line, floats round-trip exactly
bool from_line(const std::string& line, Step& s);

struct StepTiming {
  double ms = 0;       // whole apply()
  size_t voxels = 0;   // dense box size
  double prepMs = 0, fillMs = 0, workMs = 0, writeMs = 0;  // where the time went: chunks found, filled, worked, written
};

class Clay {
 public:
  explicit Clay(float voxel);
  ~Clay();
  float voxel() const { return voxel_; }

  StepTiming apply(const Step& s);  // a piece or a lone dab; marks the changed blocks dirty
  // A stroke as one unit: all its dabs in one box, the band re-levelled once (what replay does).
  StepTiming apply_stroke(const std::vector<Step>& dabs);
  // Live: begin_stroke, then dab() per dab (shown at once, the grid's old chunks kept aside), then end_stroke puts
  // the kept chunks back and applies the stroke as one unit, so the clay equals a replay of the same steps.
  void begin_stroke();
  StepTiming dab(const Step& s);
  StepTiming end_stroke(const std::vector<Step>& dabs);
  std::set<BlockKey> take_dirty();  // and clears them

  // the surface of one block (mesh.h), and of everything (the whole-surface rebuild)
  void mesh(const BlockKey& k, BlockMesh& out) const;
  std::vector<BlockKey> all_blocks() const;
  void mesh_all(std::vector<std::pair<BlockKey, BlockMesh>>& out) const;  // parallel over blocks

  // surface picking for scripted strokes: move p onto the surface along the field's gradient; false if no surface near
  bool snap(const V3& p, V3& on, V3& normal) const;
  // a ray from `origin` along unit `dir` (world) to the first surface hit, then snapped onto it
  bool cast(const V3& origin, const V3& dir, float maxDist, V3& on, V3& normal) const;
  float sample(const V3& p) const;  // world point -> distance in voxels (trilinear)

  uint64_t hash() const;     // leaves (origin, values, active masks) and tiles, in tree order
  size_t memory_bytes() const;
  size_t active_voxels() const;
  bool save(const std::string& path) const;  // .vdb (the replay cache)
  bool load(const std::string& path);
  void probe(int x, int y, int z0, int z1) const;  // --check: print a voxel column (value, on, leaf)

 private:
  openvdb::FloatGrid::Ptr grid_;
  float voxel_;
  std::set<BlockKey> dirty_;
  struct Backup;  // what a stroke changed while it was drawn (end_stroke puts it back)
  std::unique_ptr<Backup> backup_;
  StepTiming run(const Step* steps, size_t n);  // one piece, or dabs as one unit
};

// world <-> voxel index helpers
inline float to_vox(float w, float voxel) { return w / voxel; }

}  // namespace clay
