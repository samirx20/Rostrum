// Cycles node and socket names are checked against Cycles' scene/shader_nodes.cpp (principled_bsdf,
// image_texture, bump, tangent, texture_coordinate, vector_math, vector_transform); HdCycles matches USD input
// names to socket names, ignoring case. Node builders: material_nodes.h.
#include "materials.h"

#include <algorithm>
#include <filesystem>

#include <pxr/base/gf/vec4f.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdShade/material.h>

#include "json_read.h"
#include "material_nodes.h"
#include "stage_items.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

const std::vector<std::string> kBrush = {"uv", "around x", "around y", "around z"};

Picture still_picture(Reader& p, const char* key) {
  const std::string file = p.str(key);
  check_file(file, p.at(key), "an image");
  return file.empty() ? Picture{} : Picture{{file}, 0};
}

// emissionTexture: a file, or (in the material's `anim`) one file per frame of the shot (a screen playing a render).
Picture emission_picture(Reader& p, const JsObject* anim, const std::string& id, int start, int end) {
  Picture pic = still_picture(p, "emissionTexture");
  if (!anim) return pic;
  for (const auto& [key, value] : *anim)
    if (key != "emissionTexture") fail(id + ".anim." + key, "cannot change per frame", "emissionTexture");
  const auto it = anim->find("emissionTexture");
  if (it == anim->end()) return pic;
  const size_t n = size_t(end - start + 1);
  const std::string where = id + ".anim.emissionTexture", expected = std::to_string(n) + " image paths, one per frame";
  if (!it->second.IsArray() || it->second.GetJsArray().size() != n) fail(where, "has the wrong shape", expected);
  pic = Picture{{}, start};
  for (size_t i = 0; i < n; ++i) {
    const JsValue& v = it->second.GetJsArray()[i];
    const std::string at = where + "[" + std::to_string(i) + "]";
    if (!v.IsString() || v.GetString().empty()) fail(at, "is not a path", "the absolute path of an image");
    check_file(v.GetString(), at, "an image");
    pic.files.push_back(v.GetString());
  }
  return pic;
}

