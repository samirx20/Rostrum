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
#include <pxr/usd/usdGeom/subset.h>
#include <pxr/usd/usdGeom/xform.h>
#include <pxr/usd/usdShade/material.h>
#include <pxr/usd/usdShade/materialBindingAPI.h>
#include <cstdio>

#include "clay_scene.h"
#include "extrude.h"
#include "item_track.h"
#include "materials.h"
#include "mesh_build.h"
#include "skin.h"

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
  it.write_moving<GfVec3d>(x.AddTranslateOp().GetAttr(), frames({px.size(), py.size(), pz.size()}),
                    [&](size_t i) { return GfVec3d(pick(px, i), pick(py, i), pick(pz, i)); });
  it.write_moving<GfVec3f>(x.AddRotateXYZOp().GetAttr(), frames({rx.size(), ry.size(), rz.size()}),
                    [&](size_t i) { return GfVec3f(float(pick(rx, i)), float(pick(ry, i)), float(pick(rz, i))); });
  it.write_moving<GfVec3f>(x.AddScaleOp().GetAttr(), frames({sx.size(), sy.size(), sz.size()}),
                    [&](size_t i) { return GfVec3f(float(pick(sx, i)), float(pick(sy, i)), float(pick(sz, i))); });
  it.write<TfToken>(UsdGeomImageable(prim).CreateVisibilityAttr(), visible.size(), [&](size_t i) {
    return pick(visible, i) ? UsdGeomTokens->inherited : UsdGeomTokens->invisible;
  });
}

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

namespace {

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

void build_mesh(Item& it, const SdfPath& path, const JsObject* skin) {
  UsdGeomMesh m = UsdGeomMesh::Define(it.ctx.stage, path);
  author_transform(it, m.GetPrim());
  FaceGroups groups;
  MeshData d = shape(it.props, groups);
  own_uvs(it.props, d);
  write_mesh(m, d);
  if (skin) skin_mesh(m, d, *skin, it.ctx.start, it.id + ".skin");
  const std::string mat = it.props.str("material");
  bind_material(it, m.GetPrim(), mat, it.props.at("material"), UsdShadeTokens->fallbackStrength);
  if (!groups[kFront].empty()) bind_parts(it, m, groups, mat);
  if (!d.base_face.empty()) bind_face_materials(it, m, d, mat);
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
  const std::string type = r.one_of("type", {"group", "mesh", "combine", "import", "light", "camera", "clay"});
  const SdfPath path = parent.AppendChild(TfToken(id));
  if (ctx.stage->GetPrimAtPath(path))
    fail(r.at("id"), "\"" + id + "\" is the name of a prim inside the imported file", "an id the file doesn't use");
  Item it(ctx, id, r.object("props"), r.has("anim") ? &r.object("anim") : nullptr);
  ++ctx.items;
  if (type == "group") author_transform(it, UsdGeomXform::Define(ctx.stage, path).GetPrim());
  if (type == "mesh") build_mesh(it, path, r.has("skin") ? &r.object("skin") : nullptr);
  if (type == "combine") build_combine(it, r.list("children"), path);
  if (type == "import") build_import(it, path);
  if (type == "light") build_light(it, path);
  if (type == "camera") build_camera(it, path);
  if (type == "clay") ctx.clays.push_back(build_clay(it, r, path));
  if ((type == "group" || type == "import") && r.has("children"))
    build_items(ctx, r.list("children"), path, id + ".children");
  // shape / kind fields the chosen shape or kind doesn't use (the compiler sends every field)
  if (type == "mesh") mesh_known(it.props);
  if (type == "light") it.props.known({"width", "height", "length", "radius", "cone", "softness", "angle", "texture"});
  it.finish();
  r.finish();
}

}  // namespace

void build_items(ItemsContext& ctx, const JsArray& items, const SdfPath& parent, const std::string& where) {
  for (size_t i = 0; i < items.size(); ++i) build_item(ctx, items[i], parent, where + "[" + std::to_string(i) + "]");
}

}  // namespace r3d
