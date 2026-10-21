// P-3D-3: material -> albedo (value or image) and "unlit" for emission-only cards. Reads Cycles'
// node graphs (cycles_principled_bsdf / cycles_emission / cycles_image_texture) and
// UsdPreviewSurface / UsdUVTexture.
#include "prims.h"

#include <pxr/imaging/hd/sceneDelegate.h>
#include <pxr/usd/sdf/assetPath.h>

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
            for (HdMaterialNode const &n : net.nodes) {
                std::string id = n.identifier.GetString();
                char const *colour = EndsWith(id, "principled_bsdf") ? "base_color"
                                   : EndsWith(id, "diffuse_bsdf")    ? "color"
                                   : id == "UsdPreviewSurface"       ? "diffuseColor"
                                   : EndsWith(id, "emission")        ? "color"
                                                                     : nullptr;
                if (!colour) continue;
                m.unlit = EndsWith(id, "emission");
                auto it = n.parameters.find(TfToken(colour));
                if (it != n.parameters.end() && it->second.IsHolding<GfVec3f>())
                    m.baseColor = it->second.UncheckedGet<GfVec3f>();
                m.texture = TextureInto(net, n.path, TfToken(colour));
                break;
            }
        }
    }
    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->materials[GetId()] = m;
    ++_scene->materialsVersion;
    *bits = Clean;
}

PXR_NAMESPACE_CLOSE_SCOPE
