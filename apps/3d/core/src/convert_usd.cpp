// The converted layer's writer helpers (convert_usd.h).
#include "convert_usd.h"

#include <pxr/base/gf/vec2f.h>
#include <pxr/base/gf/vec4f.h>
#include <pxr/base/tf/stringUtils.h>
#include <pxr/base/vt/dictionary.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usdGeom/metrics.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>
#include <pxr/usd/usdGeom/scope.h>
#include <pxr/usd/usdGeom/subset.h>
#include <pxr/usd/usdGeom/tokens.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>
#include <pxr/usd/usdShade/shader.h>
#include <pxr/usd/usdShade/tokens.h>

#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <functional>

#include "error.h"
#include "udim.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace fs = std::filesystem;

namespace r3d::cv {

std::string stem_of(const std::string& file) { return fs::u8path(file).stem().u8string(); }

std::string folder_of(const std::string& file) {
  const size_t slash = file.find_last_of("/\\");
  return slash == std::string::npos ? std::string() : file.substr(0, slash + 1);
}

std::string asset_path(const std::string& path) {
  std::error_code ec;
  fs::path p = fs::absolute(fs::u8path(path), ec);
  return (ec ? fs::u8path(path) : p).lexically_normal().generic_u8string();
}

UsdGeomXform start_layer(const UsdStageRefPtr& stage, const std::string& file, const std::string& format,
                         double meters_per_unit, bool units_known) {
  UsdGeomSetStageUpAxis(stage, UsdGeomTokens->y);
  UsdGeomSetStageMetersPerUnit(stage, meters_per_unit);
  VtDictionary data;
  data["rostrum:format"] = VtValue(format);
  data["rostrum:unitsKnown"] = VtValue(units_known);
  stage->GetRootLayer()->SetCustomLayerData(data);
  std::string name = TfMakeValidIdentifier(stem_of(file));
  if (name.empty() || name == "_") name = "model";
  UsdGeomXform root = UsdGeomXform::Define(stage, SdfPath::AbsoluteRootPath().AppendChild(TfToken(name)));
  stage->SetDefaultPrim(root.GetPrim());
  return root;
}

void set_time_range(const UsdStageRefPtr& stage, double start, double end, double codes_per_second) {
  stage->SetStartTimeCode(start);
  stage->SetEndTimeCode(end);
  stage->SetTimeCodesPerSecond(codes_per_second);
  stage->SetFramesPerSecond(codes_per_second);
}

SdfPath Names::child(const SdfPath& parent, const std::string& raw, const std::string& fallback) {
  std::string base = TfMakeValidIdentifier(raw.empty() ? fallback : raw);
  if (base.empty() || base == "_") base = TfMakeValidIdentifier(fallback);
  std::set<std::string>& taken = taken_[parent];
  std::string name = base;
  for (int n = 1; taken.count(name); ++n) name = base + "_" + std::to_string(n);
  taken.insert(name);
  return parent.AppendChild(TfToken(name));
}

void set_transform(const UsdGeomXformable& x, const GfMatrix4d& m, UsdTimeCode time) {
  if (time.IsDefault() && m == GfMatrix4d(1.0)) return;
  bool reset = false;
  std::vector<UsdGeomXformOp> ops = x.GetOrderedXformOps(&reset);
  UsdGeomXformOp op = ops.empty() ? x.AddTransformOp() : ops.front();
  op.Set(m, time);
}

UsdGeomMesh write_mesh(const UsdStageRefPtr& stage, const SdfPath& path, const MeshArrays& m) {
  UsdGeomMesh mesh = UsdGeomMesh::Define(stage, path);
  write_mesh_sample(mesh, m, UsdTimeCode::Default(), true, true, UsdTimeCode::Default());
  return mesh;
}

void write_mesh_sample(UsdGeomMesh mesh, const MeshArrays& m, UsdTimeCode time, bool with_topology,
                       bool with_extras, UsdTimeCode extras) {
  mesh.CreateSubdivisionSchemeAttr().Set(m.subdivided ? UsdGeomTokens->catmullClark : UsdGeomTokens->none);
  if (with_topology) {
    mesh.CreateFaceVertexCountsAttr().Set(m.counts, time);
    mesh.CreateFaceVertexIndicesAttr().Set(m.indices, time);
  }
  mesh.CreatePointsAttr().Set(m.points, time);
  VtVec3fArray extent(2);
  if (UsdGeomPointBased::ComputeExtent(m.points, &extent)) mesh.CreateExtentAttr().Set(extent, time);
  if (!with_extras) return;
  if (!m.normals.empty()) {
    VtVec3fArray n = m.normals;
    if (!m.normal_indices.empty()) {  // USD's normals attribute has no indices: expand
      n.resize(m.normal_indices.size());
      for (size_t i = 0; i < m.normal_indices.size(); ++i) n[i] = m.normals[size_t(m.normal_indices[i])];
    }
    mesh.CreateNormalsAttr().Set(n, extras);
    mesh.SetNormalsInterpolation(m.normal_interp);
  }
  if (!m.uvs.empty()) {
    UsdGeomPrimvar st = UsdGeomPrimvarsAPI(mesh.GetPrim())
                            .CreatePrimvar(TfToken("st"), SdfValueTypeNames->TexCoord2fArray, m.uv_interp);
    st.Set(m.uvs, extras);
    if (!m.uv_indices.empty()) st.SetIndices(m.uv_indices, extras);
  }
}

UsdShadeMaterial write_material(const UsdStageRefPtr& stage, const MaterialDesc& d, Names& names) {
  const SdfPath scope = stage->GetDefaultPrim().GetPath().AppendChild(TfToken("Materials"));
  if (!stage->GetPrimAtPath(scope)) UsdGeomScope::Define(stage, scope);
  const SdfPath path = names.child(scope, d.name, "Material");
  UsdShadeMaterial mat = UsdShadeMaterial::Define(stage, path);

  UsdShadeShader surf = UsdShadeShader::Define(stage, path.AppendChild(TfToken("PreviewSurface")));
  surf.CreateIdAttr(VtValue(TfToken("UsdPreviewSurface")));
  mat.CreateSurfaceOutput().ConnectToSource(surf.CreateOutput(TfToken("surface"), SdfValueTypeNames->Token));
  surf.CreateInput(TfToken("useSpecularWorkflow"), SdfValueTypeNames->Int).Set(0);
  surf.CreateInput(TfToken("metallic"), SdfValueTypeNames->Float).Set(d.metallic);
  surf.CreateInput(TfToken("roughness"), SdfValueTypeNames->Float).Set(d.roughness);
  surf.CreateInput(TfToken("emissiveColor"), SdfValueTypeNames->Color3f).Set(d.emissive);
  UsdShadeInput color = surf.CreateInput(TfToken("diffuseColor"), SdfValueTypeNames->Color3f);
  UsdShadeInput opacity = surf.CreateInput(TfToken("opacity"), SdfValueTypeNames->Float);
  color.Set(d.base_color);
  opacity.Set(d.opacity);
  if (d.opacity_threshold > 0.0f)
    surf.CreateInput(TfToken("opacityThreshold"), SdfValueTypeNames->Float).Set(d.opacity_threshold);

  if (!d.base_texture.empty()) {
    // the texture read through the mesh's `st`, tinted by the colour factor (UsdUVTexture's scale)
    UsdShadeShader reader = UsdShadeShader::Define(stage, path.AppendChild(TfToken("StReader")));
    reader.CreateIdAttr(VtValue(TfToken("UsdPrimvarReader_float2")));
    reader.CreateInput(TfToken("varname"), SdfValueTypeNames->String).Set(std::string("st"));
    UsdShadeOutput st = reader.CreateOutput(TfToken("result"), SdfValueTypeNames->Float2);

    UsdShadeShader tex = UsdShadeShader::Define(stage, path.AppendChild(TfToken("BaseColorTexture")));
    tex.CreateIdAttr(VtValue(TfToken("UsdUVTexture")));
    tex.CreateInput(TfToken("file"), SdfValueTypeNames->Asset).Set(SdfAssetPath(asset_path(udim::as_set(d.base_texture))));
    tex.CreateInput(TfToken("st"), SdfValueTypeNames->Float2).ConnectToSource(st);
    tex.CreateInput(TfToken("wrapS"), SdfValueTypeNames->Token).Set(TfToken("repeat"));
    tex.CreateInput(TfToken("wrapT"), SdfValueTypeNames->Token).Set(TfToken("repeat"));
    tex.CreateInput(TfToken("sourceColorSpace"), SdfValueTypeNames->Token).Set(TfToken("sRGB"));
    tex.CreateInput(TfToken("scale"), SdfValueTypeNames->Float4)
        .Set(GfVec4f(d.base_color[0], d.base_color[1], d.base_color[2], d.opacity));
    color.ConnectToSource(tex.CreateOutput(TfToken("rgb"), SdfValueTypeNames->Float3));
    // the texture's alpha only where the material is see-through or cut out (else an opaque PNG's alpha is noise)
    if (d.opacity < 1.0f || d.opacity_threshold > 0.0f)
      opacity.ConnectToSource(tex.CreateOutput(TfToken("a"), SdfValueTypeNames->Float));
  }
  return mat;
}

void bind(const UsdPrim& prim, const UsdShadeMaterial& m) { UsdShadeMaterialBindingAPI::Apply(prim).Bind(m); }

void bind_per_face(const UsdGeomMesh& mesh, const std::vector<int>& face_material,
                   const std::vector<UsdShadeMaterial>& materials) {
  std::map<int, VtIntArray> faces;  // material -> its faces
  for (size_t f = 0; f < face_material.size(); ++f) {
    const int m = face_material[f];
    if (m >= 0 && size_t(m) < materials.size()) faces[m].push_back(int(f));
  }
  if (faces.empty()) return;
  if (faces.size() == 1 && faces.begin()->second.size() == face_material.size()) {
    bind(mesh.GetPrim(), materials[size_t(faces.begin()->first)]);
    return;
  }
  UsdShadeMaterialBindingAPI api = UsdShadeMaterialBindingAPI::Apply(mesh.GetPrim());
  for (const auto& [m, list] : faces) {
    const std::string name = materials[size_t(m)].GetPrim().GetName().GetString();
    UsdGeomSubset subset = api.CreateMaterialBindSubset(TfToken(name), list, UsdGeomTokens->face);
    bind(subset.GetPrim(), materials[size_t(m)]);
  }
  api.SetMaterialBindSubsetsFamilyType(UsdGeomTokens->nonOverlapping);
}

std::string cache_image(const std::string& file, const std::string& name, const void* bytes, std::size_t size) {
  std::error_code ec;
  const fs::path src = fs::u8path(file);
  const auto file_size = fs::file_size(src, ec);
  const auto stamp = fs::last_write_time(src, ec).time_since_epoch().count();
  char hash[32];
  std::snprintf(hash, sizeof hash, "%016llx",
                (unsigned long long)std::hash<std::string>{}(
                    asset_path(file) + "|" + std::to_string(file_size) + "|" + std::to_string(stamp)));
  const wchar_t* local = _wgetenv(L"LOCALAPPDATA");  // wide: a user folder name in any script
  const fs::path dir = (local ? fs::path(local) : fs::temp_directory_path()) / "Rostrum" / "3d-import-cache" / hash;
  fs::create_directories(dir, ec);
  if (ec) throw Error("could not make the folder for " + stem_of(file) + "'s images (" + dir.u8string() + ")");
  const fs::path out = dir / fs::u8path(name);
  if (!fs::exists(out) || fs::file_size(out, ec) != size) {
    std::ofstream f(out, std::ios::binary);
    f.write(static_cast<const char*>(bytes), std::streamsize(size));
    if (!f) throw Error("could not write the image " + out.u8string());
  }
  return out.u8string();
}

}  // namespace r3d::cv
