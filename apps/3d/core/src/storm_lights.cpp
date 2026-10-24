#include "storm_lights.h"

#include <pxr/imaging/hd/filteringSceneIndex.h>
#include <pxr/imaging/hd/light.h>
#include <pxr/imaging/hd/lightSchema.h>
#include <pxr/imaging/hd/overlayContainerDataSource.h>
#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hd/xformSchema.h>

#include <algorithm>
#include <cmath>
#include <vector>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
template <class T>
T value(const HdContainerDataSourceHandle& ds, const TfToken& name, T fallback) {
  if (auto d = HdTypedSampledDataSource<T>::Cast(ds ? ds->Get(name) : nullptr)) return d->GetTypedValue(0.0f);
  return fallback;
}

// Storm's focus for a cone (UsdLux half angle, degrees) and softness: pow(cos θ, focus) = ½ in the middle of Cycles'
// fade, cos_half + (1 − cos_half) · softness / 2. 0 (no fall-off, a hard edge) without softness.
float focus_for(double cone_deg, double softness) {
  if (!(softness > 0) || !(cone_deg > 0) || cone_deg >= 90) return 0.0f;
  const double c = std::cos(cone_deg * 3.14159265358979323846 / 180.0);
  const double mid = c + (1 - c) * std::min(softness, 1.0) / 2;
  return float(std::log(0.5) / std::log(mid));
}

// a sphere light with a shaping cone is a spot (lights_cameras.cpp), else a bulb
bool is_spot(const HdContainerDataSourceHandle& light) { return bool(light->Get(HdLightTokens->shapingConeAngle)); }

// a sphere light's world surface area (its radius times its largest world scale)
double sphere_area(const HdContainerDataSourceHandle& prim, const HdContainerDataSourceHandle& light) {
  GfMatrix4d m(1.0);
  if (auto x = HdXformSchema::GetFromParent(prim).GetMatrix()) m = x->GetTypedValue(0.0f);
  const double s = std::max({m.GetRow3(0).GetLength(), m.GetRow3(1).GetLength(), m.GetRow3(2).GetLength()});
  const double r = value(light, HdLightTokens->radius, 0.5f) * s;
  return 4 * 3.14159265358979323846 * r * r;
}

class StormLights final : public HdSingleInputFilteringSceneIndexBase {
 public:
  static HdSceneIndexBaseRefPtr New(const HdSceneIndexBaseRefPtr& in) { return TfCreateRefPtr(new StormLights(in)); }

  HdSceneIndexPrim GetPrim(const SdfPath& path) const override {
    HdSceneIndexPrim prim = _GetInputSceneIndex()->GetPrim(path);
    if (prim.primType != HdPrimTypeTokens->sphereLight || !prim.dataSource) return prim;
    const HdContainerDataSourceHandle light = HdLightSchema::GetFromParent(prim.dataSource).GetContainer();
    if (!light) return prim;
    if (is_spot(light)) prim.primType = HdPrimTypeTokens->diskLight;
    std::vector<TfToken> names;
    std::vector<HdDataSourceBaseHandle> values;
    using F = HdRetainedTypedSampledDataSource<float>;
    if (value(light, HdLightTokens->normalize, false)) {
      const double area = sphere_area(prim.dataSource, light);
      names.push_back(HdLightTokens->normalize), values.push_back(HdRetainedTypedSampledDataSource<bool>::New(false));
      names.push_back(HdLightTokens->intensity);
      values.push_back(F::New(area > 0 ? float(value(light, HdLightTokens->intensity, 1.0f) / area) : 0.0f));
    }
    if (is_spot(light)) {
      names.push_back(HdLightTokens->shapingFocus);
      values.push_back(F::New(focus_for(value(light, HdLightTokens->shapingConeAngle, 90.0f),
                                        value(light, HdLightTokens->shapingConeSoftness, 0.0f))));
    }
    if (names.empty()) return prim;
    prim.dataSource = HdOverlayContainerDataSource::New(
        HdRetainedContainerDataSource::New(HdLightSchemaTokens->light,
                                           HdRetainedContainerDataSource::New(names.size(), names.data(), values.data())),
        prim.dataSource);
    return prim;
  }
  SdfPathVector GetChildPrimPaths(const SdfPath& path) const override {
    return _GetInputSceneIndex()->GetChildPrimPaths(path);
  }

 protected:
  void _PrimsAdded(const HdSceneIndexBase&, const HdSceneIndexObserver::AddedPrimEntries& e) override {
    HdSceneIndexObserver::AddedPrimEntries out(e);  // Storm makes its light by the type it is added with
    for (auto& a : out)
      if (a.primType == HdPrimTypeTokens->sphereLight) a.primType = GetPrim(a.primPath).primType;
    _SendPrimsAdded(out);
  }
  void _PrimsRemoved(const HdSceneIndexBase&, const HdSceneIndexObserver::RemovedPrimEntries& e) override {
    _SendPrimsRemoved(e);
  }
  void _PrimsDirtied(const HdSceneIndexBase&, const HdSceneIndexObserver::DirtiedPrimEntries& e) override {
    _SendPrimsDirtied(e);  // the numbers are made when read, so an animated light stays right
  }

 private:
  explicit StormLights(const HdSceneIndexBaseRefPtr& in) : HdSingleInputFilteringSceneIndexBase(in) {}
};
}  // namespace

void register_storm_lights() {
  static const bool once = [] {
    HdSceneIndexPluginRegistry::GetInstance().RegisterSceneIndexForRenderer(
        "GL",  // Storm's display name (hdStorm plugInfo.json)
        [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle&) {
          return StormLights::New(in);
        },
        nullptr, 0, HdSceneIndexPluginRegistry::InsertionOrderAtEnd);
    return true;
  }();
  (void)once;
}

}  // namespace r3d
