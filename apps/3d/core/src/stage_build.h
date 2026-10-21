// Scene description (ENGINE_CONTRACT.md § 2) -> the USD stage. The only place the contract becomes USD.
#pragma once
#include <pxr/base/js/value.h>
#include <pxr/usd/usd/stage.h>

namespace r3d {

struct BuildResult {
  int items = 0;      // document items (all depths)
  int prims = 0;      // prims authored in the root layer
  int start = 0, end = 0;
  double fps = 24;
};

// Replaces the content of stage's root layer with the scene. Checked whole: on any problem it throws
// r3d::Error naming "<item id>.<field>" and the stage is left exactly as it was (the scene is authored into
// a fresh anonymous layer first, then moved over with TransferContent).
BuildResult build_stage(const PXR_NS::JsObject& scene, const PXR_NS::UsdStageRefPtr& stage);

}  // namespace r3d
