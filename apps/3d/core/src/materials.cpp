// Cycles node and socket names are checked against Cycles' scene/shader_nodes.cpp (principled_bsdf,
// image_texture, bump, tangent, texture_coordinate, vector_math, vector_transform); HdCycles matches USD input
// names to socket names, ignoring case. Node builders: material_nodes.h.
#include "materials.h"
#include "material_blocks.h"

#include <algorithm>
#include <filesystem>

#include <pxr/base/gf/vec4f.h>
#include <pxr/usd/sdf/changeBlock.h>
#include <pxr/usd/sdf/copyUtils.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdShade/material.h>

#include "json_read.h"
#include "light_to_color.h"
#include "material_nodes.h"
#include "material_stylized.h"
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

// Light under the surface: Cycles' random walk. The base colour stays what the surface shows; `subsurfaceColor` sets
// how far each colour travels inside (per channel, relative to the farthest one), `subsurfaceRadius` how far that
// farthest one goes, in millimetres. A channel never goes below a hundredth of the farthest (a black channel of the
// colour would otherwise stop the walk for that colour at the surface).
GfVec3f subsurface_spread(const GfVec3f& colour) {
  const float top = std::max({colour[0], colour[1], colour[2]});
  if (top <= 0.0f) return GfVec3f(1.0f);
  GfVec3f r;
  for (int i = 0; i < 3; ++i) r[i] = std::max(colour[i] / top, 0.01f);
  return r;
}

// The quick view's hint (UsdPreviewSurface has no subsurface): the diffuse colour leans a quarter of the way
// (× subsurface) toward the inside colour at the base colour's brightness, so the hue matches Final at a glance
// without getting lighter or darker. Soft shadows and glowing thin parts are Final only.
GfVec3f subsurface_hint(const GfVec3f& base, const GfVec3f& colour, float amount) {
  const auto luma = [](const GfVec3f& c) { return 0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2]; };
  const float lc = luma(colour);
  if (amount <= 0.0f || lc <= 0.0f) return base;
  const GfVec3f tint = colour * (luma(base) / lc);
  const float t = 0.25f * std::clamp(amount, 0.0f, 1.0f);
  return base * (1.0f - t) + tint * t;
}

