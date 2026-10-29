#include "unfold.h"

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
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

// The scale given to xatlas. It drops every triangle of area <= FLT_EPSILON (1.2e-7) as degenerate, leaving it no
// place in the picture (uv 0, 0); in metres that is a triangle of ~0.5 mm sides, so a fine clay lost over half its
// surface (a stamp there showed as scattered texels). The layout doesn't depend on the scale (xatlas sizes the
// picture by itself), so a surface whose triangles are smaller on average than kMeanArea is given scaled up to it;
// only true slivers stay below the epsilon. Never scaled down (a normal mesh is laid out exactly as before).
// ROSTRUM3D_UNFOLD_MEAN (m^2) overrides kMeanArea, to measure.
constexpr double kMeanArea = 1e-4;
constexpr double kChartTris = 600;   // a clay chart's most triangles (by area: unfold_triangles)
constexpr double kRegionTris = 4000; // about how many triangles a clay region holds (unfold_triangles)
float scale_for(double area, size_t ntris) {
  const char* v = std::getenv("ROSTRUM3D_UNFOLD_MEAN");
  const double want = v ? std::atof(v) : kMeanArea;
  return area > 0 && ntris ? float(std::max(1.0, std::sqrt(want / (area / double(ntris))))) : 1.0f;
}

float unit_scale(const float* points, size_t stride, const uint32_t* tris, size_t ntris, double* area_out = nullptr) {
  double area = 0;
  for (size_t t = 0; t < ntris; ++t) {
    const float* p[3] = {points + stride * tris[3 * t], points + stride * tris[3 * t + 1], points + stride * tris[3 * t + 2]};
    const double u[3] = {p[1][0] - p[0][0], p[1][1] - p[0][1], p[1][2] - p[0][2]};
    const double v[3] = {p[2][0] - p[0][0], p[2][1] - p[0][1], p[2][2] - p[0][2]};
    const double c[3] = {u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]};
    area += 0.5 * std::sqrt(c[0] * c[0] + c[1] * c[1] + c[2] * c[2]);
  }
  if (area_out) *area_out = area;
  return scale_for(area, ntris);
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

// Meshes laid out together in one square picture of `size` px: their charts (flat pieces) made once (xatlas works on
// separate meshes in parallel), then packed, again at a smaller texel scale while the pieces spill into a second
// picture. `fast` (the clay's big, smooth surfaces): no chart grows past `max_area` (m^2; xatlas's slow solve is for
// big curved charts, small ones lay flat as they are), and pieces sit on 4-pixel steps (fewer places to try packing).
AtlasPtr atlas_many(const std::vector<xatlas::MeshDecl>& decls, int size, bool fast, float max_area,
                    const std::string& where) {
  if (size < 64 || size > 16384) throw Error(where + ".size: " + std::to_string(size) + " is out of range. Accepted: 64..16384");
  AtlasPtr atlas(xatlas::Create(), xatlas::Destroy);
  for (const xatlas::MeshDecl& decl : decls) {
    const xatlas::AddMeshError e = xatlas::AddMesh(atlas.get(), decl, uint32_t(decls.size()));
    if (e != xatlas::AddMeshError::Success) throw Error(where + ": " + add_error(e));
  }
  uint32_t tris = 0;
  for (const xatlas::MeshDecl& decl : decls) tris += decl.indexCount / 3;
  xatlas::ChartOptions chart;
  // measuring knobs (3d-cl4): ROSTRUM3D_UNFOLD_COST (maxCost), ROSTRUM3D_UNFOLD_AREA (maxChartArea, m^2 as given to xatlas: scale_for)
  auto knob = [](const char* name, float dflt) { const char* v = std::getenv(name); return v ? float(std::atof(v)) : dflt; };
  if (fast) {
    chart.maxCost = knob("ROSTRUM3D_UNFOLD_COST", 2.0f);
    chart.maxChartArea = knob("ROSTRUM3D_UNFOLD_AREA", max_area);
  }
  using clock = std::chrono::steady_clock;
  const auto t0 = clock::now();
  xatlas::ComputeCharts(atlas.get(), chart);
  const auto t1 = clock::now();
  const bool profile = std::getenv("ROSTRUM3D_CLAY_PROFILE") != nullptr;
  auto ms = [](auto a, auto b) { return std::chrono::duration<double, std::milli>(b - a).count(); };
  if (profile) {
    std::fprintf(stderr, "unfold computed charts=%u tris=%u meshes=%zu chartsMs=%.1f\n", atlas->chartCount, tris,
                 decls.size(), ms(t0, t1));
    std::fflush(stderr);
  }
  xatlas::PackOptions pack;
  pack.resolution = uint32_t(size);
  pack.padding = uint32_t(std::clamp(size / 256, 2, 16));
  pack.bilinear = true;
  pack.blockAlign = fast;
  float texels = 0.0f;
  for (int attempt = 0; attempt < 6; ++attempt) {
    pack.texelsPerUnit = texels;
    xatlas::PackCharts(atlas.get(), pack);
    if (profile) {
      std::fprintf(stderr, "unfold pack %d atlases=%u texelsPerUnit=%g ms=%.1f\n", attempt + 1, atlas->atlasCount,
                   atlas->texelsPerUnit, ms(t1, clock::now()));
      std::fflush(stderr);
    }
    if (atlas->meshCount != decls.size() || atlas->width == 0 || atlas->height == 0)
      throw Error(where + ": xatlas made no picture for the mesh");
    if (atlas->atlasCount <= 1) {
      if (profile)
        std::fprintf(stderr, "unfold charts=%u tris=%u meshes=%zu cost=%.2f area=%g chartsMs=%.1f packMs=%.1f packs=%d\n",
                     atlas->chartCount, tris, decls.size(), chart.maxCost, chart.maxChartArea, ms(t0, t1),
                     ms(t1, clock::now()), attempt + 1);
      return atlas;
    }
    texels = atlas->texelsPerUnit * 0.85f;
  }
  throw Error(where + ": the mesh's pieces don't fit one " + std::to_string(size) + " px picture");
}

