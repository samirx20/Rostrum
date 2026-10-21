#include "stage_items.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <vector>

#include <pxr/base/gf/vec3d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/sdf/primSpec.h>
#include <pxr/usd/usd/references.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>
#include <pxr/usd/usdGeom/subset.h>
#include <pxr/usd/usdGeom/xform.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>
#include <cstdio>

#include "extrude.h"
#include "item_track.h"
#include "materials.h"
#include "primitives.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

void check_id(const std::string& id, const std::string& where) {
  bool ok = !id.empty() && !std::isdigit(static_cast<unsigned char>(id[0]));
  for (char ch : id) ok = ok && (std::isalnum(static_cast<unsigned char>(ch)) || ch == '_');
  if (!ok) fail(where, "\"" + id + "\" is not a valid id", "letters A-Z a-z, digits and _, not starting with a digit");
  if (id == "Looks") fail(where, "\"Looks\" is taken (/World/Looks holds the materials)", "any other id");
}

void author_transform(Item& it, const UsdPrim& prim) {
  UsdGeomXformable x(prim);
  const auto px = it.nums("x"), py = it.nums("y"), pz = it.nums("z");
  const auto rx = it.nums("rx"), ry = it.nums("ry"), rz = it.nums("rz");
  const auto sx = it.nums("sx"), sy = it.nums("sy"), sz = it.nums("sz");
  const std::vector<bool> visible = it.flags("visible");
  it.write<GfVec3d>(x.AddTranslateOp().GetAttr(), frames({px.size(), py.size(), pz.size()}),
                    [&](size_t i) { return GfVec3d(pick(px, i), pick(py, i), pick(pz, i)); });
  it.write<GfVec3f>(x.AddRotateXYZOp().GetAttr(), frames({rx.size(), ry.size(), rz.size()}),
                    [&](size_t i) { return GfVec3f(float(pick(rx, i)), float(pick(ry, i)), float(pick(rz, i))); });
  it.write<GfVec3f>(x.AddScaleOp().GetAttr(), frames({sx.size(), sy.size(), sz.size()}),
                    [&](size_t i) { return GfVec3f(float(pick(sx, i)), float(pick(sy, i)), float(pick(sz, i))); });
  it.write<TfToken>(UsdGeomImageable(prim).CreateVisibilityAttr(), visible.size(), [&](size_t i) {
    return pick(visible, i) ? UsdGeomTokens->inherited : UsdGeomTokens->invisible;
  });
}