void build_one(const UsdStageRefPtr& stage, const std::string& id, Reader& p, const JsObject* anim, int start,
               int end) {
  const SdfValueTypeName kFloat = SdfValueTypeNames->Float, kColor = SdfValueTypeNames->Color3f;
  const SdfPath path = material_path(id);
  UsdShadeMaterial mat = UsdShadeMaterial::Define(stage, path);
  const GfVec3f base = p.vec3("baseColor");
  const Picture base_tex = still_picture(p, "baseColorTexture"), rough_tex = still_picture(p, "roughnessTexture");
  const Picture bump_tex = still_picture(p, "bumpTexture"), metal_tex = still_picture(p, "metallicTexture");
  const Picture glow_tex = emission_picture(p, anim, id, start, end);
  const float metallic = float(p.num("metallic")), roughness = float(p.num("roughness"));
  const float transmission = float(p.num("transmission")), ior = float(p.num("ior"));
  const float coat = float(p.num("coat")), coat_roughness = float(p.num("coatRoughness"));
  const GfVec3f emission = p.vec3("emissionColor");
  const float emission_strength = float(p.num("emissionStrength"));
  const float anisotropy = float(p.num("anisotropy"));
  const std::string brush = p.one_of("brushDirection", kBrush);
  const float subsurface = float(p.num("subsurface"));
  const GfVec3f subsurface_colour = p.vec3("subsurfaceColor");
  const float subsurface_mm = float(p.num_min("subsurfaceRadius", 0.0, true));
  const StylizedLook look = read_stylized(p);  // Lines, Light to colour, Halftone (material_stylized.h)

  // Cycles
  UsdShadeShader c = shader(stage, path, "Cycles", "cycles_principled_bsdf");
  // A copy's colour change (copies' Change near colour): Object Info gives the copy's tint and its share (our Cycles
  // patch sets them from the copies' rostrumTint; 0 on everything else), laid over the base colour.
  UsdShadeShader tint = shader(stage, path, "CopyTint", "cycles_mix_color");
  UsdShadeShader copy = shader(stage, path, "CopyInfo", "cycles_object_info");
  set(tint, "a", kColor, base);
  link(tint, "fac", kFloat, copy, "alpha", kFloat);
  link(tint, "b", kColor, copy, "color", kColor);
  link(c, "base_color", kColor, tint, "result", kColor);
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
  set(c, "subsurface_weight", kFloat, subsurface);
  set(c, "subsurface_method", SdfValueTypeNames->String, std::string("random_walk"));
  set(c, "subsurface_radius", SdfValueTypeNames->Vector3f, subsurface_spread(subsurface_colour));
  set(c, "subsurface_scale", kFloat, subsurface_mm * 0.001f);  // the scene is in metres
  if (!base_tex.empty()) {
    UsdShadeShader t = cycles_image(stage, path, "BaseColorTexture", base_tex, true);
    link(tint, "a", kColor, t, "color", kColor);
  }
  if (!rough_tex.empty()) {
    UsdShadeShader t = cycles_image(stage, path, "RoughnessTexture", rough_tex, false);
    link(c, "roughness", kFloat, t, "color", kColor);
  }
  if (!metal_tex.empty()) {
    UsdShadeShader t = cycles_image(stage, path, "MetallicTexture", metal_tex, false);
    link(c, "metallic", kFloat, t, "color", kColor);
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

  // UsdPreviewSurface: the same values where it has them (no anisotropy, sheen, coat tint / IOR, thin film, bump or
  // subsurface: that is only hinted, subsurface_hint).
  // Glass in Storm: what transmits has no diffuse colour and lets most light through (low opacity), while its
  // reflections stay whole (UsdPreviewSurface's "transparent" opacity mode keeps the specular), so a clear
  // cover reads as a clear cover with the studio reflected in it, not as a grey slab. Storm can't blur what is
  // behind, so rough (frosted) glass is shown less see-through and milkier the rougher it is.
  const float see_through = transmission * (1.0f - 0.6f * std::clamp(roughness, 0.0f, 1.0f));
  UsdShadeShader v = shader(stage, path, "Preview", "UsdPreviewSurface");
  set(v, "diffuseColor", kColor, subsurface_hint(base, subsurface_colour, subsurface) * (1.0f - see_through));
  set(v, "metallic", kFloat, metallic);
  set(v, "roughness", kFloat, roughness);
  set(v, "ior", kFloat, ior);
  set(v, "clearcoat", kFloat, coat);
  set(v, "clearcoatRoughness", kFloat, coat_roughness);
  set(v, "emissiveColor", kColor, emission * emission_strength);
  set(v, "opacity", kFloat, 1.0f - 0.92f * see_through);
  // a clay's mask shown in the viewport (clay_usd.cpp): masked clay gets less light; anything else has no such
  // primvar and gets the fallback 1 (as before). Cycles has no such link, so Final renders don't show it.
  UsdShadeShader mask_shade = shader(stage, path, "PreviewMaskShade", "UsdPrimvarReader_float");
  set(mask_shade, "varname", SdfValueTypeNames->String, std::string("rostrumMaskShade"));
  set(mask_shade, "fallback", kFloat, 1.0f);
  link(v, "occlusion", kFloat, mask_shade, "result", kFloat);
  UsdShadeShader preview_base;  // the base colour image, for the Stylized shader too
  if (!base_tex.empty() || !rough_tex.empty() || !metal_tex.empty() || !glow_tex.empty()) {
    UsdShadeShader st = shader(stage, path, "PreviewUV", "UsdPrimvarReader_float2");
    set(st, "varname", SdfValueTypeNames->String, std::string("st"));
    if (!base_tex.empty()) {
      preview_base = preview_image(stage, path, "PreviewBaseColor", base_tex, true, st);
      link(v, "diffuseColor", kColor, preview_base, "rgb", SdfValueTypeNames->Float3);
    }
    if (!rough_tex.empty()) {
      UsdShadeShader t = preview_image(stage, path, "PreviewRoughness", rough_tex, false, st);
      link(v, "roughness", kFloat, t, "r", kFloat);
    }
    if (!metal_tex.empty()) {
      UsdShadeShader t = preview_image(stage, path, "PreviewMetallic", metal_tex, false, st);
      link(v, "metallic", kFloat, t, "r", kFloat);
    }
    if (!glow_tex.empty()) {
      UsdShadeShader t = preview_image(stage, path, "PreviewEmission", glow_tex, true, st);
      const float s = emission_strength;
      set(t, "scale", SdfValueTypeNames->Float4, GfVec4f(s, s, s, 1.0f));
      link(v, "emissiveColor", kColor, t, "rgb", SdfValueTypeNames->Float3);
    }
  }
  mat.CreateSurfaceOutput().ConnectToSource(v.CreateOutput(TfToken("surface"), SdfValueTypeNames->Token));

  // The Stylized look's own shader, on every material (outputs:rostrum:surface). With Light to colour on, the Cycles
  // surface is rewired once the scene's lights exist (light_to_color.h).
  author_stylized(stage, path, look, base, preview_base, emission * emission_strength, 1.0f - 0.92f * see_through);
  // The material's blocks (a MaterialX document, material_blocks.h): wired into both surfaces above.
  if (p.has("blocks")) {
    const std::string doc = p.str("blocks");
    if (!doc.empty()) author_blocks(stage, path, id, doc, p.at("blocks"), c, v);
  }
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

void rebuild_material(const UsdStageRefPtr& stage, const std::string& id, const JsObject& props,
                      const JsObject* anim, int start, int end) {
  const SdfPath path = material_path(id);
  UsdStageRefPtr scratch = UsdStage::CreateInMemory();
  Reader p(props, id);
  build_one(scratch, id, p, anim, start, end);  // checked whole here: a problem leaves `stage` as it was
  bool l2c = false;
  if (const UsdShadeShader look{scratch->GetPrimAtPath(path.AppendChild(TfToken("Stylized")))})
    look.GetInput(TfToken("lightToColor")).Get(&l2c);
  if (l2c) apply_light_to_color(scratch, path, scene_light_terms(stage, start, end), start);
  const SdfLayerHandle dst = stage->GetRootLayer();
  const SdfPrimSpecHandle parent = dst->GetPrimAtPath(path.GetParentPath());
  if (!parent) throw Error("material: the held stage has no " + path.GetParentPath().GetString());
  const SdfChangeBlock block;  // one change for Hydra: the material's prims replaced
  if (const SdfPrimSpecHandle old = dst->GetPrimAtPath(path)) parent->RemoveNameChild(old);
  if (!SdfCopySpec(scratch->GetRootLayer(), path, dst, path))
    throw Error("material: could not write " + path.GetString() + " into the held stage");
}

void restyle_material(const UsdStageRefPtr& stage, const std::string& id, const JsObject& props) {
  Reader p(props, id);
  const StylizedLook look = read_stylized(p);
  UsdShadeShader s(stage->GetPrimAtPath(material_path(id).AppendChild(TfToken("Stylized"))));
  if (!s) throw Error("material: \"" + id + "\" has no Stylized shader on the held stage");
  const SdfChangeBlock block;
  set_stylized_inputs(s, look);
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
