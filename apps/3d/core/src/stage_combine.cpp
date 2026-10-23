// `combine` items (ENGINE_CONTRACT.md § 2): children are inputs only, never prims of their own. Each child
// is a `mesh` or a nested `combine`, placed in the combine's space by its own transform; the result is one
// UsdGeomMesh at the combine's path, with the combine's transform, visibility and material.
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/rotation.h>
#include <pxr/usd/usdShade/tokens.h>

#include "boolean.h"
#include "mesh_build.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

// USD's translate · rotateXYZ · scale op order as one matrix (row vectors: scale first, then rx, ry, rz).
GfMatrix4d local_xform(Reader& p) {
  const double x = p.num("x"), y = p.num("y"), z = p.num("z");
  const double rx = p.num("rx"), ry = p.num("ry"), rz = p.num("rz");
  const double sx = p.num("sx"), sy = p.num("sy"), sz = p.num("sz");
  GfMatrix4d s, r, t;
  s.SetScale(GfVec3d(sx, sy, sz));
  r.SetRotate(GfRotation(GfVec3d::XAxis(), rx) * GfRotation(GfVec3d::YAxis(), ry) * GfRotation(GfVec3d::ZAxis(), rz));
  t.SetTranslate(GfVec3d(x, y, z));
  return s * r * t;
}

MeshData combined(ItemsContext& ctx, const std::string& id, Reader& props, const JsArray& children);

Solid child_solid(ItemsContext& ctx, const JsValue& value, const std::string& owner, const std::string& where) {
  if (!value.IsObject()) fail(where, "is " + value.GetTypeName(), "a mesh or combine item object");
  const std::string id = Reader(value.GetJsObject(), where).str("id");
  check_id(id, where + ".id");
  if (!ctx.ids.insert(id).second) fail(where + ".id", "\"" + id + "\" is used twice", "ids unique in the scene");
  Reader r(value.GetJsObject(), id);
  r.str("id");
  const std::string type = r.one_of("type", {"mesh", "combine"});
  if (r.has("anim"))
    fail(id, "an input of combine '" + owner + "' can't be animated yet; key the combine itself",
         "no anim on a combine's children");
  Reader p(r.object("props"), id);
  Solid s;
  s.id = id;
  s.xform = local_xform(p);
  p.flag("visible");  // an input is never shown on its own
  p.str("material");  // the combine's own material colours the result
  if (type == "mesh") {
    FaceGroups unused;
    s.mesh = shape(p, unused);
    mesh_known(p);
  } else {
    s.mesh = combined(ctx, id, p, r.list("children"));
  }
  p.finish();
  r.finish();
  return s;
}

MeshData combined(ItemsContext& ctx, const std::string& id, Reader& props, const JsArray& children) {
  const std::string op = props.one_of("op", {"union", "subtract", "intersect"});
  if (children.size() < 2)
    fail(id + ".children", std::to_string(children.size()) + " children",
         "2 or more mesh or combine children (the first is the base)");
  std::vector<Solid> solids;
  for (size_t i = 0; i < children.size(); ++i)
    solids.push_back(child_solid(ctx, children[i], id, id + ".children[" + std::to_string(i) + "]"));
  const CombineOp kind = op == "union" ? CombineOp::Union : op == "subtract" ? CombineOp::Subtract : CombineOp::Intersect;
  return combine_solids(solids, kind, id);
}

}  // namespace

void build_combine(Item& it, const JsArray& children, const SdfPath& path) {
  UsdGeomMesh m = UsdGeomMesh::Define(it.ctx.stage, path);
  author_transform(it, m.GetPrim());
  write_mesh(m, combined(it.ctx, it.id, it.props, children));
  bind_material(it, m.GetPrim(), it.props.str("material"), it.props.at("material"), UsdShadeTokens->fallbackStrength);
}

}  // namespace r3d
