#include "view_camera.h"

#include <pxr/base/gf/matrix4d.h>
#include <pxr/imaging/cameraUtil/conformWindow.h>
#include <pxr/usd/usdGeom/camera.h>

#include <algorithm>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
GfVec3d vec3(const Args& a, const char* k) {
  const auto& v = a.need(k);
  if (v.IsArray() && v.GetJsArray().size() == 3) {
    GfVec3d out;
    bool ok = true;
    for (int i = 0; i < 3; ++i) {
      const auto& x = v.GetJsArray()[i];
      ok &= x.IsReal() || x.IsInt();
      if (ok) out[i] = x.IsReal() ? x.GetReal() : double(x.GetInt());
    }
    if (ok) return out;
  }
  throw Error(a.where() + "." + k + ": needs [x, y, z], three numbers");
}
}  // namespace

ViewCamera read_view_camera(const Args& a, const std::function<SdfPath(const std::string&)>& scene_camera) {
  ViewCamera c;
  const bool free = a.has("eye") || a.has("target") || a.has("fov");
  if (a.has("camera") == free)
    throw Error(a.where() + ": give either camera (a scene camera's id) or eye + target + fov (the free camera)");
  if (!free) {
    c.camera = scene_camera(a.str("camera"));
    return c;
  }
  c.eye = vec3(a, "eye");
  c.target = vec3(a, "target");
  c.fov = a.num("fov");
  if (c.fov <= 0.5 || c.fov >= 170) throw Error(a.where() + ".fov: must be between 0.5 and 170 degrees");
  if ((c.eye - c.target).GetLength() < 1e-6) throw Error(a.where() + ".eye: must not be at the target");
  return c;
}

GfFrustum frustum_of(const UsdStageRefPtr& stage, const ViewCamera& c, int frame, int w, int h) {
  const double aspect = double(w) / h;
  if (!c.camera.IsEmpty()) {
    GfFrustum f = UsdGeomCamera(stage->GetPrimAtPath(c.camera)).GetCamera(UsdTimeCode(frame)).GetFrustum();
    CameraUtilConformWindow(&f, CameraUtilMatchHorizontally, aspect);
    return f;
  }
  const double dist = (c.eye - c.target).GetLength();
  GfVec3d up(0, 1, 0);
  if (GfCross(c.target - c.eye, up).GetLength() < 1e-9 * dist) up = GfVec3d(0, 0, -1);  // looking straight down / up
  GfMatrix4d view;
  view.SetLookAt(c.eye, c.target, up);
  GfFrustum f;
  f.SetPositionAndRotationFromMatrix(view.GetInverse());
  f.SetPerspective(c.fov, aspect, std::max(1e-4, dist * 0.002), dist * 2000);
  return f;
}

std::optional<Lens> lens_of(const UsdStageRefPtr& stage, const ViewCamera& c, int frame) {
  if (c.camera.IsEmpty()) return std::nullopt;
  const GfCamera cam = UsdGeomCamera(stage->GetPrimAtPath(c.camera)).GetCamera(UsdTimeCode(frame));
  if (cam.GetFStop() <= 0) return std::nullopt;
  return Lens{cam.GetFStop(), cam.GetFocusDistance(), cam.GetFocalLength() * GfCamera::FOCAL_LENGTH_UNIT,
              cam.GetHorizontalAperture() * GfCamera::APERTURE_UNIT};
}

}  // namespace r3d
