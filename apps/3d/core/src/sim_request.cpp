// The `simulate` request (ENGINE_CONTRACT.md § Simulation): each body's surface and start pose read from the held
// stage at `start` (send the scene without a stored result first), the bodies run through Jolt (sim.cpp), and the
// falling ones' poses written to `<folder>/bodies.bin` — float32, frames × rows × [x y z qx qy qz qw]: a plain item's
// translate and turn (world; it is top-level), a copy's position and orientation in its copies item's own space.
// A cloth (brief 26b) is a top-level shape: its mesh refined (sim_cloth.cpp) and its points per frame written to
// `<folder>/cloth_<item>.bin` in the item's own space as it stood at `start`, with the faces it was simulated with.
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/quatd.h>
#include <pxr/base/gf/rotation.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/mesh.h>
#include <pxr/usd/usdGeom/primvarsAPI.h>
#include <pxr/usd/usdGeom/xformCache.h>

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <map>

#include "args.h"
#include "error.h"
#include "inspect.h"
#include "json_read.h"
#include "requests.h"
#include "sim.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {

// a world matrix's frame: its origin and its turn (scale and shear taken out)
void frame_of(const GfMatrix4d& m, GfVec3d* origin, GfQuatd* turn) {
  *origin = m.ExtractTranslation();
  *turn = m.RemoveScaleShear().ExtractRotationQuat().GetNormalized();
}

GfVec3d to_body(const GfVec3d& world, const GfVec3d& origin, const GfQuatd& turn) {
  return turn.GetInverse().Transform(world - origin);
}

sim::V3 v3(const GfVec3d& v) { return {v[0], v[1], v[2]}; }

// Every visible mesh under `root` at `t`: its points (and, when `tris`, its triangles), through `to_world(mesh)` then
// into the body's frame.
template <class ToWorld>
void gather(const UsdPrim& root, UsdTimeCode t, const ToWorld& to_world, const GfVec3d& origin, const GfQuatd& turn,
            std::vector<sim::V3>* pts, std::vector<sim::V3>* tris) {
  for (UsdPrim p : UsdPrimRange(root, UsdTraverseInstanceProxies())) {
    if (!p.IsA<UsdGeomMesh>()) continue;
    const UsdGeomMesh mesh(p);
    if (mesh.ComputeVisibility(t) == UsdGeomTokens->invisible) continue;
    VtVec3fArray points;
    if (!mesh.GetPointsAttr().Get(&points, t) || points.empty()) continue;
    const GfMatrix4d m = to_world(p);
    std::vector<sim::V3> local(points.size());
    for (size_t i = 0; i < points.size(); ++i) local[i] = v3(to_body(m.Transform(GfVec3d(points[i])), origin, turn));
    pts->insert(pts->end(), local.begin(), local.end());
    if (!tris) continue;
    VtIntArray counts, index;
    mesh.GetFaceVertexCountsAttr().Get(&counts, t);
    mesh.GetFaceVertexIndicesAttr().Get(&index, t);
    size_t at = 0;
    for (int n : counts) {
      for (int k = 1; k + 1 < n && at + size_t(k) + 1 < index.size(); ++k)  // a fan over each face
        for (int c : {index[at], index[at + size_t(k)], index[at + size_t(k) + 1]})
          if (c >= 0 && size_t(c) < local.size()) tris->push_back(local[size_t(c)]);
      at += size_t(std::max(0, n));
    }
  }
}

sim::Body settings(const JsValue& v, size_t i) {
  const std::string where = "simulate.bodies[" + std::to_string(i) + "]";
  if (!v.IsObject()) fail(where, "is " + v.GetTypeName(), "a body object");
  Reader r(v.GetJsObject(), where);
  sim::Body b;
  b.item = r.str("item");
  b.falls = r.one_of("kind", {"falls", "still"}) == "falls";
  b.mass = r.num("mass");
  b.bounce = r.num("bounce");
  b.friction = r.num("friction");
  b.asleep = r.one_of("starts", {"moving", "asleep"}) == "asleep";
  const std::string shape = r.one_of("shape", {"exact", "box", "sphere"});
  b.shape = shape == "box" ? sim::Body::Box : shape == "sphere" ? sim::Body::Sphere : sim::Body::Exact;
  if (r.has("velocity")) {
    const GfVec3f vel = r.vec3("velocity");
    b.velocity = {vel[0], vel[1], vel[2]};
  }
  if (r.has("wakeFrame")) b.wake = r.count("wakeFrame", 0, 1000000);
  if (b.mass < 0) fail(r.at("mass"), "is below 0", "0 (from its size) or a mass in kg");
  r.finish();
  return b;
}

