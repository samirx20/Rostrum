// Which camera a viewport picture or a pick looks through: a scene camera by id, or the screen's free camera
// (eye, target, vertical field of view, +Y up). One place turns either into the frustum Hydra draws and picks with.
#pragma once
#include <pxr/base/gf/frustum.h>
#include <pxr/base/gf/vec3d.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include <functional>
#include <optional>
#include <string>

#include "args.h"

namespace r3d {

struct ViewCamera {
  PXR_NS::SdfPath camera;  // a scene camera; empty = the free camera
  PXR_NS::GfVec3d eye, target;
  double fov = 30;         // free camera, vertical, degrees
};

// The f-stop a camera with depth of field off is written with: a lens closed so far nothing blurs. Not 0 (USD's "no
// depth of field"): Cycles' Hydra camera skips an f-stop of 0 and keeps the aperture of the last camera that had one, so a
// camera switched off after a render with depth of field on rendered blurred in the same engine (Drop, 2026-10-29).
constexpr double kClosedFStop = 1e7;

// a scene camera's lens, for the viewport's depth of field (scene units)
struct Lens {
  double fStop = 0, focusDistance = 0, focalLength = 0, sensorWidth = 0;
};

// `camera`, or `eye` + `target` + `fov`; anything else is an error naming what is accepted
ViewCamera read_view_camera(const Args& a, const std::function<PXR_NS::SdfPath(const std::string&)>& scene_camera);
// the frustum for a width x height picture at `frame` (a scene camera keeps its sensor width, as in render)
PXR_NS::GfFrustum frustum_of(const PXR_NS::UsdStageRefPtr& stage, const ViewCamera& c, int frame, int w, int h);
// Shapes the scene camera's sensor like a width x height picture: its height = its width x h / w at `frame`, written
// on the stage's session layer (the document's own camera is untouched) and only when it differs. Every renderer then
// frames the camera alike, whatever its window policy: Storm keeps the sensor's width (frustum_of above, and the
// engine's override window policy), but Cycles' Hydra camera ignores that override and always fits the whole sensor
// into the picture (its hydra/camera.cpp keeps CameraUtilFit), so a picture wider than the sensor (a 2.39:1 render of a
// camera with the default 16:9 sensor) showed more at the sides in Final than in Quick. Called before each draw.
void shape_sensor(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& camera, int frame, int w, int h);
// the scene camera's lens when its depth of field is on (f-stop above 0); none for the free camera
std::optional<Lens> lens_of(const PXR_NS::UsdStageRefPtr& stage, const ViewCamera& c, int frame);

}  // namespace r3d
