// Clay (CL3): the piece shapes beyond a ball or a capsule, as distance fields. A drawn outline that puffs both ways
// out of its plane, a profile spun round an axis, and an item of the scene turned into clay. A step's field is made
// once, when the step is applied (clay_store.cpp), and is then read-only: evaluated from many threads at once, each
// with its own FieldEval. Distances are in grains (voxels) at voxel-space points, negative inside. No OpenVDB here.
#pragma once
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include "clay_step.h"

namespace r3d::clay {

// what a piece step names, as read from the scene (clay_scene.cpp): metres, the clay's own space
struct ShapeSpec {
  enum class Kind : uint8_t { Ball, Outline, Spin, Item } kind = Kind::Ball;  // Ball: sphere / capsule (Step a, b)
  V3 o, u, v;                              // outline, spin: the plane's origin and its two in-plane unit axes
  std::vector<std::array<float, 2>> pts;   // outline: [u, v] points; spin: the profile's [r, h] points
  float puff = 1.0f;                       // outline: thickness factor (1 = round)
  std::string source;                      // item: the source item's id
};

class Field {
 public:
  struct Grid;  // an item's level set (clay_shapes.cpp)
  enum class Kind : uint8_t { Outline, Spin, Item } kind = Kind::Outline;
  V3 lo, hi;  // voxel-space bounds of the shape (not mirrored)

  // outline and spin: the plane in voxel space (n = u x v); a 2-D grid of nx x ny cells of `cell` grains, cell (i, j)
  // centred at (a0 + i cell, b0 + j cell) along (u, v)
  V3 o, u, v, n;
  float a0 = 0, b0 = 0, cell = 1;
  int nx = 0, ny = 0;
  // outline: per cell, the inside cell whose ball is nearest in power (j * nx + i), and per cell its ball's radius
  // (grains; 0 outside the outline); 1 / puff and min(1, puff)
  std::vector<int32_t> arg;
  std::vector<float> radius;
  float inv_puff = 1, scale = 1;
  // spin: per cell the signed distance (grains) of (r, h) = (cell's a, cell's b) to the profile closed by the axis
  std::vector<float> table;
  // item
  std::shared_ptr<const Grid> grid;
};

// One thread's way to read a field (an item's keeps a cache of the grid's nodes). Mirrored: min of p and x -> -x.
class FieldEval {
 public:
  FieldEval(const Field& f, bool mirror);
  ~FieldEval();
  FieldEval(const FieldEval&) = delete;
  FieldEval& operator=(const FieldEval&) = delete;
  float operator()(V3 p);

 private:
  struct Probe;
  float raw(V3 p);
  const Field& f_;
  bool mirror_;
  std::unique_ptr<Probe> probe_;
};

// The field of an outline / spin step (`spec` already checked by clay_scene.cpp) for a clay of `voxel` metres per
// grain. Throws r3d::Error naming `where` when the shape covers no grain at all.
std::shared_ptr<const Field> make_outline(const ShapeSpec& spec, float voxel, const std::string& where);
std::shared_ptr<const Field> make_spin(const ShapeSpec& spec, float voxel, const std::string& where);

// The field of an item step: the prim of item `spec.source` on `stage` and every mesh under it (hidden ones too),
// world-transformed then into the clay's space (the clay's Xform at `clay`), as a level set of half width `halfWidth`
// grains. Throws r3d::Error naming `where`.source for an unknown item or one with no mesh.
std::shared_ptr<const Field> make_item(const ShapeSpec& spec, const PXR_NS::UsdStageRefPtr& stage,
                                       const PXR_NS::SdfPath& clay, float voxel, float halfWidth,
                                       const std::string& where);

// how far (grains) an item's level set must reach for a piece of blend `blend` grains (Volume::run reads the field up
// to a chunk's centre this far past the band and the blend; past it the field is clamped, which only far voxels see)
float item_half_width(float blend);

}  // namespace r3d::clay