AtlasPtr atlas_one(const xatlas::MeshDecl& decl, int size, const std::string& where) {
  return atlas_many({decl}, size, false, 0.0f, where);
}

}  // namespace

Unfolded unfold_mesh(const VtArray<GfVec3f>& points, const VtArray<int>& counts, const VtArray<int>& indices, int size,
                     const std::string& where) {
  if (size < 64 || size > 16384) throw Error(where + ".size: " + std::to_string(size) + " is out of range. Accepted: 64..16384");
  if (counts.empty()) throw Error(where + ": the mesh has no faces to unfold");
  const Fan t = fan(counts, indices, points.size(), where);
  const float k = unit_scale(reinterpret_cast<const float*>(points.cdata()), 3, t.points.data(), t.points.size() / 3);
  std::vector<GfVec3f> scaled(points.begin(), points.end());
  for (GfVec3f& p : scaled) p *= k;

  xatlas::MeshDecl decl;
  decl.vertexPositionData = scaled.data();
  decl.vertexPositionStride = sizeof(GfVec3f);
  decl.vertexCount = uint32_t(points.size());
  decl.indexData = t.points.data();
  decl.indexFormat = xatlas::IndexFormat::UInt32;
  decl.indexCount = uint32_t(t.points.size());   // triangles only: no faceVertexCount (see the top of this file)
  decl.epsilon = 1e-6f * k;  // the core's shapes split points at hard edges; xatlas joins them back by position

  const AtlasPtr atlas = atlas_one(decl, size, where);
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

UnfoldedTris unfold_triangles(const float* points, size_t npoints, const int32_t* tris, size_t ntris, int size,
                              const std::string& where) {
  if (ntris == 0) throw Error(where + ": the surface has no triangles to unfold");
  if (npoints > UINT32_MAX || 3 * ntris > UINT32_MAX) throw Error(where + ": the surface is too big to unfold");
  // Regions: the surface cut by a grid of cubes by triangle middle, each region a mesh of its own with its own points,
  // so xatlas charts them in parallel; a region's edge is a seam, like a chart's. A cube holds about kRegionTris
  // triangles (its side the square root of that many triangles' area): xatlas's chart merging costs about the cube of
  // the charts in one connected piece, so a million-triangle clay cut 3 × 3 × 3 took over 10 minutes.
  for (size_t t = 0; t < 3 * ntris; ++t)
    if (tris[t] < 0 || size_t(tris[t]) >= npoints) throw Error(where + ": triangle " + std::to_string(t / 3) + " names a missing point");
  float lo[3] = {FLT_MAX, FLT_MAX, FLT_MAX}, hi[3] = {-FLT_MAX, -FLT_MAX, -FLT_MAX};
  for (size_t i = 0; i < npoints; ++i)
    for (int a = 0; a < 3; ++a) lo[a] = std::min(lo[a], points[3 * i + a]), hi[a] = std::max(hi[a], points[3 * i + a]);
  const uint32_t* corners = reinterpret_cast<const uint32_t*>(tris);
  double area = 0;
  const float scale = unit_scale(points, 3, corners, ntris, &area);
  const float extent = std::max({hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 1e-6f});
  const float cell = std::max(float(std::sqrt(area / double(ntris) * kRegionTris)), extent / 1e6f);
  std::map<uint64_t, std::vector<uint32_t>> regions;      // cell -> its triangles, in order
  for (size_t t = 0; t < ntris; ++t) {
    const float* p[3] = {points + 3 * tris[3 * t], points + 3 * tris[3 * t + 1], points + 3 * tris[3 * t + 2]};
    uint64_t key = 0;
    for (int a = 0; a < 3; ++a)
      key = (key << 21) | uint64_t(std::clamp(int(((p[0][a] + p[1][a] + p[2][a]) / 3 - lo[a]) / cell), 0, (1 << 21) - 1));
    regions[key].push_back(uint32_t(t));
  }
  struct Region { std::vector<float> pts; std::vector<uint32_t> idx; const std::vector<uint32_t>* tris; };
  std::vector<Region> parts;
  std::vector<xatlas::MeshDecl> decls;
  parts.reserve(regions.size());
  for (const auto& [key, list] : regions) {
    Region r{{}, {}, &list};
    std::map<int32_t, uint32_t> local;
    for (const uint32_t t : list)
      for (int k = 0; k < 3; ++k) {
        const int32_t g = tris[3 * t + k];
        auto [it, made] = local.emplace(g, uint32_t(r.pts.size() / 3));
        if (made)
          for (int c = 0; c < 3; ++c) r.pts.push_back(points[3 * g + c] * scale);
        r.idx.push_back(it->second);
      }
    parts.push_back(std::move(r));
  }
  for (const Region& r : parts) {
    xatlas::MeshDecl decl;
    decl.vertexPositionData = r.pts.data();
    decl.vertexPositionStride = 3 * sizeof(float);
    decl.vertexCount = uint32_t(r.pts.size() / 3);
    decl.indexData = r.idx.data();
    decl.indexFormat = xatlas::IndexFormat::UInt32;
    decl.indexCount = uint32_t(r.idx.size());
    decls.push_back(decl);
  }
  // charts of at most about kChartTris triangles: xatlas's slow solve is for big charts (measured on a 109k-triangle
  // clay, a cap of 1/200 of the surface: 30 s -> 2.6 s in one mesh). A cap by area share grew with the clay: a
  // million-triangle clay, every triangle charted, took over 10 minutes.
  const AtlasPtr atlas = atlas_many(decls, size, true, float(area * scale * scale / double(ntris) * kChartTris), where);
  const float w = float(atlas->width), h = float(atlas->height);
  UnfoldedTris r;
  r.st.resize(6 * ntris);
  for (size_t m = 0; m < parts.size(); ++m) {
    const xatlas::Mesh& out = atlas->meshes[m];
    const std::vector<uint32_t>& list = *parts[m].tris;
    if (out.indexCount != 3 * list.size())
      throw Error(where + ": xatlas gave " + std::to_string(out.indexCount) + " triangle corners back for " +
                  std::to_string(3 * list.size()));
    for (size_t j = 0; j < list.size(); ++j)
      for (int k = 0; k < 3; ++k) {  // corner k of the region's triangle j is corner k of surface triangle list[j]
        const xatlas::Vertex& v = out.vertexArray[out.indexArray[3 * j + k]];
        r.st[6 * size_t(list[j]) + 2 * k] = v.uv[0] / w;
        r.st[6 * size_t(list[j]) + 2 * k + 1] = 1.0f - v.uv[1] / h;  // t counts up
      }
  }
  r.charts = int(atlas->chartCount);
  r.used = atlas->utilization ? atlas->utilization[0] : 0.0f;
  return r;
}

}  // namespace r3d
