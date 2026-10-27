// Material -> RostrumMaterialData. The core writes a `rostrum_stylized` node per material on the
// "rostrum" render context (outputs:rostrum:surface): every stylized setting is read from it, and its
// baseColor's link is followed to the image file. Without that node (another stage, a plain
// UsdPreviewSurface, Cycles' own graphs) only the base colour / image and the glow are read.
#include "prims.h"

#include <pxr/imaging/hd/sceneDelegate.h>
#include <pxr/usd/sdf/assetPath.h>

#include <algorithm>

PXR_NAMESPACE_OPEN_SCOPE

namespace {

bool EndsWith(std::string const &s, char const *tail)
{
    std::string t(tail);
    return s.size() >= t.size() && s.compare(s.size() - t.size(), t.size(), t) == 0;
}

std::string AssetPath(VtValue const &v)
{
    if (!v.IsHolding<SdfAssetPath>()) return "";
    SdfAssetPath const &a = v.UncheckedGet<SdfAssetPath>();
    return a.GetResolvedPath().empty() ? a.GetAssetPath() : a.GetResolvedPath();
}

// the image file wired straight into `node.input` ("" when a value or another node feeds it)
std::string TextureInto(HdMaterialNetwork const &net, SdfPath const &node, TfToken const &input)
{
    for (HdMaterialRelationship const &r : net.relationships) {
        if (r.outputId != node || r.outputName != input) continue;
        for (HdMaterialNode const &n : net.nodes) {
            if (n.path != r.inputId) continue;
            for (char const *key : {"filename", "file"}) {
                auto it = n.parameters.find(TfToken(key));
                if (it != n.parameters.end() && !AssetPath(it->second).empty()) return AssetPath(it->second);
            }
        }
    }
    return "";
}

// one authored input of a node, leniently typed (USD may hand a float as a double, a bool as an int)
struct Params {
    std::map<TfToken, VtValue> const &p;

