// P-Clay proof: the pictures. Storm (Hydra) shows the clay as one mesh prim per block, and only changed blocks are
// sent again; Cycles renders the whole rebuilt surface for a Final picture. Throwaway proof code.
#pragma once
#include <memory>
#include <string>

#include "mesh.h"

namespace clay {

struct Camera {
  float eye[3] = {0, 0, 3};
  float target[3] = {0, 0, 0};
  float fovYDeg = 30;
};

class View {
 public:
  // hidden GL context (offscreen, no visible window), an in-memory USD stage with: /Clay (Xform, block meshes go
  // under it), a clay material (warm grey, rough, UsdPreviewSurface) bound to /Clay, a ground-free studio lighting
  // (key, fill, rim + a soft dome, UsdLux), and /Cam.
  View(int width, int height);
  ~View();

  void set_camera(const Camera& c);

  // Create or update the prim for `key` (/Clay/b_<x>_<y>_<z>, negative numbers written as n5 etc.) with the mesh;
  // an empty mesh removes the prim. Points, normals (vertex interpolation), counts (all 3), indices.
  void set_block(const BlockKey& key, const BlockMesh& m);
  // Batch several set_block calls into one USD change (Sdf change block): begin/end around them.
  void begin_changes();
  void end_changes();
  size_t block_count() const;

  // One Storm frame of the current stage through /Cam, waited for on the GPU (glFinish). Returns wall ms.
  double render_storm();
  // Writes the last Storm frame (sRGB PNG).
  void save_storm_png(const std::string& path);

  // Final: Cycles renders `whole` (the whole rebuilt surface, one mesh) with the same camera, material and lights,
  // into an sRGB PNG at `path`. `samples` Cycles samples, denoised. Throws std::runtime_error on failure (no file).
  // Returns wall seconds. Call it as often as needed (other meshes, other cameras): one Cycles engine is made by the
  // first call and reused until the View goes.
  double render_cycles(const BlockMesh& whole, int samples, const std::string& path);

  // Writes the current stage (block prims) as .usda for inspection.
  void export_usda(const std::string& path);

 private:
  struct Impl;
  std::unique_ptr<Impl> p_;
};

}  // namespace clay
