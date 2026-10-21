// Cycles node and socket names are checked against Cycles' scene/shader_nodes.cpp (principled_bsdf,
// image_texture, bump); HdCycles matches USD input names to socket names, ignoring case.
#include "materials.h"

#include <filesystem>

#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/shader.h>

#include "json_read.h"
#include "stage_items.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

UsdShadeShader shader(const UsdStageRefPtr& stage, const SdfPath& mat, const char* name, const char* id) {
  UsdShadeShader s = UsdShadeShader::Define(stage, mat.AppendChild(TfToken(name)));
  s.SetShaderId(TfToken(id));
  return s;
}

template <class T>
void set(UsdShadeShader& s, const char* input, const SdfValueTypeName& type, const T& value) {
  s.CreateInput(TfToken(input), type).Set(value);
}

void link(UsdShadeShader& dst, const char* input, const SdfValueTypeName& type, UsdShadeShader& src,
          const char* output, const SdfValueTypeName& out_type) {
  dst.CreateInput(TfToken(input), type).ConnectToSource(src.CreateOutput(TfToken(output), out_type));
}

// cycles_image_texture on the mesh's default UVs (primvars:st); colour = sRGB, anything else = data.
UsdShadeShader cycles_image(const UsdStageRefPtr& stage, const SdfPath& mat, const char* name,
                            const std::string& file, bool colour) {
  UsdShadeShader t = shader(stage, mat, name, "cycles_image_texture");
  set(t, "filename", SdfValueTypeNames->Asset, SdfAssetPath(file));
  set(t, "colorspace", SdfValueTypeNames->String, std::string(colour ? "__builtin_srgb" : "data"));
  return t;
}

UsdShadeShader preview_image(const UsdStageRefPtr& stage, const SdfPath& mat, const char* name,
                             const std::string& file, bool colour, UsdShadeShader& st) {
  UsdShadeShader t = shader(stage, mat, name, "UsdUVTexture");
  set(t, "file", SdfValueTypeNames->Asset, SdfAssetPath(file));
  set(t, "sourceColorSpace", SdfValueTypeNames->Token, TfToken(colour ? "sRGB" : "raw"));
  link(t, "st", SdfValueTypeNames->Float2, st, "result", SdfValueTypeNames->Float2);
  return t;
}

void build_one(const UsdStageRefPtr& stage, const std::string& id, Reader& p) {
  const SdfValueTypeName kFloat = SdfValueTypeNames->Float, kColor = SdfValueTypeNames->Color3f;
  const SdfPath path = material_path(id);
  UsdShadeMaterial mat = UsdShadeMaterial::Define(stage, path);
  const GfVec3f base = p.vec3("baseColor");
  const std::string base_tex = p.str("baseColorTexture"), rough_tex = p.str("roughnessTexture");
  const std::string bump_tex = p.str("bumpTexture");
  check_file(base_tex, p.at("baseColorTexture"), "an image");
  check_file(rough_tex, p.at("roughnessTexture"), "an image");
  check_file(bump_tex, p.at("bumpTexture"), "an image");
  const float metallic = float(p.num("metallic")), roughness = float(p.num("roughness"));
  const float transmission = float(p.num("transmission")), ior = float(p.num("ior"));
  const float coat = float(p.num("coat")), coat_roughness = float(p.num("coatRoughness"));
  const GfVec3f emission = p.vec3("emissionColor");
  const float emission_strength = float(p.num("emissionStrength"));

  // Cycles
  UsdShadeShader c = shader(stage, path, "Cycles", "cycles_principled_bsdf");
  set(c, "base_color", kColor, base);
  set(c, "metallic", kFloat, metallic);
  set(c, "roughness", kFloat, roughness);
  set(c, "transmission_weight", kFloat, transmission);
  set(c, "ior", kFloat, ior);
  set(c, "coat_weight", kFloat, coat);
  set(c, "coat_roughness", kFloat, coat_roughness);
  set(c, "anisotropic", kFloat, float(p.num("anisotropy")));
  set(c, "anisotropic_rotation", kFloat, float(p.num("anisotropyRotation")));
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

  // UsdPreviewSurface: the same values where it has them (no anisotropy, thin film or bump).
  // Glass in Storm: what transmits has no diffuse colour and lets most light through (low opacity), while its
  // reflections stay whole (UsdPreviewSurface's "transparent" opacity mode keeps the specular), so a clear
  // cover reads as a clear cover with the studio reflected in it, not as a grey slab.
  UsdShadeShader v = shader(stage, path, "Preview", "UsdPreviewSurface");
  set(v, "diffuseColor", kColor, base * (1.0f - transmission));
  set(v, "metallic", kFloat, metallic);
  set(v, "roughness", kFloat, roughness);
  set(v, "ior", kFloat, ior);
  set(v, "clearcoat", kFloat, coat);
  set(v, "clearcoatRoughness", kFloat, coat_roughness);
  set(v, "emissiveColor", kColor, emission * emission_strength);
  set(v, "opacity", kFloat, 1.0f - 0.92f * transmission);
  if (!base_tex.empty() || !rough_tex.empty()) {
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

std::set<std::string> build_materials(const UsdStageRefPtr& stage, const JsArray& materials) {
  std::set<std::string> ids;
  for (size_t i = 0; i < materials.size(); ++i) {
    const std::string where = "materials[" + std::to_string(i) + "]";
    if (!materials[i].IsObject()) fail(where, "is " + materials[i].GetTypeName(), "an object");
    Reader m(materials[i].GetJsObject(), where);
    const std::string id = m.str("id");
    check_id(id, m.at("id"));
    if (!ids.insert(id).second) fail(m.at("id"), "\"" + id + "\" is used twice", "unique material ids");
    Reader props(m.object("props"), id);
    build_one(stage, id, props);
    m.finish();
  }
  return ids;
}

}  // namespace r3d
