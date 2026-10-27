// The Rostrum Stylized render delegate: which prims it takes, and the AOVs it writes.
#include "delegate.h"
#include "prims.h"
#include "renderBuffer.h"
#include "renderPass.h"

#include <pxr/imaging/hd/camera.h>
#include <pxr/imaging/hd/tokens.h>

PXR_NAMESPACE_OPEN_SCOPE

HdRostrumDelegate::HdRostrumDelegate(HdRenderSettingsMap const &settings)
    : HdRenderDelegate(settings), _registry(std::make_shared<HdResourceRegistry>())
{
}

TfTokenVector const &HdRostrumDelegate::GetSupportedRprimTypes() const
{
    static TfTokenVector t = {HdPrimTypeTokens->mesh};
    return t;
}

TfTokenVector const &HdRostrumDelegate::GetSupportedSprimTypes() const
{
    static TfTokenVector t = {HdPrimTypeTokens->camera,      HdPrimTypeTokens->material,
                              HdPrimTypeTokens->distantLight, HdPrimTypeTokens->domeLight,
                              HdPrimTypeTokens->rectLight,    HdPrimTypeTokens->sphereLight,
                              HdPrimTypeTokens->diskLight};
    return t;
}

TfTokenVector const &HdRostrumDelegate::GetSupportedBprimTypes() const
{
    static TfTokenVector t = {HdPrimTypeTokens->renderBuffer};
    return t;
}

HdRenderPassSharedPtr HdRostrumDelegate::CreateRenderPass(HdRenderIndex *index,
                                                          HdRprimCollection const &collection)
{
    return std::make_shared<HdRostrumRenderPass>(index, collection, this);
}

HdRprim *HdRostrumDelegate::CreateRprim(TfToken const &typeId, SdfPath const &id)
{
    if (typeId == HdPrimTypeTokens->mesh) return new HdRostrumMesh(id, &_scene);
    TF_CODING_ERROR("Rostrum Stylized: unknown rprim type %s", typeId.GetText());
    return nullptr;
}

void HdRostrumDelegate::DestroyRprim(HdRprim *prim) { delete prim; }

HdSprim *HdRostrumDelegate::CreateSprim(TfToken const &typeId, SdfPath const &id)
{
    if (typeId == HdPrimTypeTokens->camera) return new HdCamera(id);
    if (typeId == HdPrimTypeTokens->material) return new HdRostrumMaterial(id, &_scene);
    return new HdRostrumLight(id, typeId, &_scene);  // every other supported sprim is a light
}

HdSprim *HdRostrumDelegate::CreateFallbackSprim(TfToken const &typeId)
{
    return CreateSprim(typeId, SdfPath::EmptyPath());
}

void HdRostrumDelegate::DestroySprim(HdSprim *prim) { delete prim; }

HdBprim *HdRostrumDelegate::CreateBprim(TfToken const &, SdfPath const &id)
{
    return new HdRostrumRenderBuffer(id);
}

HdBprim *HdRostrumDelegate::CreateFallbackBprim(TfToken const &)
{
    return new HdRostrumRenderBuffer(SdfPath::EmptyPath());
}

void HdRostrumDelegate::DestroyBprim(HdBprim *prim) { delete prim; }

HdAovDescriptor HdRostrumDelegate::GetDefaultAovDescriptor(TfToken const &name) const
{
    if (name == HdAovTokens->color) return HdAovDescriptor(HdFormatFloat16Vec4, false, VtValue(GfVec4f(0)));
    if (name == HdAovTokens->depth) return HdAovDescriptor(HdFormatFloat32, false, VtValue(1.0f));
    if (name == HdAovTokens->primId || name == HdAovTokens->instanceId ||
        name == HdAovTokens->elementId)
        return HdAovDescriptor(HdFormatInt32, false, VtValue(-1));
    return HdAovDescriptor();
}

TfTokenVector HdRostrumDelegate::GetMaterialRenderContexts() const
{
    // the core's `rostrum_stylized` node (outputs:rostrum:surface), else the universal surface
    // (UsdPreviewSurface). Hydra falls back to the universal one anyway; it is listed so the
    // fallback doesn't depend on which path (scene index or legacy) asks.
    return {TfToken("rostrum"), TfToken("")};
}

std::map<std::string, float> HdRostrumDelegate::LookSettings() const
{
    std::map<std::string, float> out;
    for (auto const &[key, value] : _settingsMap) {
        if (key.GetString().rfind("rostrum:", 0) != 0) continue;
        if (value.IsHolding<float>()) out[key] = value.UncheckedGet<float>();
        else if (value.IsHolding<double>()) out[key] = float(value.UncheckedGet<double>());
        else if (value.IsHolding<int>()) out[key] = float(value.UncheckedGet<int>());
        else if (value.IsHolding<bool>()) out[key] = value.UncheckedGet<bool>() ? 1.0f : 0.0f;
        else if (value.IsHolding<GfVec3f>() || value.IsHolding<GfVec3d>()) {
            GfVec3f v = value.IsHolding<GfVec3f>() ? value.UncheckedGet<GfVec3f>()
                                                   : GfVec3f(value.UncheckedGet<GfVec3d>());
            for (int i = 0; i < 3; ++i) out[key.GetString() + ":" + "xyz"[i]] = v[i];
        }
        else TF_WARN("Rostrum Stylized: setting %s has an unsupported type %s", key.GetText(),
                     value.GetTypeName().c_str());
    }
    return out;
}

PXR_NAMESPACE_CLOSE_SCOPE
