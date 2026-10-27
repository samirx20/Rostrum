// Clay items of the scene (clay_scene.h): the Xform, and the steps read loudly for the clay store.
#include "clay_scene.h"

#include <array>
#include <cmath>
#include <filesystem>
#include <memory>

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

// a list of [x, y] number pairs, at least `least`
std::vector<std::array<float, 2>> pairs(Reader& s, const char* key, size_t least, const char* what) {
  const JsArray& list = s.list(key);
  if (list.size() < least)
    fail(s.at(key), std::to_string(list.size()) + " points", "at least " + std::to_string(least) + " " + what);
  std::vector<std::array<float, 2>> out;
  for (size_t i = 0; i < list.size(); ++i) {
    const std::string at = s.at(key) + "[" + std::to_string(i) + "]";
    if (!list[i].IsArray() || list[i].GetJsArray().size() != 2) fail(at, "is not a list of 2", what);
    std::array<float, 2> q;
    for (int k = 0; k < 2; ++k) {
      const JsValue& x = list[i].GetJsArray()[k];
      if (!is_number(x) || !std::isfinite(to_number(x))) fail(at, "holds " + x.GetTypeName(), what);
      q[k] = float(to_number(x));
    }
    out.push_back(q);
  }
  return out;
}

// twice the signed area of the closed polygon (shoelace)
double area2(const std::vector<std::array<float, 2>>& p) {
  double a = 0;
  for (size_t i = 0, j = p.size() - 1; i < p.size(); j = i++) a += double(p[j][0]) * p[i][1] - double(p[i][0]) * p[j][1];
  return a;
}