namespace {

void bind_material(Item& it, const UsdPrim& prim, const std::string& mat, const std::string& where, const TfToken& strength) {
  if (mat.empty()) return;
  const auto& ids = it.ctx.materials;
  if (!ids.count(mat))
    fail(where, "no material \"" + mat + "\"",
         ids.empty() ? "\"\" (the scene has no materials)"
                     : "\"\" or " + join(std::vector<std::string>(ids.begin(), ids.end())));
  const UsdShadeMaterial m = UsdShadeMaterial::Get(it.ctx.stage, material_path(mat));
  if (!UsdShadeMaterialBindingAPI::Apply(prim).Bind(m, strength))
    fail(where, "could not bind material \"" + mat + "\" to " + prim.GetPath().GetString(), "a material of this scene");
}

// `groups` gets the faces of each part (front, bevel, side, back) for an outline; other shapes leave it empty.
MeshData shape(Reader& p, FaceGroups& groups) {
  const std::string s = p.one_of("shape", {"box", "sphere", "cylinder", "plane", "disc", "torus", "outline"});
  const bool smooth = p.flag("smooth");
  auto size = [&](const char* key) { return float(p.num_min(key, 0.0, false)); };
  auto bevel = [&](float most) {
    const float b = float(p.num_min("bevel", 0.0, true));
    if (b > most) fail(p.at("bevel"), std::to_string(b) + " is too big for the shape", "0 .. " + std::to_string(most));
    return b;
  };
  if (s == "box") {
    const float w = size("width"), h = size("height"), d = size("depth");
    const float b = bevel(std::min({w, h, d}) / 2);
    return make_box(w, h, d, b, p.count("segments", 1, 256), smooth);
  }
  if (s == "cylinder") {
    const float r = size("radius"), h = size("height");
    const float b = bevel(std::min(r, h / 2));
    return make_cylinder(r, h, b, p.count("segments", 3, 1024), smooth);
  }
  if (s == "sphere") {
    const float r = size("radius");
    return make_sphere(r, p.count("segments", 3, 1024), smooth);
  }
  if (s == "torus") {
    const float r = size("radius"), tube = size("tube");
    return make_torus(r, tube, p.count("segments", 3, 1024), smooth);
  }
  if (s == "disc") {
    const float r = size("radius");
    return make_disc(r, p.count("segments", 3, 1024));
  }
  if (s == "outline") {
    const float d = float(p.num_min("depth", 0.0, true));
    const float b = bevel(d / 2);
    const std::vector<OutlineShape> shapes = read_outline(p.list("outline"), p.at("outline"));
    Extruded e = make_extrusion(shapes, d, b, p.count("segments", 1, 1024), smooth, p.where());
    groups = std::move(e.groups);
    return std::move(e.mesh);
  }
  const float w = size("width"), d = size("depth");
  return make_plane(w, d);
}

// An outline's parts as a "materialBind" partition of GeomSubsets (Storm and Cycles' Hydra plug-in both
// read them), each bound to its material: "" = the mesh's material, and for the bevel the front's.
void bind_parts(Item& it, const UsdGeomMesh& m, const FaceGroups& groups, const std::string& mat) {
  std::string mats[4], where[4];
  for (int g = 0; g < 4; ++g) {
    const std::string key = std::string(kFacePartNames[g]) + "Material";
    mats[g] = it.props.str(key);
    where[g] = it.props.at(key);
  }
  for (int g : {kFront, kSide, kBack, kBevel}) {  // the bevel last: it falls back on the resolved front
    if (!mats[g].empty()) continue;
    mats[g] = g == kBevel ? mats[kFront] : mat;
    where[g] = g == kBevel ? where[kFront] : it.props.at("material");
  }
  UsdShadeMaterialBindingAPI api = UsdShadeMaterialBindingAPI::Apply(m.GetPrim());
  for (int g = 0; g < 4; ++g) {
    if (groups[g].empty()) continue;
    const UsdGeomSubset sub = api.CreateMaterialBindSubset(TfToken(kFacePartNames[g]), groups[g]);
    bind_material(it, sub.GetPrim(), mats[g], where[g], UsdShadeTokens->fallbackStrength);
  }
  api.SetMaterialBindSubsetsFamilyType(UsdGeomTokens->partition);
}

void build_mesh(Item& it, const SdfPath& path) {
  UsdGeomMesh m = UsdGeomMesh::Define(it.ctx.stage, path);
  author_transform(it, m.GetPrim());
  FaceGroups groups;
  const MeshData d = shape(it.props, groups);
  m.CreatePointsAttr().Set(d.points);
  m.CreateNormalsAttr().Set(d.normals);
  m.SetNormalsInterpolation(UsdGeomTokens->vertex);  // Cycles ignores face-varying normals
  m.CreateFaceVertexCountsAttr().Set(d.counts);
  m.CreateFaceVertexIndicesAttr().Set(d.indices);
  m.CreateSubdivisionSchemeAttr().Set(UsdGeomTokens->none);
  UsdGeomPrimvarsAPI(m.GetPrim())
      .CreatePrimvar(TfToken("st"), SdfValueTypeNames->TexCoord2fArray, UsdGeomTokens->faceVarying)
      .Set(d.st);
  VtVec3fArray extent;
  if (UsdGeomPointBased::ComputeExtent(d.points, &extent)) m.CreateExtentAttr().Set(extent);
  const std::string mat = it.props.str("material");
  bind_material(it, m.GetPrim(), mat, it.props.at("material"), UsdShadeTokens->fallbackStrength);
  if (!groups[kFront].empty()) bind_parts(it, m, groups, mat);
}

// An import references the file; its material and its parts' changes are overrides in our layer.
void build_import(Item& it, const SdfPath& path) {
  const UsdStageRefPtr& stage = it.ctx.stage;
  UsdPrim prim = UsdGeomXform::Define(stage, path).GetPrim();
  author_transform(it, prim);
  Reader& p = it.props;
  const std::string file = p.str("file"), inner = p.str("prim");
  const std::string kinds = "the absolute path of a .usd, .usda, .usdc or .usdz file";
  if (file.empty()) fail(p.at("file"), "is empty", kinds);
  check_file(file, p.at("file"), "a .usd, .usda, .usdc or .usdz file");
  std::string ext = std::filesystem::path(file).extension().string();
  std::transform(ext.begin(), ext.end(), ext.begin(), [](unsigned char c) { return char(std::tolower(c)); });
  if (ext != ".usd" && ext != ".usda" && ext != ".usdc" && ext != ".usdz") fail(p.at("file"), "is not a USD file", kinds);
  if (inner.empty()) {
    prim.GetReferences().AddReference(file);
  } else {
    if (!SdfPath::IsValidPathString(inner) || !SdfPath(inner).IsAbsolutePath() || !SdfPath(inner).IsPrimPath())
      fail(p.at("prim"), "\"" + inner + "\" is not a prim path", "\"\" (the file's default prim) or a path like /Root/Body");
    prim.GetReferences().AddReference(file, SdfPath(inner));
  }
  if (prim.GetPrimStack().size() < 2)  // only our own spec: the reference brought nothing in
    fail(p.at(inner.empty() ? "file" : "prim"),
         "nothing came in: the file did not open, or has no " + (inner.empty() ? "default prim" : "prim " + inner),
         "a file and prim that inspect_usd lists");

  const std::string mat = p.str("material");
  bind_material(it, prim, mat, p.at("material"), UsdShadeTokens->strongerThanDescendants);
  const JsArray& parts = p.list("parts");
  std::vector<SdfPath> painted;  // parts given a material: none may hold another (the outer one would win)
  for (size_t i = 0; i < parts.size(); ++i) {
    const std::string where = it.id + ".parts[" + std::to_string(i) + "]";
    if (!parts[i].IsObject()) fail(where, "is " + parts[i].GetTypeName(), "{\"path\", \"material\", \"visible\"}");
    Reader part(parts[i].GetJsObject(), where);
    const std::string rel = part.str("path");
    const std::string accepted = "a path from inspect_usd, relative to the import's prim, like Body/Screen";
    if (!SdfPath::IsValidPathString(rel) || SdfPath(rel).IsAbsolutePath() || !SdfPath(rel).IsPrimPath())
      fail(part.at("path"), "\"" + rel + "\" is not a relative prim path", accepted);
    const SdfPath ppath = path.AppendPath(SdfPath(rel));
    if (!ppath.HasPrefix(path) || ppath == path || !stage->GetPrimAtPath(ppath))
      fail(part.at("path"), "no part \"" + rel + "\" in the file", accepted);
    UsdPrim over = stage->OverridePrim(ppath);
    const std::string pm = part.str("material");
    if (!pm.empty() && !mat.empty())
      fail(part.at("material"), "the whole import already has material \"" + mat + "\"",
           "\"\" here, or \"\" for " + it.id + ".material");
    for (const SdfPath& other : painted)
      if (!pm.empty() && (ppath.HasPrefix(other) || other.HasPrefix(ppath)))
        fail(part.at("material"), "this part and part " + other.GetString() + " both set a material and one holds the other",
             "materials on parts that don't contain each other");
    if (!pm.empty()) painted.push_back(ppath);
    bind_material(it, over, pm, part.at("material"), UsdShadeTokens->strongerThanDescendants);
    UsdGeomImageable(over).CreateVisibilityAttr().Set(part.flag("visible") ? UsdGeomTokens->inherited
                                                                           : UsdGeomTokens->invisible);
    part.finish();
  }
}

void build_item(ItemsContext& ctx, const JsValue& value, const SdfPath& parent, const std::string& where) {
  if (!value.IsObject()) fail(where, "is " + value.GetTypeName(), "an item object");
  const std::string id = Reader(value.GetJsObject(), where).str("id");
  check_id(id, where + ".id");
  if (!ctx.ids.insert(id).second) fail(where + ".id", "\"" + id + "\" is used twice", "ids unique in the scene");
  Reader r(value.GetJsObject(), id);
  r.str("id");
  const std::string type = r.one_of("type", {"group", "mesh", "import", "light", "camera"});
  const SdfPath path = parent.AppendChild(TfToken(id));
  if (ctx.stage->GetPrimAtPath(path))
    fail(r.at("id"), "\"" + id + "\" is the name of a prim inside the imported file", "an id the file doesn't use");
  Item it(ctx, id, r.object("props"), r.has("anim") ? &r.object("anim") : nullptr);
  ++ctx.items;
  if (type == "group") author_transform(it, UsdGeomXform::Define(ctx.stage, path).GetPrim());
  if (type == "mesh") build_mesh(it, path);
  if (type == "import") build_import(it, path);
  if (type == "light") build_light(it, path);
  if (type == "camera") build_camera(it, path);
  if ((type == "group" || type == "import") && r.has("children"))
    build_items(ctx, r.list("children"), path, id + ".children");
  // shape / kind fields the chosen shape or kind doesn't use (the compiler sends every field)
  if (type == "mesh")
    it.props.known({"width", "height", "depth", "radius", "tube", "bevel", "segments", "outline", "frontMaterial",
                    "bevelMaterial", "sideMaterial", "backMaterial"});
  if (type == "light") it.props.known({"width", "height", "length", "radius", "angle", "texture"});
  it.finish();
  r.finish();
}

}  // namespace

void build_items(ItemsContext& ctx, const JsArray& items, const SdfPath& parent, const std::string& where) {
  for (size_t i = 0; i < items.size(); ++i) build_item(ctx, items[i], parent, where + "[" + std::to_string(i) + "]");
}

}  // namespace r3d
