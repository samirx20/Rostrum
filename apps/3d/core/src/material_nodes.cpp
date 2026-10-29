#include "material_nodes.h"

#include <pxr/base/gf/vec3f.h>
#include <pxr/base/vt/array.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/sdf/types.h>

#include "error.h"
#include "udim.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

// One file as the attribute's value; several = one time sample per frame (asset paths are held, never blended).
void set_files(UsdShadeShader& s, const char* input, const Picture& pic) {
  UsdAttribute a = s.CreateInput(TfToken(input), SdfValueTypeNames->Asset).GetAttr();
  a.Set(SdfAssetPath(pic.files.front()));
  if (pic.files.size() > 1)
    for (size_t i = 0; i < pic.files.size(); ++i)
      a.Set(SdfAssetPath(pic.files[i]), UsdTimeCode(double(pic.start) + double(i)));
}

}  // namespace

UsdShadeShader shader(const UsdStageRefPtr& stage, const SdfPath& mat, const char* name, const char* id) {
  UsdShadeShader s = UsdShadeShader::Define(stage, mat.AppendChild(TfToken(name)));
  s.SetShaderId(TfToken(id));
  return s;
}

void link(UsdShadeShader& dst, const char* input, const SdfValueTypeName& type, UsdShadeShader& src,
          const char* output, const SdfValueTypeName& out_type) {
  dst.CreateInput(TfToken(input), type).ConnectToSource(src.CreateOutput(TfToken(output), out_type));
}

UsdShadeShader cycles_image(const UsdStageRefPtr& stage, const SdfPath& mat, const char* name, const Picture& pic,
                            bool colour) {
  UsdShadeShader t = shader(stage, mat, name, "cycles_image_texture");
  set_files(t, "filename", pic);
  set(t, "colorspace", SdfValueTypeNames->String, std::string("data"));
  // A UDIM set (v1.34): Cycles' image_texture loads only the tiles in its `tiles` list (1001 alone by default), each
  // file the name with <UDIM> replaced by the tile number. The tiles there when the material is built are listed.
  if (udim::is_set(pic.files.front())) {
    const std::vector<int> found = udim::tile_numbers(pic.files.front());
    set(t, "tiles", SdfValueTypeNames->IntArray, VtIntArray(found.begin(), found.end()));
  }
  const std::string& f = pic.files.front();
  const std::string ext = f.size() > 4 ? f.substr(f.size() - 4) : f;
  if (!colour || ext == ".exr" || ext == ".hdr" || ext == ".EXR" || ext == ".HDR") return t;  // float: linear already
  // 3d-cl4: this Cycles reads an 8-bit colour picture as it is, never sRGB-decoded, whether asked "__builtin_srgb" or
  // left to auto (a painted beige came out pale and grey in Final, beside the right beige in Quick). So it is read
  // as data and decoded here: gamma 2.2, within a few levels of sRGB's curve. The caller links this node's "color".
  UsdShadeShader g = shader(stage, mat, (std::string(name) + "Decode").c_str(), "cycles_gamma");
  set(g, "gamma", SdfValueTypeNames->Float, 2.2f);
  link(g, "color", SdfValueTypeNames->Color3f, t, "color", SdfValueTypeNames->Color3f);
  return g;
}

UsdShadeShader preview_image(const UsdStageRefPtr& stage, const SdfPath& mat, const char* name, const Picture& pic,
                             bool colour, UsdShadeShader& st) {
  UsdShadeShader t = shader(stage, mat, name, "UsdUVTexture");
  set_files(t, "file", pic);
  set(t, "sourceColorSpace", SdfValueTypeNames->Token, TfToken(colour ? "sRGB" : "raw"));
  link(t, "st", SdfValueTypeNames->Float2, st, "result", SdfValueTypeNames->Float2);
  return t;
}

void brush_tangent(const UsdStageRefPtr& stage, const SdfPath& mat, UsdShadeShader& bsdf,
                   const std::string& direction) {
  const SdfValueTypeName kVec = SdfValueTypeNames->Vector3f, kStr = SdfValueTypeNames->String;
  if (direction == "uv") {
    UsdShadeShader t = shader(stage, mat, "BrushTangent", "cycles_tangent");
    set(t, "direction_type", kStr, std::string("uv_map"));
    set(t, "attribute", kStr, std::string());  // "" = the mesh's default UVs (primvars:st)
    link(bsdf, "tangent", SdfValueTypeNames->Normal3f, t, "tangent", SdfValueTypeNames->Normal3f);
    return;
  }
  GfVec3f axis(0.0f);
  if (direction == "around x") axis[0] = 1.0f;
  else if (direction == "around y") axis[1] = 1.0f;
  else if (direction == "around z") axis[2] = 1.0f;
  else throw Error("brushDirection: \"" + direction + "\" is unknown. Accepted: uv, around x, around y, around z");
  UsdShadeShader pos = shader(stage, mat, "BrushPosition", "cycles_texture_coordinate");
  UsdShadeShader cross = shader(stage, mat, "BrushCircle", "cycles_vector_math");
  set(cross, "math_type", kStr, std::string("cross_product"));
  set(cross, "vector1", kVec, axis);
  link(cross, "vector2", kVec, pos, "object", SdfValueTypeNames->Point3f);
  UsdShadeShader world = shader(stage, mat, "BrushToWorld", "cycles_vector_transform");
  set(world, "transform_type", kStr, std::string("vector"));
  set(world, "convert_from", kStr, std::string("object"));
  set(world, "convert_to", kStr, std::string("world"));
  link(world, "vector", kVec, cross, "vector", kVec);
  link(bsdf, "tangent", SdfValueTypeNames->Normal3f, world, "vector", kVec);
}

}  // namespace r3d