bool is_cloth(const JsValue& v) {
  if (!v.IsObject()) return false;
  const auto it = v.GetJsObject().find("kind");
  return it != v.GetJsObject().end() && it->second.IsString() && it->second.GetString() == "cloth";
}

sim::Cloth cloth_settings(const JsValue& v, size_t i) {
  Reader r(v.GetJsObject(), "simulate.bodies[" + std::to_string(i) + "]");
  sim::Cloth c;
  c.item = r.str("item");
  r.str("kind");
  c.weight = r.num("weight");
  c.stiffness = r.num("stiffness");
  if (r.has("wakeFrame")) c.wake = r.count("wakeFrame", 0, 1000000);
  c.friction = r.num("friction");
  if (r.has("air")) c.air = r.num("air");
  if (r.has("wind")) c.wind = r.num("wind");
  if (r.has("windTurn")) c.windTurn = r.num("windTurn");
  const std::string pin = r.one_of("pinned", {"none", "top", "bottom", "left", "right", "front", "back"});
  const char* pins[] = {"none", "top", "bottom", "left", "right", "front", "back"};
  for (int k = 0; k < 7; ++k)
    if (pin == pins[k]) c.pinned = sim::Cloth::Pin(k);
  if (!(c.weight > 0)) fail(r.at("weight"), "is not above 0", "kg per m², e.g. 0.2 (cotton)");
  if (c.stiffness < 0 || c.stiffness > 1) fail(r.at("stiffness"), "is outside 0..1", "0 (silk) .. 1 (thin card)");
  if (!(c.air >= 0 && c.air <= 4)) fail(r.at("air"), "is outside 0..4", "0 (no air) .. 1 (room air) .. 4");
  if (!(c.wind >= 0 && c.wind <= 5)) fail(r.at("wind"), "is outside 0..5", "0 (still air) .. 0.5 (a draught) .. 5 m/s");
  r.finish();
  return c;
}

// A cloth item's mesh at `t`, refined, its points in world space; `to_local` takes them back to the item's own space.
sim::Cloth gather_cloth(sim::Cloth c, const UsdPrim& prim, UsdTimeCode t, UsdGeomXformCache& xc, GfMatrix4d* to_local) {
  if (!prim.IsA<UsdGeomMesh>())
    throw Error("simulate: " + c.item + " is not a shape, so it can't be cloth: make a plane (or another shape) the cloth");
  const UsdGeomMesh mesh(prim);
  VtVec3fArray points;
  VtIntArray counts, index;
  mesh.GetPointsAttr().Get(&points, t);
  mesh.GetFaceVertexCountsAttr().Get(&counts, t);
  mesh.GetFaceVertexIndicesAttr().Get(&index, t);
  if (points.empty() || counts.empty())
    throw Error("simulate: " + c.item + " has no surface to drape: give it a shape (a plane drapes best), or set Simulate to Off");
  VtVec2fArray st;
  TfToken interp;
  if (const UsdGeomPrimvar pv = UsdGeomPrimvarsAPI(prim).GetPrimvar(TfToken("st"))) {
    pv.Get(&st, t);
    interp = pv.GetInterpolation();
  }
  c.points.resize(points.size());
  c.st.assign(points.size(), {0.0f, 0.0f});
  std::vector<bool> has_st(points.size(), false);
  for (size_t i = 0; i < points.size(); ++i) c.points[i] = v3(GfVec3d(points[i]));
  std::vector<std::vector<int>> faces;
  size_t at = 0;
  for (int n : counts) {
    std::vector<int> f;
    for (int k = 0; k < n && at + size_t(k) < index.size(); ++k) {
      const int p = index[at + size_t(k)];
      f.push_back(p);
      if (p < 0 || size_t(p) >= points.size() || has_st[size_t(p)]) continue;
      const size_t corner = at + size_t(k);  // a seam keeps the first corner's u v
      if (interp == UsdGeomTokens->faceVarying && corner < st.size()) c.st[size_t(p)] = {st[corner][0], st[corner][1]};
      else if (interp == UsdGeomTokens->vertex && size_t(p) < st.size()) c.st[size_t(p)] = {st[size_t(p)][0], st[size_t(p)][1]};
      has_st[size_t(p)] = true;
    }
    faces.push_back(std::move(f));
    at += size_t(std::max(0, n));
  }
  sim::refine(c, faces);
  if (c.triangles.empty())
    throw Error("simulate: " + c.item + " has no surface to drape (every face is flat to a line): give it a shape, or set Simulate to Off");
  const GfMatrix4d m = xc.GetLocalToWorldTransform(prim);
  if (std::abs(m.GetDeterminant()) < 1e-18)
    throw Error("simulate: " + c.item + " is scaled to nothing, so it can't be cloth: give it a size");
  *to_local = m.GetInverse();
  for (sim::V3& p : c.points) p = v3(m.Transform(GfVec3d(p[0], p[1], p[2])));
  return c;
}