    VtValue const *Find(char const *name) const
    {
        auto it = p.find(TfToken(name));
        return it == p.end() ? nullptr : &it->second;
    }
    float Float(char const *name, float fallback) const
    {
        VtValue const *v = Find(name);
        if (!v) return fallback;
        if (v->IsHolding<float>()) return v->UncheckedGet<float>();
        if (v->IsHolding<double>()) return float(v->UncheckedGet<double>());
        if (v->IsHolding<int>()) return float(v->UncheckedGet<int>());
        return fallback;
    }
    bool Bool(char const *name, bool fallback) const
    {
        VtValue const *v = Find(name);
        if (!v) return fallback;
        if (v->IsHolding<bool>()) return v->UncheckedGet<bool>();
        if (v->IsHolding<int>()) return v->UncheckedGet<int>() != 0;
        if (v->IsHolding<float>()) return v->UncheckedGet<float>() != 0.0f;
        return fallback;
    }
    GfVec3f Color(char const *name, GfVec3f fallback) const
    {
        VtValue const *v = Find(name);
        if (!v) return fallback;
        if (v->IsHolding<GfVec3f>()) return v->UncheckedGet<GfVec3f>();
        if (v->IsHolding<GfVec3d>()) return GfVec3f(v->UncheckedGet<GfVec3d>());
        return fallback;
    }
};

void ReadStylized(HdMaterialNetwork const &net, HdMaterialNode const &n, RostrumMaterialData &m)
{
    Params p{n.parameters};
    m.baseColor = p.Color("baseColor", m.baseColor);
    m.texture = TextureInto(net, n.path, TfToken("baseColor"));
    m.emission = p.Color("emission", m.emission);
    m.lines = p.Bool("lines", m.lines);
    m.linesWidth = p.Float("linesWidth", m.linesWidth);
    m.linesColor = p.Color("linesColor", m.linesColor);
    m.linesTaper = p.Float("linesTaper", m.linesTaper);
    m.linesWobble = p.Float("linesWobble", m.linesWobble);
    m.linesCreaseAngle = p.Float("linesCreaseAngle", m.linesCreaseAngle);
    m.lightToColor = p.Bool("lightToColor", m.lightToColor);
    m.litColor = p.Color("litColor", m.litColor);
    m.midColor = p.Color("midColor", m.midColor);
    m.shadowColor = p.Color("shadowColor", m.shadowColor);
    m.shadowBelow = p.Float("shadowBelow", m.shadowBelow);
    m.litFrom = p.Float("litFrom", m.litFrom);
    m.lightSoftness = p.Float("lightSoftness", m.lightSoftness);
    m.lightSmooth = p.Bool("lightSmooth", m.lightSmooth);
    m.halftone = p.Bool("halftone", m.halftone);
    m.halftoneLines = p.Bool("halftoneLines", m.halftoneLines);
    m.halftoneSize = p.Float("halftoneSize", m.halftoneSize);
    m.halftoneAngle = p.Float("halftoneAngle", m.halftoneAngle);
    m.halftoneColor = p.Color("halftoneColor", m.halftoneColor);
}

// UsdPreviewSurface or a Cycles graph: base colour (value or image) and glow only
void ReadPlain(HdMaterialNetwork const &net, RostrumMaterialData &m)
{
    for (HdMaterialNode const &n : net.nodes) {
        std::string id = n.identifier.GetString();
        char const *colour = EndsWith(id, "principled_bsdf") ? "base_color"
                           : EndsWith(id, "diffuse_bsdf")    ? "color"
                           : id == "UsdPreviewSurface"       ? "diffuseColor"
                           : EndsWith(id, "emission")        ? "color"
                                                             : nullptr;
        if (!colour) continue;
        Params p{n.parameters};
        if (EndsWith(id, "emission")) {  // Cycles' emission-only card: shown as painted
            m.baseColor = GfVec3f(0);
            m.emission = p.Color("color", GfVec3f(1)) * p.Float("strength", 1.0f);
            m.texture = TextureInto(net, n.path, TfToken(colour));
            if (!m.texture.empty()) { m.baseColor = GfVec3f(1); m.emission = GfVec3f(0); m.unlit = true; }
            break;
        }
        m.baseColor = p.Color(colour, m.baseColor);
        m.texture = TextureInto(net, n.path, TfToken(colour));
        if (id == "UsdPreviewSurface") m.emission = p.Color("emissiveColor", GfVec3f(0));
        else if (EndsWith(id, "principled_bsdf"))
            m.emission = p.Color("emission_color", GfVec3f(0)) * p.Float("emission_strength", 0.0f);
        break;
    }
}

}  // namespace

HdRostrumMaterial::~HdRostrumMaterial()
{
    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->materials.erase(GetId());
    ++_scene->materialsVersion;
}

void HdRostrumMaterial::Sync(HdSceneDelegate *sd, HdRenderParam *, HdDirtyBits *bits)
{
    RostrumMaterialData m;
    VtValue res = sd->GetMaterialResource(GetId());
    if (res.IsHolding<HdMaterialNetworkMap>()) {
        for (auto const &[terminal, net] : res.UncheckedGet<HdMaterialNetworkMap>().map) {
            if (terminal != HdMaterialTerminalTokens->surface) continue;
            HdMaterialNode const *stylized = nullptr;
            for (HdMaterialNode const &n : net.nodes)
                if (n.identifier == "rostrum_stylized") stylized = &n;
            if (stylized) ReadStylized(net, *stylized, m);
            else ReadPlain(net, m);
        }
    }
    // a glowing card: glow over a black base and nothing stylized asked for
    float glow = std::max({m.emission[0], m.emission[1], m.emission[2]});
    float base = std::max({m.baseColor[0], m.baseColor[1], m.baseColor[2]});
    if (glow > 0.0f && base <= 1e-4f && m.texture.empty() && !m.lines && !m.halftone && !m.lightToColor)
        m.unlit = true;
    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->materials[GetId()] = m;
    ++_scene->materialsVersion;
    *bits = Clean;
}

PXR_NAMESPACE_CLOSE_SCOPE