void build_one(const UsdStageRefPtr& stage, const std::string& id, Reader& p, const JsObject* anim, int start,
               int end) {
  const SdfValueTypeName kFloat = SdfValueTypeNames->Float, kColor = SdfValueTypeNames->Color3f;
  const SdfPath path = material_path(id);
  UsdShadeMaterial mat = UsdShadeMaterial::Define(stage, path);
  const GfVec3f base = p.vec3("baseColor");
  const Picture base_tex = still_picture(p, "baseColorTexture"), rough_tex = still_picture(p, "roughnessTexture");
  const Picture bump_tex = still_picture(p, "bumpTexture");
  const Picture glow_tex = emission_picture(p, anim, id, start, end);
  const float metallic = float(p.num("metallic")), roughness = float(p.num("roughness"));
  const float transmission = float(p.num("transmission")), ior = float(p.num("ior"));
  const float coat = float(p.num("coat")), coat_roughness = float(p.num("coatRoughness"));
  const GfVec3f emission = p.vec3("emissionColor");
  const float emission_strength = float(p.num("emissionStrength"));
  const float anisotropy = float(p.num("anisotropy"));
  const std::string brush = p.one_of("brushDirection", kBrush);

  // Cycles
  UsdShadeShader c = shader(stage, path, "Cycles", "cycles_principled_bsdf");
  set(c, "base_color", kColor, base);
  set(c, "metallic", kFloat, metallic);
  set(c, "roughness", kFloat, roughness);  // also blurs what is seen through glass (frosted glass): one roughness
  set(c, "transmission_weight", kFloat, transmission);
  set(c, "ior", kFloat, ior);
  set(c, "coat_weight", kFloat, coat);
  set(c, "coat_roughness", kFloat, coat_roughness);
  set(c, "coat_tint", kColor, p.vec3("coatTint"));
  set(c, "coat_ior", kFloat, float(p.num("coatIor")));
  set(c, "sheen_weight", kFloat, float(p.num("sheen")));
  set(c, "sheen_roughness", kFloat, float(p.num("sheenRoughness")));
  set(c, "sheen_tint", kColor, p.vec3("sheenTint"));
  set(c, "anisotropic", kFloat, anisotropy);
  set(c, "anisotropic_rotation", kFloat, float(p.num("anisotropyRotation")));
  if (anisotropy > 0.0f) brush_tangent(stage, path, c, brush);
  set(c, "emission_color", kColor, emission);
  set(c, "emission_strength", kFloat, emission_strength);
  set(c, "thin_film_thickness", kFloat, float(p.num("thinFilm")));
  if (!base_tex.empty()) {
    UsdShadeShader t = cycles_image(stage, path, "BaseColorTexture", base_tex, true);
    link(c, "base_color", kColor, t, "color", kColor);
  }
  if (!rough_tex.empty()) {
    UsdShadeShader t = cycles_image(stage, path, "RoughnessTexture", rough_tex, false);
    link(c, "roughness", kFloat, t, "color", kColor);
  }
  if (!glow_tex.empty()) {  // the picture is the glow colour; emission_strength still scales it
    UsdShadeShader t = cycles_image(stage, path, "EmissionTexture", glow_tex, true);
    link(c, "emission_color", kColor, t, "color", kColor);
  }
  const float bump_strength = float(p.num("bumpStrength"));
  if (!bump_tex.empty()) {
    UsdShadeShader t = cycles_image(stage, path, "BumpTexture", bump_tex, false);
    UsdShadeShader bump = shader(stage, path, "Bump", "cycles_bump");
    set(bump, "strength", kFloat, bump_strength);
    set(bump, "distance", kFloat, 0.01f);  // a white texel stands 1 cm proud (scene is in metres)
    link(bump, "height", kFloat, t, "color", kColor);
    link(c, "normal", SdfValueTypeNames->Normal3f, bump, "normal", SdfValueTypeNames->Normal3f);
  }
  mat.CreateSurfaceOutput(TfToken("cycles"))
      .ConnectToSource(c.CreateOutput(TfToken("BSDF"), SdfValueTypeNames->Token));

  // UsdPreviewSurface: the same values where it has them (no anisotropy, sheen, coat tint / IOR, thin film or bump).
  // Glass in Storm: what transmits has no diffuse colour and lets most light through (low opacity), while its
  // reflections stay whole (UsdPreviewSurface's "transparent" opacity mode keeps the specular), so a clear
  // cover reads as a clear cover with the studio reflected in it, not as a grey slab. Storm can't blur what is
  // behind, so rough (frosted) glass is shown less see-through and milkier the rougher it is.
  const float see_through = transmission * (1.0f - 0.6f * std::clamp(roughness, 0.0f, 1.0f));
  UsdShadeShader v = shader(stage, path, "Preview", "UsdPreviewSurface");
  set(v, "diffuseColor", kColor, base * (1.0f - see_through));
  set(v, "metallic", kFloat, metallic);
  set(v, "roughness", kFloat, roughness);
  set(v, "ior", kFloat, ior);
  set(v, "clearcoat", kFloat, coat);
  set(v, "clearcoatRoughness", kFloat, coat_roughness);
  set(v, "emissiveColor", kColor, emission * emission_strength);
  set(v, "opacity", kFloat, 1.0f - 0.92f * see_through);
  if (!base_tex.empty() || !rough_tex.empty() || !glow_tex.empty()) {
    UsdShadeShader st = shader(stage, path, "PreviewUV", "UsdPrimvarReader_float2");
    set(st, "varname", SdfValueTypeNames->String, std::string("st"));
    if (!base_tex.empty()) {
      UsdShadeShader t = preview_image(stage, path, "PreviewBaseColor", base_tex, true, st);
      link(v, "diffuseColor", kColor, t, "rgb", SdfValueTypeNames->Float3);
    }
    if (!rough_tex.empty()) {
      UsdShadeShader t = preview_image(stage, path, "PreviewRoughness", rough_tex, false, st);
      link(v, "roughness", kFloat, t, "r", kFloat);
    }
    if (!glow_tex.empty()) {
      UsdShadeShader t = preview_image(stage, path, "PreviewEmission", glow_tex, true, st);
      const float s = emission_strength;
      set(t, "scale", SdfValueTypeNames->Float4, GfVec4f(s, s, s, 1.0f));
      link(v, "emissiveColor", kColor, t, "rgb", SdfValueTypeNames->Float3);
    }
  }
  mat.CreateSurfaceOutput().ConnectToSource(v.CreateOutput(TfToken("surface"), SdfValueTypeNames->Token));
  p.finish();
}

}  // namespace

SdfPath material_path(const std::string& id) {
  return SdfPath("/World/Looks").AppendChild(TfToken(id));
}

void check_file(const std::string& path, const std::string& where, const char* what) {
  if (path.empty()) return;
  const std::string accepted = std::string("\"\" or the absolute path of ") + what;
  if (!std::filesystem::path(path).is_absolute()) fail(where, "\"" + path + "\" is not absolute", accepted);
  if (!std::filesystem::is_regular_file(path)) fail(where, "\"" + path + "\" does not exist", accepted);
}

std::set<std::string> build_materials(const UsdStageRefPtr& stage, const JsArray& materials, int start,
                                      int end) {
  std::set<std::string> ids;
  for (size_t i = 0; i < materials.size(); ++i) {
    const std::string where = "materials[" + std::to_string(i) + "]";
    if (!materials[i].IsObject()) fail(where, "is " + materials[i].GetTypeName(), "an object");
    Reader m(materials[i].GetJsObject(), where);
    const std::string id = m.str("id");
    check_id(id, m.at("id"));
    if (!ids.insert(id).second) fail(m.at("id"), "\"" + id + "\" is used twice", "unique material ids");
    Reader props(m.object("props"), id);
    build_one(stage, id, props, m.has("anim") ? &m.object("anim") : nullptr, start, end);
    m.finish();
  }
  return ids;
}

}  // namespace r3d