// CL3: a drawn (outline), spun (spin) or item piece (CL3-CONTRACT § 2), checked here; its field is made when it is applied
void read_shape(Reader& s, const std::string& shape, clay::ShapeSpec& spec) {
  using K = clay::ShapeSpec::Kind;
  if (shape == "item") {
    spec.kind = K::Item;
    spec.source = s.str("source");
    if (spec.source.empty()) fail(s.at("source"), "is empty", "the id of the part or import the clay was made from");
    if (s.has("sourceKey")) s.str("sourceKey");  // Python's hash of the source: in the key, not used here
    return;
  }
  const JsArray& plane = s.list("plane");
  const char* planeWhat = "9 numbers [ox, oy, oz, ux, uy, uz, vx, vy, vz]: an origin and two unit, perpendicular axes";
  if (plane.size() != 9) fail(s.at("plane"), std::to_string(plane.size()) + " numbers", planeWhat);
  float q[9];
  for (int i = 0; i < 9; ++i) {
    if (!is_number(plane[i]) || !std::isfinite(to_number(plane[i])))
      fail(s.at("plane"), "holds " + plane[i].GetTypeName(), planeWhat);
    q[i] = float(to_number(plane[i]));
  }
  spec.o = {q[0], q[1], q[2]};
  spec.u = {q[3], q[4], q[5]};
  spec.v = {q[6], q[7], q[8]};
  if (std::fabs(clay::len(spec.u) - 1) > 1e-3f || std::fabs(clay::len(spec.v) - 1) > 1e-3f ||
      std::fabs(clay::dot(spec.u, spec.v)) > 1e-3f)
    fail(s.at("plane"), "the axes are not unit length and perpendicular", planeWhat);
  spec.u = clay::unit(spec.u);
  spec.v = clay::unit(spec.v);
  if (shape == "outline") {
    spec.kind = K::Outline;
    spec.pts = pairs(s, "outline", 3, "[u, v] points in the plane (metres)");
    if (!(std::fabs(area2(spec.pts)) > 1e-12)) fail(s.at("outline"), "encloses no area", "an outline round an area");
    spec.puff = 1.0f;
    if (s.has("puff")) {
      spec.puff = float(s.num("puff"));
      if (!(spec.puff >= 0.1f && spec.puff <= 3.0f)) fail(s.at("puff"), std::to_string(spec.puff), "0.1 .. 3");
    }
  } else {
    spec.kind = K::Spin;
    spec.pts = pairs(s, "profile", 2, "[r, h] points: distance from the axis (>= 0) and height along it (metres)");
    for (size_t i = 0; i < spec.pts.size(); ++i)
      if (spec.pts[i][0] < 0)
        fail(s.at("profile") + "[" + std::to_string(i) + "]", "r " + std::to_string(spec.pts[i][0]), "r >= 0");
    std::vector<std::array<float, 2>> closed = spec.pts;  // closed by the axis
    closed.insert(closed.begin(), std::array<float, 2>{0.0f, spec.pts.front()[1]});
    closed.push_back(std::array<float, 2>{0.0f, spec.pts.back()[1]});
    if (!(std::fabs(area2(closed)) > 1e-12)) fail(s.at("profile"), "encloses no area with the axis", "a profile reaching out from the axis");
  }
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
    const std::string shape = s.has("shape") ? s.one_of("shape", {"sphere", "capsule", "outline", "spin", "item"}) : "";
    if (shape.empty() || shape == "sphere" || shape == "capsule") {
      p.a = v3(s.vec3("a"));
      p.b = v3(s.vec3("b"));
      p.radius = float(positive(s, "radius"));
    } else {
      read_shape(s, shape, st.spec);
    }
    p.blend = float(s.num_min("blend", 0.0, true));
    p.mirror = s.flag("mirror");
  } else {
    clay::Brush& b = st.brush;
    b.op = op_of(s, {"add", "carve", "smooth", "pull", "flatten", "crease", "mask"});
    b.radius = float(positive(s, "radius"));
    b.strength = float(s.num("strength"));
    if (b.strength < 0 || b.strength > 1) fail(s.at("strength"), std::to_string(b.strength), "0..1");
    b.mirror = s.flag("mirror");
    b.accumulate = s.flag("accumulate");
    // CL2's settings; a step without them (CL1) is applied as CL1 did: falloff 0.5, spacing 0.3, every face, as is
    if (s.has("falloff")) {
      b.falloff = float(s.num("falloff"));
      if (!(b.falloff >= 0 && b.falloff <= 1)) fail(s.at("falloff"), std::to_string(b.falloff), "0 (soft) .. 1 (hard)");
    }
    if (s.has("spacing")) {
      b.spacing = float(s.num("spacing"));
      if (!(b.spacing >= 0.05f && b.spacing <= 1))
        fail(s.at("spacing"), std::to_string(b.spacing), "0.05 .. 1 (x the radius)");
    }
    if (s.has("frontOnly")) b.frontOnly = s.flag("frontOnly");
    if (s.has("invert")) b.invert = s.flag("invert");
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
        const size_t w = rows[i].IsArray() ? rows[i].GetJsArray().size() : 0;
        if (w != 9 && w != 11)
          fail(at, "is not a list of 9 or 11",
               "[ax, ay, az, nx, ny, nz, bx, by, bz] numbers, then radiusScale, strengthScale (pen pressure) or none");
        clay::DabRow r;
        r[9] = r[10] = 1.0f;  // no pen
        for (size_t k = 0; k < w; ++k) {
          const JsValue& x = rows[i].GetJsArray()[k];
          if (!is_number(x)) fail(at, "holds " + x.GetTypeName(), "numbers");
          r[k] = float(to_number(x));
        }
        if (!(r[9] > 0 && r[9] <= 1) || !(r[10] >= 0 && r[10] <= 1))
          fail(at, "has pen scales " + std::to_string(r[9]) + ", " + std::to_string(r[10]),
               "radiusScale above 0 up to 1, strengthScale 0..1");
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
  if (node.has("paint")) {  // 3d-cl4: the clay holds paint, its surface is unfolded (clay_surface.h)
    Reader paint(node.object("paint"), node.at("paint"));
    n.paintFile = paint.str("file");
    if (!std::filesystem::u8path(n.paintFile).is_absolute())
      fail(paint.at("file"), "\"" + n.paintFile + "\" is not an absolute path", "the surface file's absolute path");
    n.paintSize = paint.count("size", 64, 16384);
    paint.finish();
  }
  if (node.has("skin")) {  // CL5: the clay bends with its bones (clay_skin.h)
    n.skin = std::make_shared<SkinRig>(read_skin(node.object("skin"), it.id + ".skin"));
    n.skinStart = it.ctx.start;
  }
  const JsArray& steps = node.list("steps");
  for (size_t i = 0; i < steps.size(); ++i)
    n.steps.push_back(read_step(steps[i], it.id + ".steps[" + std::to_string(i) + "]"));
  return n;
}

}  // namespace r3d
