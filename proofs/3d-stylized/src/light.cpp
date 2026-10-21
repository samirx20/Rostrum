// P-3D-3: light -> type, transform, colour, and the stylized controls authored on the light
// (rostrum:ramp:positions / :colors / :smooth, rostrum:gain, rostrum:wrap, rostrum:shadow,
// rostrum:hemiUp, rostrum:enable), authored as constant primvars on the light (primvars:rostrum:...).
// Custom light inputs (inputs:rostrum:...) are asked for first, but UsdImaging 26.03 does not pass them.
#include "prims.h"

#include <pxr/base/tf/getenv.h>
#include <pxr/imaging/hd/lightSchema.h>
#include <pxr/imaging/hd/primvarsSchema.h>
#include <pxr/imaging/hd/renderIndex.h>
#include <pxr/imaging/hd/sceneDelegate.h>
#include <pxr/imaging/hd/sceneIndex.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hd/xformSchema.h>
#include <pxr/usd/usdLux/blackbody.h>

PXR_NAMESPACE_OPEN_SCOPE

namespace {

struct LightReader {
    HdContainerDataSourceHandle light, prim;

    VtValue Get(char const *name) const
    {
        TfToken key(name);
        if (light)
            if (auto ds = HdSampledDataSource::Cast(light->Get(key))) return ds->GetValue(0.0f);
        if (auto ds = HdPrimvarsSchema::GetFromParent(prim).GetPrimvar(key).GetPrimvarValue())
            return ds->GetValue(0.0f);
        return VtValue();
    }
    template <class T> T Typed(char const *name, T fallback) const
    {
        VtValue v = Get(name);
        if (v.IsHolding<T>()) return v.UncheckedGet<T>();
        if (v.IsHolding<VtArray<T>>() && !v.UncheckedGet<VtArray<T>>().empty())
            return v.UncheckedGet<VtArray<T>>()[0];
        if constexpr (std::is_same_v<T, float>)
            if (v.IsHolding<double>()) return float(v.UncheckedGet<double>());
        return fallback;
    }
};

}  // namespace

HdRostrumLight::~HdRostrumLight()
{
    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->lights.erase(GetId());
    ++_scene->lightsVersion;
}

void HdRostrumLight::Sync(HdSceneDelegate *sd, HdRenderParam *, HdDirtyBits *bits)
{
    SdfPath const &id = GetId();
    HdSceneIndexPrim prim = sd->GetRenderIndex().GetTerminalSceneIndex()->GetPrim(id);
    LightReader r{HdLightSchema::GetFromParent(prim.dataSource).GetContainer(), prim.dataSource};

    RostrumLightData l;
    l.type = _type;
    if (auto m = HdXformSchema::GetFromParent(prim.dataSource).GetMatrix()) l.xform = m->GetTypedValue(0.0f);
    l.color = r.Typed<GfVec3f>("color", GfVec3f(1));
    if (r.Typed<bool>("enableColorTemperature", false))
        l.color = GfCompMult(l.color, UsdLuxBlackbodyTemperatureAsRgb(r.Typed<float>("colorTemperature", 6500)));
    l.gain = r.Typed<float>("rostrum:gain", 1.0f);
    l.wrap = r.Typed<float>("rostrum:wrap", 0.0f);
    l.shadow = r.Typed<bool>("rostrum:shadow", _type != HdPrimTypeTokens->domeLight);
    l.enabled = r.Typed<bool>("rostrum:enable", true);
    l.hemiUp = r.Typed<GfVec3f>("rostrum:hemiUp", GfVec3f(0, 1, 0));
    l.ramp.smooth = r.Typed<float>("rostrum:ramp:smooth", 0.0f);
    VtValue pos = r.Get("rostrum:ramp:positions"), col = r.Get("rostrum:ramp:colors");
    if (pos.IsHolding<VtFloatArray>() && col.IsHolding<VtVec3fArray>()) {
        VtFloatArray const &p = pos.UncheckedGet<VtFloatArray>();
        VtVec3fArray const &c = col.UncheckedGet<VtVec3fArray>();
        if (p.size() != c.size() || p.empty())
            TF_WARN("Rostrum Stylized: light %s: rostrum:ramp:positions (%zu) and :colors (%zu) differ",
                    id.GetText(), p.size(), c.size());
        else {
            l.ramp.positions.assign(p.begin(), p.end());
            l.ramp.colors.assign(c.begin(), c.end());
        }
    }
    if (TfGetenvBool("ROSTRUM_DEBUG", false))
        printf("[rostrum] light %s type=%s ramp=%zu gain=%.2f color=(%.2f %.2f %.2f)\n", id.GetText(),
               _type.GetText(), l.ramp.positions.size(), l.gain, l.color[0], l.color[1], l.color[2]);

    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->lights[id] = std::move(l);
    ++_scene->lightsVersion;
    *bits = Clean;
}

PXR_NAMESPACE_CLOSE_SCOPE
