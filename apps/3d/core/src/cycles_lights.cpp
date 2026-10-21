#include "cycles_lights.h"

#include <pxr/base/tf/diagnostic.h>
#include <pxr/imaging/hd/filteringSceneIndex.h>
#include <pxr/imaging/hd/light.h>
#include <pxr/imaging/hd/lightSchema.h>
#include <pxr/imaging/hd/overlayContainerDataSource.h>
#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/usdLux/blackbody.h>

#include <cmath>
#include <iterator>

#include "error.h"
#include "sky.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
constexpr float kPi = 3.14159265358979323846f;
constexpr float kCyclesDistant = 4.0f;  // hydra/light.cpp's factor on a distant light's strength

template <class T>
T value(const HdContainerDataSourceHandle& ds, const TfToken& name, T fallback) {
  if (auto d = HdTypedSampledDataSource<T>::Cast(ds ? ds->Get(name) : nullptr)) return d->GetTypedValue(0.0f);
  return fallback;
}

using F = HdRetainedTypedSampledDataSource<float>;

// the dome's light as the picture alone (strength 1): see cycles_lights.h
HdContainerDataSourceHandle dome_params(const HdContainerDataSourceHandle& light) {
  GfVec3f gain = value(light, HdLightTokens->color, GfVec3f(1)) * value(light, HdLightTokens->intensity, 1.0f) *
                 std::exp2(value(light, HdLightTokens->exposure, 0.0f));
  if (value(light, HdLightTokens->enableColorTemperature, false))
    gain = GfCompMult(gain, UsdLuxBlackbodyTemperatureAsRgb(value(light, HdLightTokens->colorTemperature, 6500.0f)));
  const SdfAssetPath tex = value(light, HdLightTokens->textureFile, SdfAssetPath());
  const std::string source = tex.GetResolvedPath().empty() ? tex.GetAssetPath() : tex.GetResolvedPath();
  const std::string picture = dome_picture(source, gain);
  const TfToken names[] = {HdLightTokens->color, HdLightTokens->intensity, HdLightTokens->exposure,
                           HdLightTokens->enableColorTemperature, HdLightTokens->textureFile};
  const HdDataSourceBaseHandle values[] = {
      HdRetainedTypedSampledDataSource<GfVec3f>::New(GfVec3f(1)), F::New(1.0f / kPi), F::New(0.0f),
      HdRetainedTypedSampledDataSource<bool>::New(false),
      HdRetainedTypedSampledDataSource<SdfAssetPath>::New(SdfAssetPath(picture, picture))};
  return HdRetainedContainerDataSource::New(std::size(names), names, values);
}

HdContainerDataSourceHandle distant_params(const HdContainerDataSourceHandle& light) {
  return HdRetainedContainerDataSource::New(
      HdLightTokens->intensity, F::New(value(light, HdLightTokens->intensity, 1.0f) / kCyclesDistant));
}

class CyclesLights final : public HdSingleInputFilteringSceneIndexBase {
 public:
  static HdSceneIndexBaseRefPtr New(const HdSceneIndexBaseRefPtr& in) { return TfCreateRefPtr(new CyclesLights(in)); }

  HdSceneIndexPrim GetPrim(const SdfPath& path) const override {
    HdSceneIndexPrim prim = _GetInputSceneIndex()->GetPrim(path);
    const bool dome = prim.primType == HdPrimTypeTokens->domeLight;
    if ((!dome && prim.primType != HdPrimTypeTokens->distantLight) || !prim.dataSource) return prim;
    const HdContainerDataSourceHandle light = HdLightSchema::GetFromParent(prim.dataSource).GetContainer();
    HdContainerDataSourceHandle params;
    try {
      params = dome ? dome_params(light) : distant_params(light);
    } catch (const Error& e) {  // reported after the render by hydra.cpp (throw_usd_errors): never a quiet wrong sky
      TF_RUNTIME_ERROR("%s: %s", path.GetText(), e.what());
      return prim;
    }
    prim.dataSource = HdOverlayContainerDataSource::New(
        HdRetainedContainerDataSource::New(HdLightSchemaTokens->light, params), prim.dataSource);
    return prim;
  }
  SdfPathVector GetChildPrimPaths(const SdfPath& path) const override {
    return _GetInputSceneIndex()->GetChildPrimPaths(path);
  }

 protected:
  void _PrimsAdded(const HdSceneIndexBase&, const HdSceneIndexObserver::AddedPrimEntries& e) override {
    _SendPrimsAdded(e);
  }
  void _PrimsRemoved(const HdSceneIndexBase&, const HdSceneIndexObserver::RemovedPrimEntries& e) override {
    _SendPrimsRemoved(e);
  }
  void _PrimsDirtied(const HdSceneIndexBase&, const HdSceneIndexObserver::DirtiedPrimEntries& e) override {
    _SendPrimsDirtied(e);  // the numbers are made when read, so an animated light stays right
  }

 private:
  explicit CyclesLights(const HdSceneIndexBaseRefPtr& in) : HdSingleInputFilteringSceneIndexBase(in) {}
};
}  // namespace

void register_cycles_lights() {
  static const bool once = [] {
    HdSceneIndexPluginRegistry::GetInstance().RegisterSceneIndexForRenderer(
        "Cycles",
        [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle&) {
          return CyclesLights::New(in);
        },
        nullptr, 0, HdSceneIndexPluginRegistry::InsertionOrderAtStart);
    return true;
  }();
  (void)once;
}

}  // namespace r3d
