#include "storm_sun.h"

#include <pxr/base/gf/rotation.h>
#include <pxr/imaging/hd/filteringSceneIndex.h>
#include <pxr/imaging/hd/light.h>
#include <pxr/imaging/hd/lightSchema.h>
#include <pxr/imaging/hd/repr.h>
#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/rprimCollection.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hd/visibilitySchema.h>
#include <pxr/imaging/hd/xformSchema.h>
#include <pxr/imaging/hdx/shadowMatrixComputation.h>
#include <pxr/imaging/hdx/simpleLightTask.h>
#include <pxr/usd/usdGeom/bboxCache.h>
#include <pxr/usd/usdGeom/tokens.h>

#include <algorithm>
#include <iterator>
#include <memory>
#include <vector>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
const SdfPath kSun("/_RostrumStormSun");

struct State {
  std::optional<StormSun> sun;
  SunShadow shadow;
};
State& state() {
  static State s;
  return s;
}

// The shadow map's view: orthographic, from the sun, a square just covering `seen`, from the far side of `scene`
// (things outside the camera's view still cast into it). Read when Storm draws, so it follows the camera.
class SunShadowMatrix final : public HdxShadowMatrixComputation {
 public:
  std::vector<GfMatrix4d> Compute(const GfVec4f&, CameraUtilConformWindowPolicy) override { return compute(); }
  std::vector<GfMatrix4d> Compute(const CameraUtilFraming&, CameraUtilConformWindowPolicy) override { return compute(); }

 private:
  static std::vector<GfMatrix4d> compute() {
    const State& s = state();
    if (!s.sun || s.shadow.seen.IsEmpty()) return {};  // no matrix: Storm draws the light without a shadow
    const GfVec3d d = s.sun->toward, c = s.shadow.seen.GetMidpoint();
    const double r = std::max(s.shadow.seen.GetSize().GetLength() / 2, 1e-3);
    double lo = -r, hi = r;
    for (int i = 0; i < 8; ++i) {
      const double t = GfDot(s.shadow.scene.GetCorner(i) - c, d);
      lo = std::min(lo, t), hi = std::max(hi, t);
    }
    const double margin = 0.01 * r + 1e-3;
    const GfFrustum f(c + d * (hi + margin), GfRotation(GfVec3d(0, 0, 1), d), GfRange2d(GfVec2d(-r, -r), GfVec2d(r, r)),
                      GfRange1d(margin * 0.5, hi - lo + 2 * margin), GfFrustum::Orthographic);
    return {f.ComputeViewMatrix() * f.ComputeProjectionMatrix()};
  }
};

// The light as Storm reads it (hdSt/light.cpp, distant light): colour × intensity with `normalize` on is the light
// on a facing surface, which UsdPreviewSurface turns into albedo / π × that × cos (previewSurface.glslfx).
HdContainerDataSourceHandle sun_prim(const StormSun& sun) {
  static const HdxShadowParams shadow = [] {
    HdxShadowParams p;
    p.shadowMatrix = std::make_shared<SunShadowMatrix>();
    p.enabled = true;
    p.resolution = 2048;
    p.bias = -0.002;  // of the shadow map's depth range: keeps surfaces from shadowing themselves
    p.blur = 0.01;    // metres: a slightly soft edge, like the sun's half degree
    return p;
  }();
  static const HdRprimCollection casters(HdTokens->geometry, HdReprSelector(HdReprTokens->smoothHull));
  using F = HdRetainedTypedSampledDataSource<float>;
  using B = HdRetainedTypedSampledDataSource<bool>;
  const TfToken names[] = {HdLightTokens->color,     HdLightTokens->intensity,    HdLightTokens->exposure,
                           HdLightTokens->normalize, HdLightTokens->angle,        HdLightTokens->hasShadow,
                           HdLightTokens->shadowEnable, HdLightTokens->shadowParams, HdLightTokens->shadowCollection};
  const HdDataSourceBaseHandle values[] = {
      HdRetainedTypedSampledDataSource<GfVec3f>::New(sun.irradiance), F::New(1.0f), F::New(0.0f), B::New(true),
      F::New(float(sun.angleDeg)), B::New(true), B::New(true), HdRetainedSampledDataSource::New(VtValue(shadow)),
      HdRetainedSampledDataSource::New(VtValue(casters))};
  GfMatrix4d m(1);
  m.SetRotate(GfRotation(GfVec3d(0, 0, 1), sun.toward));  // a distant light shines down its −Z: its +Z faces the sun
  return HdRetainedContainerDataSource::New(
      HdLightSchemaTokens->light, HdRetainedContainerDataSource::New(std::size(names), names, values),
      HdXformSchemaTokens->xform,
      HdXformSchema::Builder().SetMatrix(HdRetainedTypedSampledDataSource<GfMatrix4d>::New(m)).Build(),
      HdVisibilitySchemaTokens->visibility, HdVisibilitySchema::BuildRetained(B::New(true)));
}

