// Clay items of the scene (clay_scene.h): the Xform, and the steps read loudly for the clay store.
#include "clay_scene.h"

#include <filesystem>

#include <pxr/usd/usdGeom/xform.h>
#include <pxr/usd/usdShade/tokens.h>

#include "item_track.h"
#include "mesh_build.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {

clay::V3 v3(const GfVec3f& v) { return {v[0], v[1], v[2]}; }

clay::Op op_of(Reader& s, const std::vector<std::string>& accepted) {
  clay::Op op = clay::Op::Add;
  clay::op_from_name(s.one_of("op", accepted).c_str(), op);
  return op;
}

double positive(Reader& s, const char* key) {
  const double d = s.num(key);
  if (!(d > 0)) fail(s.at(key), std::to_string(d), "a number above 0 (metres)");
  return d;
}

clay::StepNode read_step(const JsValue& value, const std::string& where) {
  if (!value.IsObject()) fail(where, "is " + value.GetTypeName(), "a step object {\"key\", \"kind\", …}");
  Reader s(value.GetJsObject(), where);
  clay::StepNode st;
  st.where = where;
  st.key = s.str("key");
  if (st.key.empty()) fail(s.at("key"), "is empty", "the step's chain hash");
  st.piece = s.one_of("kind", {"piece", "stroke"}) == "piece";
  if (st.piece) {
    clay::Step& p = st.shape;
    p.kind = clay::Kind::Piece;
    p.op = op_of(s, {"add", "carve"});
    p.a = v3(s.vec3("a"));
    p.b = v3(s.vec3("b"));
    p.radius = float(positive(s, "radius"));
    p.blend = float(s.num_min("blend", 0.0, true));
    p.mirror = s.flag("mirror");
  } else {
    clay::Brush& b = st.brush;
    b.op = op_of(s, {"add", "carve", "smooth", "pull", "flatten", "crease"});
    b.radius = float(positive(s, "radius"));
    b.strength = float(s.num("strength"));
    if (b.strength < 0 || b.strength > 1) fail(s.at("strength"), std::to_string(b.strength), "0..1");
    b.mirror = s.flag("mirror");
    b.accumulate = s.flag("accumulate");
    const int ways = int(s.has("dabs")) + int(s.has("dabList")) + int(s.has("path") || s.has("dir"));
    const char* accepted = "exactly one of dabs (a .dabs file), dabList (inline) or path + dir";
    if (ways != 1) fail(where, std::to_string(ways) + " stroke paths given", accepted);
    if (s.has("dabs")) {
      st.path = clay::StepNode::Path::File;
      st.file = s.str("dabs");
      const std::filesystem::path f = std::filesystem::u8path(st.file);
      if (!f.is_absolute() || !std::filesystem::is_regular_file(f))
        fail(s.at("dabs"), "no file \"" + st.file + "\"", "the absolute path of the stroke's .dabs file");
      st.name = f.filename().u8string();
    } else if (s.has("dabList")) {
      st.path = clay::StepNode::Path::Inline;
      const JsArray& rows = s.list("dabList");
      for (size_t i = 0; i < rows.size(); ++i) {
        const std::string at = s.at("dabList") + "[" + std::to_string(i) + "]";
        if (!rows[i].IsArray() || rows[i].GetJsArray().size() != 9)
          fail(at, "is not a list of 9", "[ax, ay, az, nx, ny, nz, bx, by, bz] numbers");
        clay::DabRow r;
        for (int k = 0; k < 9; ++k) {
          const JsValue& x = rows[i].GetJsArray()[k];
          if (!is_number(x)) fail(at, "holds " + x.GetTypeName(), "numbers");
          r[k] = float(to_number(x));
        }
        st.rows.push_back(r);
      }
    } else {
      st.path = clay::StepNode::Path::Along;
      const JsArray& pts = s.list("path");
      if (pts.empty()) fail(s.at("path"), "is empty", "one or more [x, y, z] points (clay space)");
      for (size_t i = 0; i < pts.size(); ++i)
        st.along.push_back(v3(Reader::vec3_of(pts[i], s.at("path") + "[" + std::to_string(i) + "]")));
      st.dir = v3(s.vec3("dir"));
      if (clay::len(st.dir) < 1e-9f) fail(s.at("dir"), "is [0, 0, 0]", "the direction the strokes press along");
    }
  }
  s.finish();
  return st;
}

}  // namespace

clay::Node build_clay(Item& it, Reader& node, const SdfPath& path) {
  UsdPrim prim = UsdGeomXform::Define(it.ctx.stage, path).GetPrim();
  author_transform(it, prim);
  clay::Node n;
  n.id = it.id;
  n.path = path;
  const double detail = it.props.num("detail");
  if (!(detail >= 0.0001 && detail <= 0.1)) fail(it.props.at("detail"), std::to_string(detail), "0.0001 .. 0.1 (metres per grain)");
  n.detail = float(detail);
  // the block meshes are children of the Xform: they take its material (fallback strength: inherited)
  bind_material(it, prim, it.props.str("material"), it.props.at("material"), UsdShadeTokens->fallbackStrength);
  it.props.flag("smooth");  // always smooth normals for now
  n.cache = node.str("cache");
  if (!n.cache.empty() && !std::filesystem::u8path(n.cache).is_absolute())
    fail(node.at("cache"), "\"" + n.cache + "\" is not an absolute path", "\"\" or the cache file's absolute path");
  const JsArray& steps = node.list("steps");
  for (size_t i = 0; i < steps.size(); ++i)
    n.steps.push_back(read_step(steps[i], it.id + ".steps[" + std::to_string(i) + "]"));
  return n;
}

}  // namespace r3d
