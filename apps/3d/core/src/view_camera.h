// Which camera a viewport picture or a pick looks through: a scene camera by id, or the screen's free camera
// (eye, target, vertical field of view, +Y up). One place turns either into the frustum Hydra draws and picks with.
#pragma once
#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include <functional>
#include <string>

#include "args.h"

namespace r3d {

struct ViewCamera {
  PXR_NS::SdfPath camera;  // a scene camera; empty = the free camera
  PXR_NS::GfVec3d eye, target;
  double fov = 30;         // free camera, vertical, degrees
};

// `camera`, or `eye` + `target` + `fov`; anything else is an error naming what is accepted
ViewCamera read_view_camera(const Args& a, const std::function<PXR_NS::SdfPath(const std::string&)>& scene_camera);
// the frustum for a width x height picture at `frame` (a scene camera keeps its sensor width, as in render)
PXR_NS::GfFrustum frustum_of(const PXR_NS::UsdStageRefPtr& stage, const ViewCamera& c, int frame, int w, int h);

}  // namespace r3d