template <class T>
void put_raw(std::ofstream& f, const T* data, size_t n) {
  f.write(reinterpret_cast<const char*>(data), std::streamsize(n * sizeof(T)));
}

// "RCL1", int32 points, triangles, frames, start; int32 × 3 × triangles; float32 × 2 × points (u v); then per frame
// float32 × 3 × points in the item's own space (ENGINE_CONTRACT § Simulation).
void write_cloth(const std::filesystem::path& file, const sim::Cloth& c, const std::vector<float>& world, int start, int frames,
                 const GfMatrix4d& to_local) {
  std::ofstream f(file, std::ios::binary);
  const int32_t head[4] = {int32_t(c.points.size()), int32_t(c.triangles.size()), int32_t(frames), int32_t(start)};
  f.write("RCL1", 4);
  put_raw(f, head, 4);
  std::vector<int32_t> tris;
  tris.reserve(c.triangles.size() * 3);
  for (const auto& t : c.triangles) tris.insert(tris.end(), {int32_t(t[0]), int32_t(t[1]), int32_t(t[2])});
  put_raw(f, tris.data(), tris.size());
  std::vector<float> st;
  st.reserve(c.st.size() * 2);
  for (const auto& uv : c.st) st.insert(st.end(), {uv[0], uv[1]});
  put_raw(f, st.data(), st.size());
  std::vector<float> local(world.size());
  for (size_t i = 0; i + 2 < world.size(); i += 3) {
    const GfVec3d p = to_local.Transform(GfVec3d(world[i], world[i + 1], world[i + 2]));
    local[i] = float(p[0]);
    local[i + 1] = float(p[1]);
    local[i + 2] = float(p[2]);
  }
  put_raw(f, local.data(), local.size());
  if (!f) throw Error("simulate: could not write " + file.u8string());
}

void put(std::vector<float>& out, const GfVec3d& p, const GfQuatd& q) {
  const GfVec3d im = q.GetImaginary();
  for (double x : {p[0], p[1], p[2], im[0], im[1], im[2], q.GetReal()}) out.push_back(float(x));
}

}  // namespace

