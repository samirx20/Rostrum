#include "unfold.h"

#include <algorithm>
#include <map>
#include <memory>

#include <xatlas.h>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

// How a face's corners get their (s, t). xatlas is given triangles, never polygons: its polygon input reads face f's
// corners at f × (that face's corner count), so a mesh mixing quads, triangles and a 64-sided cap is read wrongly
// (seen: 4724 corners back for 4480). Each face is cut into a fan (corner 0, i, i + 1); for triangles xatlas answers
// per triangle corner in the order given. A face's triangles normally share one chart (flat piece): each face takes
// the chart most of its triangles landed in, and each of its corners the output vertex of that chart made from the
// corner's point (`xref`). A corner that chart doesn't hold (the face was cut between charts) takes its own
// triangle's answer, and the face is counted (`split`), never hidden.

namespace r3d {
namespace {

using AtlasPtr = std::unique_ptr<xatlas::Atlas, void (*)(xatlas::Atlas*)>;

const char* add_error(xatlas::AddMeshError e) {
  switch (e) {
    case xatlas::AddMeshError::IndexOutOfRange: return "a face names a point the mesh doesn't have";
    case xatlas::AddMeshError::InvalidIndexCount: return "the triangle corners don't add up";
    default: return "xatlas couldn't read the mesh";
  }
}

struct Fan {
  std::vector<uint32_t> points;   // 3 per triangle: the mesh's point indices
  std::vector<uint32_t> corner;   // 3 per triangle: the face corner (index into the mesh's face indices) each came from
  std::vector<uint32_t> face;     // 1 per triangle: the face it is part of
};

Fan fan(const VtArray<int>& counts, const VtArray<int>& indices, size_t npoints, const std::string& where) {
  Fan t;
  size_t first = 0;
  for (size_t f = 0; f < counts.size(); first += size_t(counts[f]), ++f) {
    const std::string face = where + ": face " + std::to_string(f);
    if (counts[f] < 3) throw Error(face + " has fewer than 3 corners");
    if (first + size_t(counts[f]) > indices.size()) throw Error(where + ": the faces have more corners than the mesh lists");
    for (int i = 1; i + 1 < counts[f]; ++i) {
      for (const size_t c : {first, first + size_t(i), first + size_t(i) + 1}) {
        if (indices[c] < 0 || size_t(indices[c]) >= npoints)
          throw Error(face + " names point " + std::to_string(indices[c]) + ", which the mesh doesn't have");
        t.points.push_back(uint32_t(indices[c]));
        t.corner.push_back(uint32_t(c));
      }
      t.face.push_back(uint32_t(f));
    }
  }
  if (first != indices.size())
    throw Error(where + ": the faces have " + std::to_string(first) + " corners but the mesh lists " + std::to_string(indices.size()));
  return t;
}

// The (s, t) of every face corner from xatlas's per-triangle answer (the method at the top).
std::vector<GfVec2f> per_corner(const xatlas::Mesh& out, const Fan& t, size_t faces, size_t corners, float w, float h,
                                int* split) {
  auto st = [&](const xatlas::Vertex& v) { return GfVec2f(v.uv[0] / w, 1.0f - v.uv[1] / h); };  // t counts up
  const size_t tris = t.face.size();
  std::vector<std::map<int32_t, int>> votes(faces);       // face -> chart -> its triangles there (charted ones only)
  for (size_t k = 0; k < tris; ++k) {
    const int32_t c = out.vertexArray[out.indexArray[3 * k]].chartIndex;
    if (c >= 0) ++votes[t.face[k]][c];
  }
  std::vector<int32_t> chart(faces, -1);                  // -1: every triangle of the face too thin to chart
  for (size_t f = 0; f < faces; ++f)
    if (!votes[f].empty())
      chart[f] = std::max_element(votes[f].begin(), votes[f].end(),
                                  [](const auto& a, const auto& b) { return a.second < b.second; })->first;
  std::map<std::pair<int32_t, uint32_t>, uint32_t> made;  // (chart, input point) -> output vertex
  for (uint32_t v = 0; v < out.vertexCount; ++v)
    made.emplace(std::make_pair(out.vertexArray[v].chartIndex, out.vertexArray[v].xref), v);
  std::vector<GfVec2f> r(corners, GfVec2f(0, 0));
  std::vector<char> how(corners, 0);                      // 0 not yet, 1 its own triangle's chart, 2 the face's chart
  for (size_t k = 0; k < 3 * tris; ++k) {
    const uint32_t f = t.face[k / 3], c = t.corner[k];
    if (how[c] == 2) continue;
    const auto it = made.find({chart[f], t.points[k]});
    if (it != made.end()) {
      r[c] = st(out.vertexArray[it->second]);
      how[c] = 2;
    } else if (how[c] == 0) {
      r[c] = st(out.vertexArray[out.indexArray[k]]);
      how[c] = 1;
    }
  }
  std::vector<char> cut(faces, 0);
  for (size_t k = 0; k < 3 * tris; ++k)
    if (how[t.corner[k]] == 1) cut[t.face[k / 3]] = 1;
  *split = int(std::count(cut.begin(), cut.end(), char(1)));
  return r;
}

}  // namespace

Unfolded unfold_mesh(const VtArray<GfVec3f>& points, const VtArray<int>& counts, const VtArray<int>& indices, int size,
                     const std::string& where) {
  if (size < 64 || size > 16384) throw Error(where + ".size: " + std::to_string(size) + " is out of range. Accepted: 64..16384");
  if (counts.empty()) throw Error(where + ": the mesh has no faces to unfold");
  const Fan t = fan(counts, indices, points.size(), where);

  xatlas::MeshDecl decl;
  decl.vertexPositionData = points.cdata();
  decl.vertexPositionStride = sizeof(GfVec3f);
  decl.vertexCount = uint32_t(points.size());
  decl.indexData = t.points.data();
  decl.indexFormat = xatlas::IndexFormat::UInt32;
  decl.indexCount = uint32_t(t.points.size());   // triangles only: no faceVertexCount (see the top of this file)
  decl.epsilon = 1e-6f;  // the core's shapes split points at hard edges; xatlas joins them back by position

  xatlas::PackOptions pack;
  pack.resolution = uint32_t(size);
  pack.padding = uint32_t(std::clamp(size / 256, 2, 16));
  pack.bilinear = true;
  // Pieces that don't fit one picture spill into a second: shrink the texel scale until all fit in one.
  float texels = 0.0f;
  for (int attempt = 0; attempt < 6; ++attempt) {
    AtlasPtr atlas(xatlas::Create(), xatlas::Destroy);
    const xatlas::AddMeshError e = xatlas::AddMesh(atlas.get(), decl);
    if (e != xatlas::AddMeshError::Success) throw Error(where + ": " + add_error(e));
    pack.texelsPerUnit = texels;
    xatlas::Generate(atlas.get(), xatlas::ChartOptions(), pack);
    if (atlas->meshCount != 1 || atlas->width == 0 || atlas->height == 0)
      throw Error(where + ": xatlas made no picture for the mesh");
    if (atlas->atlasCount > 1) {
      texels = atlas->texelsPerUnit * 0.85f;
      continue;
    }
    const xatlas::Mesh& out = atlas->meshes[0];
    if (out.indexCount != t.points.size())
      throw Error(where + ": xatlas gave " + std::to_string(out.indexCount) + " triangle corners back for " +
                  std::to_string(t.points.size()));
    Unfolded r;
    r.st = per_corner(out, t, counts.size(), indices.size(), float(atlas->width), float(atlas->height), &r.split);
    r.charts = int(atlas->chartCount);
    r.used = atlas->utilization ? atlas->utilization[0] : 0.0f;
    return r;
  }
  throw Error(where + ": the mesh's pieces don't fit one " + std::to_string(size) + " px picture");
}

}  // namespace r3d
