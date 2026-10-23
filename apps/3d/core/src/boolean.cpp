// MeshData <-> Manifold. Each Manifold vertex carries 8 properties: x y z, nx ny nz, s t. MeshData's st is
// per corner, so one Manifold vertex is made per distinct (point, st) pair; Merge() then welds the vertices
// that share a position, which is what makes the split hard edges and UV seams one closed solid again.
#include "boolean.h"

#include <cmath>
#include <map>
#include <utility>

#include <manifold/manifold.h>

#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

constexpr int kProps = 8;

const char* reason(manifold::Manifold::Error e) {
  using E = manifold::Manifold::Error;
  switch (e) {
    case E::NonFiniteVertex: return "a point is not finite";
    case E::NotManifold: return "it has open edges or holes";
    case E::ResultTooLarge: return "it is too large";
    default: return "its mesh could not be read";
  }
}

std::string quoted(const std::vector<Solid>& solids, size_t from, size_t to) {
  std::vector<std::string> ids;
  for (size_t i = from; i < to; ++i) ids.push_back("'" + solids[i].id + "'");
  return join(ids);
}

manifold::Manifold to_manifold(const Solid& s, const std::string& where) {
  const MeshData& m = s.mesh;
  const GfMatrix4d normal_xf = s.xform.GetInverse().GetTranspose();
  manifold::MeshGL gl;
  gl.numProp = kProps;
  std::map<std::pair<int, std::pair<float, float>>, uint32_t> made;  // (point, st) -> Manifold vertex
  auto vertex = [&](size_t k) {
    const int i = m.indices[k];
    const auto key = std::make_pair(i, std::make_pair(m.st[k][0], m.st[k][1]));
    auto it = made.find(key);
    if (it != made.end()) return it->second;
    const GfVec3d p = s.xform.Transform(GfVec3d(m.points[i]));
    GfVec3d n = normal_xf.TransformDir(GfVec3d(m.normals[i]));
    n.Normalize();
    const float v[kProps] = {float(p[0]), float(p[1]), float(p[2]), float(n[0]), float(n[1]), float(n[2]),
                             m.st[k][0], m.st[k][1]};
    const uint32_t id = uint32_t(gl.vertProperties.size() / kProps);
    gl.vertProperties.insert(gl.vertProperties.end(), v, v + kProps);
    made.emplace(key, id);
    return id;
  };
  size_t k = 0;
  for (int c : m.counts) {  // faces are convex: a fan from the first corner
    for (int j = 1; j + 1 < c; ++j)
      for (size_t corner : {k, k + size_t(j), k + size_t(j) + 1}) gl.triVerts.push_back(vertex(corner));
    k += size_t(c);
  }
  gl.Merge();
  manifold::Manifold out(gl);
  const bool bad = out.Status() != manifold::Manifold::Error::NoError;
  if (bad || out.IsEmpty())
    fail(where, "'" + s.id + "' is not a closed solid (" + (bad ? reason(out.Status()) : "it has no volume") +
                    "), so it can't be combined",
         "closed shapes as inputs: box, sphere, cylinder, torus, text or svg with depth > 0, or another combine "
         "(a plane or disc is a surface, not a solid)");
  return out;
}

// Cut faces carry the cutter's outward normals, which point into the result: flip each vertex whose
// normal disagrees with the faces around it.
MeshData from_manifold(const manifold::Manifold& solid) {
  const manifold::MeshGL gl = solid.GetMeshGL();
  const size_t np = gl.numProp, nv = gl.NumVert();
  MeshData m;
  m.points.resize(nv);
  m.normals.resize(nv);
  for (size_t v = 0; v < nv; ++v) {
    const float* p = &gl.vertProperties[v * np];
    m.points[v] = GfVec3f(p[0], p[1], p[2]);
    m.normals[v] = np >= 6 ? GfVec3f(p[3], p[4], p[5]) : GfVec3f(0.0f);
  }
  std::vector<float> agree(nv, 0.0f);
  for (size_t t = 0; t < gl.NumTri(); ++t) {
    const uint32_t a = gl.triVerts[3 * t], b = gl.triVerts[3 * t + 1], c = gl.triVerts[3 * t + 2];
    GfVec3f face = GfCross(m.points[b] - m.points[a], m.points[c] - m.points[a]);
    face.Normalize();
    for (uint32_t v : {a, b, c}) {
      agree[v] += GfDot(m.normals[v], face);
      m.indices.push_back(int(v));
      const float* p = &gl.vertProperties[v * np];
      m.st.push_back(np >= 8 ? GfVec2f(p[6], p[7]) : GfVec2f(0.0f));
    }
    m.counts.push_back(3);
  }
  for (size_t v = 0; v < nv; ++v) {
    if (agree[v] < 0.0f) m.normals[v] = -m.normals[v];
    m.normals[v].Normalize();
  }
  return m;
}

}  // namespace

MeshData combine_solids(const std::vector<Solid>& solids, CombineOp op, const std::string& where) {
  if (solids.size() < 2) fail(where, std::to_string(solids.size()) + " inputs", "2 or more children");
  std::vector<manifold::Manifold> all;
  for (const Solid& s : solids) all.push_back(to_manifold(s, where));
  using manifold::OpType;
  manifold::Manifold out;
  if (op == CombineOp::Union) out = manifold::Manifold::BatchBoolean(all, OpType::Add);
  if (op == CombineOp::Intersect) out = manifold::Manifold::BatchBoolean(all, OpType::Intersect);
  if (op == CombineOp::Subtract)
    out = all[0] - manifold::Manifold::BatchBoolean(std::vector<manifold::Manifold>(all.begin() + 1, all.end()),
                                                    OpType::Add);
  if (out.Status() != manifold::Manifold::Error::NoError)
    fail(where, std::string("the combine failed (") + reason(out.Status()) + ")", "closed solids that Manifold can join");
  if (out.IsEmpty()) {
    const std::string first = "'" + solids[0].id + "'";
    if (op == CombineOp::Subtract)
      fail(where, "Subtract gave an empty shape: " + quoted(solids, 1, solids.size()) + " cover " + first + " entirely",
           "cutters that leave part of the first child");
    if (op == CombineOp::Intersect)
      fail(where, "Intersect gave an empty shape: " +
                      (solids.size() == 2 ? first + " and '" + solids[1].id + "' don't overlap"
                                          : quoted(solids, 0, solids.size()) + " don't all overlap"),
           "children that share some volume");
    fail(where, "Union gave an empty shape", "closed solids with volume");
  }
  return from_manifold(out);
}

}  // namespace r3d