class SunScene;
std::vector<SunScene*>& scenes() {
  static std::vector<SunScene*> v;
  return v;
}

class SunScene final : public HdSingleInputFilteringSceneIndexBase {
 public:
  static HdSceneIndexBaseRefPtr New(const HdSceneIndexBaseRefPtr& in) { return TfCreateRefPtr(new SunScene(in)); }
  ~SunScene() override { scenes().erase(std::remove(scenes().begin(), scenes().end(), this), scenes().end()); }

  HdSceneIndexPrim GetPrim(const SdfPath& path) const override {
    if (path == kSun && state().sun) return {HdPrimTypeTokens->distantLight, sun_prim(*state().sun)};
    return _GetInputSceneIndex()->GetPrim(path);
  }
  SdfPathVector GetChildPrimPaths(const SdfPath& path) const override {
    SdfPathVector v = _GetInputSceneIndex()->GetChildPrimPaths(path);
    if (path == SdfPath::AbsoluteRootPath() && state().sun) v.push_back(kSun);
    return v;
  }
  void changed(bool had, bool has) {
    if (!had && has) _SendPrimsAdded({{kSun, HdPrimTypeTokens->distantLight}});
    else if (had && !has) _SendPrimsRemoved({{kSun}});
    else if (has)
      _SendPrimsDirtied({{kSun, HdDataSourceLocatorSet{HdLightSchema::GetDefaultLocator(),
                                                        HdXformSchema::GetDefaultLocator()}}});
  }

 protected:
  void _PrimsAdded(const HdSceneIndexBase&, const HdSceneIndexObserver::AddedPrimEntries& e) override {
    _SendPrimsAdded(e);
  }
  void _PrimsRemoved(const HdSceneIndexBase&, const HdSceneIndexObserver::RemovedPrimEntries& e) override {
    _SendPrimsRemoved(e);
  }
  void _PrimsDirtied(const HdSceneIndexBase&, const HdSceneIndexObserver::DirtiedPrimEntries& e) override {
    _SendPrimsDirtied(e);
  }

 private:
  explicit SunScene(const HdSceneIndexBaseRefPtr& in) : HdSingleInputFilteringSceneIndexBase(in) {
    scenes().push_back(this);
  }
};
}  // namespace

void register_storm_sun() {
  static const bool once = [] {
    HdSceneIndexPluginRegistry::GetInstance().RegisterSceneIndexForRenderer(
        "GL",  // Storm's display name (hdStorm plugInfo.json)
        [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle&) {
          return SunScene::New(in);
        },
        nullptr, 0, HdSceneIndexPluginRegistry::InsertionOrderAtEnd);
    return true;
  }();
  (void)once;
}

void set_storm_sun(const std::optional<StormSun>& sun, const SunShadow& shadow) {
  State& s = state();
  const bool had = bool(s.sun), has = bool(sun);
  const bool changed = had != has || (has && !(*sun == *s.sun));
  s.sun = sun;
  s.shadow = shadow;  // read by the shadow matrix at draw time: no re-sync needed when only the camera moved
  if (changed)
    for (SunScene* scene : scenes()) scene->changed(had, has);
}

SunShadow sun_shadow(const UsdStageRefPtr& stage, int frame, const GfFrustum& view) {
  UsdGeomBBoxCache cache(UsdTimeCode(frame), {UsdGeomTokens->default_, UsdGeomTokens->render});
  SunShadow out;
  out.scene = cache.ComputeWorldBound(stage->GetPseudoRoot()).ComputeAlignedRange();
  if (out.scene.IsEmpty()) return out;
  // the camera's view, out to the far side of the scene
  GfFrustum f = view;
  double far_d = 0;
  for (int i = 0; i < 8; ++i) far_d = std::max(far_d, (out.scene.GetCorner(i) - f.GetPosition()).GetLength());
  const double near_d = std::max(1e-3, f.GetNearFar().GetMin());
  f.SetNearFar(GfRange1d(near_d, std::max(far_d, near_d * 2)));
  GfRange3d seen;
  for (const GfVec3d& corner : f.ComputeCorners()) seen.UnionWith(corner);
  out.seen = GfRange3d::GetIntersection(out.scene, seen);
  if (out.seen.IsEmpty()) out.seen = out.scene;
  return out;
}

}  // namespace r3d
