#include "cycles_lights.h"

#include <pxr/base/tf/diagnostic.h>
#include <pxr/imaging/hd/filteringSceneIndex.h>
#include <pxr/imaging/hd/light.h>
#include <pxr/imaging/hd/lightSchema.h>
#include <pxr/imaging/hd/overlayContainerDataSource.h>
#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hd/visibilitySchema.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/usdLux/blackbody.h>

#include <algorithm>
#include <cmath>
#include <iterator>
#include <set>
#include <vector>

#include "error.h"
#include "light_extras.h"
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
using F0 = HdRetainedTypedSampledDataSource<bool>;

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

// product lighting (light_extras.h): what our patch on Cycles' Hydra plug-in reads; none of it for a plain light
HdContainerDataSourceHandle extras_params(const SdfPath& path, const TfToken& type, const LightExtras& x) {
  std::vector<TfToken> names;
  std::vector<HdDataSourceBaseHandle> values;
  auto add = [&](const TfToken& n, HdDataSourceBaseHandle v) { names.push_back(n), values.push_back(std::move(v)); };
  if (type == HdPrimTypeTokens->domeLight) {
    const auto seen = x.domeSeen.find(path);  // Cycles: the background's camera visibility (patch: session.cpp)
    add(TfToken("visibleInPrimaryRay"), HdRetainedTypedSampledDataSource<bool>::New(seen == x.domeSeen.end() || seen->second));
  }
  if (x.cards.count(path)) add(TfToken("visibleInPrimaryRay"), HdRetainedTypedSampledDataSource<bool>::New(true));
  if (const auto c = x.coneDeg.find(path); c != x.coneDeg.end()) add(HdLightTokens->shapingConeAngle, F::New(c->second));
  if (const auto m = x.membership.find(path); m != x.membership.end())
    add(TfToken("rostrumLightSets"), HdRetainedTypedSampledDataSource<int64_t>::New(int64_t(m->second)));
  if (names.empty()) return nullptr;
  return HdRetainedContainerDataSource::New(names.size(), names.data(), values.data());
}

HdContainerDataSourceHandle with_light(const HdContainerDataSourceHandle& prim, HdContainerDataSourceHandle params) {
  return HdOverlayContainerDataSource::New(HdRetainedContainerDataSource::New(HdLightSchemaTokens->light, params), prim);
}

class CyclesLights;
std::vector<CyclesLights*> g_live;  // every Cycles engine's filter, for announce_light_extras()

class CyclesLights final : public HdSingleInputFilteringSceneIndexBase {
 public:
  static HdSceneIndexBaseRefPtr New(const HdSceneIndexBaseRefPtr& in) { return TfCreateRefPtr(new CyclesLights(in)); }
  ~CyclesLights() override { g_live.erase(std::remove(g_live.begin(), g_live.end(), this), g_live.end()); }
  void announce(const HdSceneIndexObserver::DirtiedPrimEntries& e) { _SendPrimsDirtied(e); }

  HdSceneIndexPrim GetPrim(const SdfPath& path) const override {
    HdSceneIndexPrim prim = _GetInputSceneIndex()->GetPrim(path);
    if (!prim.dataSource) return prim;
    const LightExtras& x = light_extras();
    if (!HdPrimTypeIsLight(prim.primType)) {
      if (path.GetName() == kCardName)  // Storm's card: in Cycles the light itself is seen (visibleInPrimaryRay)
        prim.dataSource = HdOverlayContainerDataSource::New(
            HdRetainedContainerDataSource::New(HdVisibilitySchemaTokens->visibility,
                                               HdVisibilitySchema::BuildRetained(F0::New(false))),
            prim.dataSource);
      else if (const int set = x.receiver_set(path))  // light linking: the receiver set (patch: geometry.inl)
        prim.dataSource = HdOverlayContainerDataSource::New(
            HdRetainedContainerDataSource::New(TfToken("rostrumLightSet"), HdRetainedTypedSampledDataSource<int>::New(set)),
            prim.dataSource);
      return prim;
    }
    const bool dome = prim.primType == HdPrimTypeTokens->domeLight;
    if (const auto extras = extras_params(path, prim.primType, x)) prim.dataSource = with_light(prim.dataSource, extras);
    if (!dome && prim.primType != HdPrimTypeTokens->distantLight) return prim;
    const HdContainerDataSourceHandle light = HdLightSchema::GetFromParent(prim.dataSource).GetContainer();
    HdContainerDataSourceHandle params;
    try {
      params = dome ? dome_params(light) : distant_params(light);
    } catch (const Error& e) {  // reported after the render by hydra.cpp (throw_usd_errors): never a quiet wrong sky
      TF_RUNTIME_ERROR("%s: %s", path.GetText(), e.what());
      return prim;
    }
    prim.dataSource = with_light(prim.dataSource, params);
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
  explicit CyclesLights(const HdSceneIndexBaseRefPtr& in) : HdSingleInputFilteringSceneIndexBase(in) { g_live.push_back(this); }
};

// The paths whose product lighting a filter hands over: lights (their params) and linked items (re-synced geometry).
std::pair<std::set<SdfPath>, std::set<SdfPath>> extras_paths(const LightExtras& x) {
  std::set<SdfPath> lights(x.cards.begin(), x.cards.end()), items;
  for (const auto& [p, v] : x.coneDeg) lights.insert(p);
  for (const auto& [p, v] : x.domeSeen) lights.insert(p);
  for (const auto& [p, v] : x.membership) lights.insert(p);
  for (const auto& [p, v] : x.receivers) items.insert(p);
  return {lights, items};
}
}  // namespace

void announce_light_extras() {
  static std::set<SdfPath> was_lights, was_items;
  auto [lights, items] = extras_paths(light_extras());
  HdSceneIndexObserver::DirtiedPrimEntries e;
  for (const auto* set : {&lights, &was_lights})
    for (const SdfPath& p : *set) e.emplace_back(p, HdDataSourceLocatorSet{HdLightSchema::GetDefaultLocator()});
  for (const auto* set : {&items, &was_items})
    for (const SdfPath& p : *set) e.emplace_back(p, HdDataSourceLocatorSet{HdVisibilitySchema::GetDefaultLocator()});
  if (!e.empty())
    for (CyclesLights* f : g_live) f->announce(e);
  was_lights = std::move(lights), was_items = std::move(items);
}

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