JsObject Core::simulate(const JsObject& o, const std::function<void(const JsObject&)>& progress) {
  Args a(o, "simulate", {"start", "end", "fps", "folder", "progress", "ground", "bodies"});
  need_scene("simulate");
  sim::Setup setup;
  setup.start = a.whole("start");
  setup.end = a.whole("end");
  setup.fps = a.num("fps");
  check_frame(setup.start, "simulate.start");
  check_frame(setup.end, "simulate.end");
  const std::filesystem::path folder = std::filesystem::u8path(a.str("folder"));
  if (!std::filesystem::is_directory(folder)) throw Error("simulate.folder: no folder " + a.str("folder"));
  setup.ground = a.has("ground");
  if (setup.ground) {
    const JsValue& g = a.need("ground");
    if (!g.IsObject()) throw Error("simulate.ground: needs {\"y\": height} or null (no ground)");
    Reader r(g.GetJsObject(), "simulate.ground");
    setup.groundY = r.num("y");
    r.finish();
  }
  const JsValue& list = a.need("bodies");
  if (!list.IsArray() || list.GetJsArray().empty()) throw Error("simulate.bodies: needs a list of one body or more");

  const UsdTimeCode t(setup.start);
  UsdGeomXformCache xc(t);
  std::vector<sim::Body> bodies;
  std::vector<sim::Cloth> cloths;
  std::vector<GfMatrix4d> cloth_local;  // each cloth: world → its own space at `start`
  struct CopiesOut { GfMatrix4d to_local; GfQuatd turn_back; };
  std::map<std::string, CopiesOut> copies_out;  // a falling copies item: world → its own space
  const auto twice = [&](const std::string& item, size_t i) {
    bool seen = false;
    for (const sim::Body& b : bodies) seen = seen || b.item == item;
    for (const sim::Cloth& c : cloths) seen = seen || c.item == item;
    if (seen) throw Error("simulate.bodies[" + std::to_string(i) + "].item: \"" + item + "\" is given twice");
  };
  for (size_t i = 0; i < list.GetJsArray().size(); ++i) {
    if (is_cloth(list.GetJsArray()[i])) {
      sim::Cloth c = cloth_settings(list.GetJsArray()[i], i);
      twice(c.item, i);
      const SdfPath path = item_path(stage_, c.item);
      const UsdPrim prim = path.IsEmpty() ? UsdPrim() : stage_->GetPrimAtPath(path);
      if (!prim) throw Error("simulate.bodies[" + std::to_string(i) + "].item: no item \"" + c.item + "\" in the scene");
      if (prim.GetParent().GetPath() != SdfPath("/World"))
        throw Error("simulate: " + c.item + " is inside " + prim.GetParent().GetName().GetString() +
                    "; only items at the top of the scene can be cloth: take it out first");
      GfMatrix4d back;
      cloths.push_back(gather_cloth(std::move(c), prim, t, xc, &back));
      cloth_local.push_back(back);
      continue;
    }
    const sim::Body base = settings(list.GetJsArray()[i], i);
    twice(base.item, i);
    const auto cs = copies_.find(base.item);
    if (cs != copies_.end()) {  // every copy is a body
      const copies::State& s = cs->second;
      const UsdPrim self = stage_->GetPrimAtPath(s.path);
      if (base.falls)
        for (UsdPrim p = self; p && !p.IsPseudoRoot(); p = p.GetParent())
          if (UsdGeomXformable(p) && UsdGeomXformable(p).TransformMightBeTimeVarying())
            throw Error("simulate: " + base.item + " moves (keys on it or on what holds it), so its copies can't fall: "
                        "remove those keys, or key the copies' source instead");
      GfMatrix4d world;
      const std::vector<copies::Copy> laid = copies::at_frame(stage_, s, setup.start, &world);
      GfVec3d w_origin;
      GfQuatd w_turn;
      frame_of(world, &w_origin, &w_turn);
      copies_out[base.item] = {world.GetInverse(), w_turn.GetInverse()};
      for (size_t c = 0; c < laid.size(); ++c) {
        sim::Body b = base;
        b.copy = int(c);
        if (b.falls) {  // Vary › Start and a pour: each copy falls a little later than the item's Falls from
          b.wake = std::min(b.wake + copies::start_delay(s.p, int(c), setup.fps), setup.end - setup.start + 1);
          b.appears = copies::streams(s.p);  // a stream: not there until it starts
          const GfVec3f leave = copies::start_velocity(s.p, int(c));  // a pour's: its own space, turned to the world's
          if (const float speed = leave.GetLength(); speed > 0) {
            const GfVec3d dir = world.TransformDir(GfVec3d(leave)).GetNormalized() * double(speed);
            for (int k = 0; k < 3; ++k) b.velocity[size_t(k)] += dir[k];
          }
        }
        const copies::Copy& cp = laid[c];
        GfMatrix4d inst = GfMatrix4d().SetScale(GfVec3d(cp.scale)) * GfMatrix4d().SetRotate(GfRotation(GfQuatd(cp.rot))) *
                          GfMatrix4d().SetTranslate(GfVec3d(cp.pos));
        const GfMatrix4d place = inst * world;
        GfVec3d origin;
        GfQuatd turn;
        frame_of(place, &origin, &turn);
        b.pos = v3(origin);
        const GfVec3d im = turn.GetImaginary();
        b.rot = {im[0], im[1], im[2], turn.GetReal()};
        const UsdPrim proto = self.GetChild(TfToken(s.sources[std::min<size_t>(size_t(cp.proto), s.sources.size() - 1)]));
        const auto to_world = [&](const UsdPrim& mesh) {
          bool reset = false;
          return xc.ComputeRelativeTransform(mesh, self, &reset) * place;
        };
        gather(proto, t, to_world, origin, turn, &b.points, b.falls || b.shape != sim::Body::Exact ? nullptr : &b.triangles);
        bodies.push_back(std::move(b));
      }
      continue;
    }
    const SdfPath path = item_path(stage_, base.item);
    const UsdPrim prim = path.IsEmpty() ? UsdPrim() : stage_->GetPrimAtPath(path);
    if (!prim) throw Error("simulate.bodies[" + std::to_string(i) + "].item: no item \"" + base.item + "\" in the scene");
    if (prim.GetParent().GetPath() != SdfPath("/World"))
      throw Error("simulate: " + base.item + " is inside " + prim.GetParent().GetName().GetString() +
                  "; only items at the top of the scene can simulate: take it out first");
    sim::Body b = base;
    GfVec3d origin;
    GfQuatd turn;
    frame_of(xc.GetLocalToWorldTransform(prim), &origin, &turn);
    b.pos = v3(origin);
    const GfVec3d im = turn.GetImaginary();
    b.rot = {im[0], im[1], im[2], turn.GetReal()};
    const auto to_world = [&](const UsdPrim& mesh) { return xc.GetLocalToWorldTransform(mesh); };
    gather(prim, t, to_world, origin, turn, &b.points, b.falls || b.shape != sim::Body::Exact ? nullptr : &b.triangles);
    bodies.push_back(std::move(b));
  }

  const bool tell = a.flag("progress", false);
  const sim::Result res = sim::run(setup, bodies, cloths, [&](int i, int of, int frame) {
    if (tell && progress)
      progress(JsObject{{"progress", JsValue(i)}, {"of", JsValue(of)}, {"frame", JsValue(frame)}});
  });

  // the rows: world for plain items, the copies item's own space for copies
  std::vector<float> data;
  data.reserve(res.frames.size() * res.rows.size() * 7);
  for (const auto& frame : res.frames)
    for (size_t j = 0; j < res.rows.size(); ++j) {
      const sim::Body& b = bodies[size_t(res.rows[j])];
      GfVec3d p(frame[j].pos[0], frame[j].pos[1], frame[j].pos[2]);
      GfQuatd q(frame[j].rot[3], GfVec3d(frame[j].rot[0], frame[j].rot[1], frame[j].rot[2]));
      if (b.copy >= 0) {
        const CopiesOut& c = copies_out.at(b.item);
        p = c.to_local.Transform(p);
        q = (c.turn_back * q).GetNormalized();
      }
      put(data, p, q);
    }
  const std::filesystem::path file = folder / "bodies.bin";
  {
    std::ofstream f(file, std::ios::binary);
    f.write(reinterpret_cast<const char*>(data.data()), std::streamsize(data.size() * sizeof(float)));
    if (!f) throw Error("simulate: could not write " + file.u8string());
  }
  JsArray cloth_out;
  for (size_t c = 0; c < cloths.size(); ++c) {
    const std::filesystem::path cf = folder / ("cloth_" + cloths[c].item + ".bin");
    write_cloth(cf, cloths[c], res.cloth[c], setup.start, int(res.frames.size()), cloth_local[c]);
    cloth_out.push_back(JsValue(JsObject{{"item", JsValue(cloths[c].item)}, {"file", JsValue(cf.u8string())},
                                         {"points", JsValue(int(cloths[c].points.size()))},
                                         {"triangles", JsValue(int(cloths[c].triangles.size()))},
                                         {"refined", JsValue(cloths[c].refined)}}));
  }
  JsArray rows;
  for (size_t j = 0; j < res.rows.size(); ++j) {
    const sim::Body& b = bodies[size_t(res.rows[j])];
    JsObject row{{"item", JsValue(b.item)}, {"copy", JsValue(b.copy)}, {"row", JsValue(int(j))}};
    if (b.appears && b.wake > 0) row["appear"] = JsValue(setup.start + b.wake);  // the shot frame it appears and falls
    rows.push_back(JsValue(row));
  }
  const auto r1 = [](double v) { return std::round(v * 10) / 10; };
  return JsObject{{"ok", JsValue(true)}, {"jolt", JsValue(sim::jolt_version())}, {"sim", JsValue(sim::kVersion)},
                  {"frames", JsValue(JsArray{JsValue(setup.start), JsValue(setup.end)})}, {"rows", JsValue(int(res.rows.size()))},
                  {"file", JsValue(file.u8string())}, {"bodies", JsValue(rows)}, {"cloth", JsValue(cloth_out)},
                  {"atRest", JsValue(res.atRest)},
                  {"ms", JsValue(r1(res.ms))}, {"frameMs", JsValue(std::round(res.frameMs * 100) / 100)}};
}

}  // namespace r3d
