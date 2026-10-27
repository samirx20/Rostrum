// Light -> type, transform, colour, UsdLux brightness (intensity, exposure, normalize, shape size,
// a spot's cone, a dome's picture), and the legacy stylized controls authored as constant primvars
// on the light (primvars:rostrum:ramp:positions / :colors / :smooth, rostrum:gain, rostrum:wrap,
// rostrum:shadow, rostrum:hemiUp, rostrum:enable). Custom light inputs (inputs:rostrum:...) are
// asked for first, but UsdImaging 26.03 does not pass them.
#include "prims.h"

#include <pxr/base/gf/half.h>
#include <pxr/base/tf/getenv.h>
#include <pxr/imaging/hd/lightSchema.h>
#include <pxr/imaging/hd/primvarsSchema.h>
#include <pxr/imaging/hd/renderIndex.h>
#include <pxr/imaging/hd/sceneDelegate.h>
#include <pxr/imaging/hd/sceneIndex.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hd/xformSchema.h>
#include <pxr/imaging/hio/image.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/usdLux/blackbody.h>

#include <algorithm>
#include <cmath>
#include <cstdio>

PXR_NAMESPACE_OPEN_SCOPE

namespace {

struct LightReader {
    HdContainerDataSourceHandle light, prim;

    VtValue Get(TfToken const &key) const
    {
        if (light)
            if (auto ds = HdSampledDataSource::Cast(light->Get(key))) return ds->GetValue(0.0f);
        if (auto ds = HdPrimvarsSchema::GetFromParent(prim).GetPrimvar(key).GetPrimvarValue())
            return ds->GetValue(0.0f);
        return VtValue();
    }
    VtValue Get(char const *name) const { return Get(TfToken(name)); }
    template <class T> T Typed(TfToken const &key, T fallback) const
    {
        VtValue v = Get(key);
        if (v.IsHolding<T>()) return v.UncheckedGet<T>();
        if (v.IsHolding<VtArray<T>>() && !v.UncheckedGet<VtArray<T>>().empty())
            return v.UncheckedGet<VtArray<T>>()[0];
        if constexpr (std::is_same_v<T, float>)
            if (v.IsHolding<double>()) return float(v.UncheckedGet<double>());
        return fallback;
    }
    template <class T> T Typed(char const *name, T fallback) const { return Typed<T>(TfToken(name), fallback); }
};

// What a white matte surface facing straight up / straight down shows under a dome whose picture is
// `path` (lat-long, +Y up, top row = straight up), at gain 1: the picture's cosine-weighted light over
// that half of the sky / pi. A dome with no picture shows 1 both ways. Read once per file.
std::pair<GfVec3f, GfVec3f> DomeBrightness(std::string const &path)
{
    static std::mutex lock;
    static std::map<std::string, std::pair<GfVec3f, GfVec3f>> cache;
    std::pair<GfVec3f, GfVec3f> flat{GfVec3f(1), GfVec3f(1)};
    if (path.empty()) return flat;
    std::lock_guard<std::mutex> g(lock);
    auto it = cache.find(path);
    if (it != cache.end()) return it->second;
    std::pair<GfVec3f, GfVec3f> out = flat;
    HioImageSharedPtr img = HioImage::OpenForReading(path);
    bool ok = false;
    if (img) {
        HioImage::StorageSpec spec;
        spec.width = img->GetWidth();
        spec.height = img->GetHeight();
        spec.format = img->GetFormat();
        spec.flipped = false;
        HioType type = HioGetHioType(spec.format);
        int n = HioGetComponentCount(spec.format);
        size_t texel = HioGetDataSizeOfFormat(spec.format);
        std::vector<unsigned char> px(size_t(spec.width) * spec.height * texel);
        spec.data = px.data();
        if ((type == HioTypeFloat || type == HioTypeHalfFloat) && n >= 3 && spec.width > 0 && spec.height > 0 &&
            img->Read(spec)) {
            int const w = spec.width, h = spec.height;
            double up[3] = {0, 0, 0}, down[3] = {0, 0, 0};
            for (int v = 0; v < h; ++v) {
                double polar = (v + 0.5) / h * M_PI;
                double cosv = std::cos(polar), dw = (2 * M_PI / w) * (M_PI / h) * std::sin(polar);
                double row[3] = {0, 0, 0};
                for (int u = 0; u < w; ++u) {
                    unsigned char const *t = px.data() + (size_t(v) * w + u) * texel;
                    for (int c = 0; c < 3; ++c)
                        row[c] += type == HioTypeFloat ? double(reinterpret_cast<float const *>(t)[c])
                                                       : double(float(reinterpret_cast<GfHalf const *>(t)[c]));
                }
                for (int c = 0; c < 3; ++c) (cosv > 0 ? up : down)[c] += row[c] * std::abs(cosv) * dw;
            }
            out = {GfVec3f(float(up[0] / M_PI), float(up[1] / M_PI), float(up[2] / M_PI)),
                   GfVec3f(float(down[0] / M_PI), float(down[1] / M_PI), float(down[2] / M_PI))};
            ok = true;
        }
    }
    if (!ok)
        fprintf(stderr, "Rostrum Stylized: cannot read the dome picture %s (a float image is needed); "
                        "lighting it as a flat dome\n", path.c_str());
    cache[path] = out;
    return out;
}

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
    l.color = r.Typed<GfVec3f>(HdLightTokens->color, GfVec3f(1));
    if (r.Typed<bool>(HdLightTokens->enableColorTemperature, false))
        l.color = GfCompMult(l.color, UsdLuxBlackbodyTemperatureAsRgb(
                                          r.Typed<float>(HdLightTokens->colorTemperature, 6500.0f)));
    l.intensity = r.Typed<float>(HdLightTokens->intensity, 1.0f) *
                  std::exp2(r.Typed<float>(HdLightTokens->exposure, 0.0f));
    l.normalize = r.Typed<bool>(HdLightTokens->normalize, false);
    // the shape in world units: the light's own scale applies (a sphere / disk: its largest)
    double sx = l.xform.GetRow3(0).GetLength(), sy = l.xform.GetRow3(1).GetLength(),
           sz = l.xform.GetRow3(2).GetLength();
    l.width = float(r.Typed<float>(HdLightTokens->width, 1.0f) * sx);
    l.height = float(r.Typed<float>(HdLightTokens->height, 1.0f) * sy);
    l.radius = float(r.Typed<float>(HdLightTokens->radius, 0.5f) * std::max({sx, sy, sz}));
    if (_type == HdPrimTypeTokens->sphereLight) {
        l.coneAngle = r.Typed<float>(HdLightTokens->shapingConeAngle, 180.0f);
        l.coneSoftness = r.Typed<float>(HdLightTokens->shapingConeSoftness, 0.0f);
    }
    if (_type == HdPrimTypeTokens->domeLight) {
        SdfAssetPath tex = r.Typed<SdfAssetPath>(HdLightTokens->textureFile, SdfAssetPath());
        std::string file = tex.GetResolvedPath().empty() ? tex.GetAssetPath() : tex.GetResolvedPath();
        auto [up, down] = DomeBrightness(file);
        // the core's own floor level for this dome (light_to_color.cpp, what Cycles' Light to colour counts) wins,
        // so "how lit" is the same number in both; the picture's up / down balance is kept
        GfVec3f level = r.Typed<GfVec3f>("rostrum:domeLevel", GfVec3f(-1.0f));
        if (level[0] >= 0.0f) {
            for (int c = 0; c < 3; ++c) {
                float k = up[c] > 1e-6f ? level[c] / up[c] : 1.0f;
                up[c] *= k;
                down[c] *= k;
            }
        }
        l.domeUp = up;
        l.domeDown = down;
        l.domeFile = file;
    }
    l.gain = r.Typed<float>("rostrum:gain", 1.0f);
    l.wrap = r.Typed<float>("rostrum:wrap", 0.0f);
    VtValue shadow = r.Get("rostrum:shadow");
    if (shadow.IsHolding<bool>()) l.shadow = shadow.UncheckedGet<bool>();
    else if (shadow.IsHolding<VtBoolArray>() && !shadow.UncheckedGet<VtBoolArray>().empty())
        l.shadow = shadow.UncheckedGet<VtBoolArray>()[0];
    else l.shadow = r.Typed<bool>(HdLightTokens->shadowEnable, true);
    if (_type == HdPrimTypeTokens->domeLight) l.shadow = false;
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
        printf("[rostrum] light %s type=%s intensity=%.3f normalize=%d size=(%.2f %.2f r %.2f) ramp=%zu "
               "color=(%.2f %.2f %.2f)\n", id.GetText(), _type.GetText(), l.intensity, int(l.normalize), l.width,
               l.height, l.radius, l.ramp.positions.size(), l.color[0], l.color[1], l.color[2]);

    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->lights[id] = std::move(l);
    ++_scene->lightsVersion;
    *bits = Clean;
}

PXR_NAMESPACE_CLOSE_SCOPE
