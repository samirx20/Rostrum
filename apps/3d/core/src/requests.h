// The core's state between requests (the stage, Hydra, colour, memory watch) and the requests that use it.
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdGeom/mesh.h>

#include <functional>
#include <memory>

#include "gpu_mem.h"
#include "hydra.h"
#include "image_out.h"
#include "shm.h"
#include "stage_build.h"
#include "view_post.h"

namespace r3d {

class Core {
 public:
  Core();
  PXR_NS::JsObject scene(const PXR_NS::JsObject& a);
  PXR_NS::JsObject render(const PXR_NS::JsObject& a, const std::function<void(const PXR_NS::JsObject&)>& progress);
  PXR_NS::JsObject view(const PXR_NS::JsObject& a);
  PXR_NS::JsObject pick(const PXR_NS::JsObject& a);
  PXR_NS::JsObject geometry(const PXR_NS::JsObject& a);  // geometry_request.cpp
  PXR_NS::JsObject unfold(const PXR_NS::JsObject& a);    // geometry_request.cpp (unfold.h)
  PXR_NS::JsObject save(const PXR_NS::JsObject& a);
  PXR_NS::JsObject info();

 private:
  Hydra& hydra();  // the GL context and engines are made on first use
  void need_scene(const char* request) const;
  PXR_NS::SdfPath camera(const std::string& id, const char* request) const;
  void check_frame(int frame, const char* where) const;
  // the built mesh of a top-level `mesh` or `combine` item (geometry, unfold); loud about anything else
  PXR_NS::UsdGeomMesh built_mesh(const std::string& id, const char* request) const;

  PXR_NS::UsdStageRefPtr stage_;
  std::unique_ptr<Hydra> hydra_;
  ColorOut color_;
  GpuMemWatch mem_;
  bool loaded_ = false;
  BuildResult built_;
  PXR_NS::JsObject scene_;  // the loaded scene as sent (geometry names combine inputs from it)
  std::unique_ptr<Shm> shm_;  // the live viewport's pictures
  std::unique_ptr<ViewPost> post_;  // after hydra_: released while its GL context is still there
};

}  // namespace r3d
