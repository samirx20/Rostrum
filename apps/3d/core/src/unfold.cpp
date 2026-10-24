#include "unfold.h"

#include <algorithm>
#include <memory>

#include <xatlas.h>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

using AtlasPtr = std::unique_ptr<xatlas::Atlas, void (*)(xatlas::Atlas*)>;

const char* add_error(xatlas::AddMeshError e) {
  switch (e) {
    case xatlas::AddMeshError::IndexOutOfRange: return "a face names a point the mesh doesn't have";
    case xatlas::AddMeshError::InvalidFaceVertexCount: return "a face has fewer than 3 corners";
    case xatlas::AddMeshError::InvalidIndexCount: return "the face corners don't add up";
    default: return "xatlas couldn't read the mesh";
  }
}

}  // namespace

Unfolded unfold_mesh(const VtArray<GfVec3f>& points, const VtArray<int>& counts, const VtArray<int>& indices, int size,
                     const std::string& where) {
  if (size < 64 || size > 16384) throw Error(where + ".size: " + std::to_string(size) + " is out of range. Accepted: 64..16384");
  if (counts.empty()) throw Error(where + ": the mesh has no faces to unfold");
  std::vector<uint8_t> corners(counts.size());
  size_t total = 0;
  for (size_t f = 0; f < counts.size(); ++f) {
    if (counts[f] < 3 || counts[f] > 255)
      throw Error(where + ": face " + std::to_string(f) + " has " + std::to_string(counts[f]) +
                  " corners. Accepted: 3..255 corners per face (split the face first)");
    corners[f] = uint8_t(counts[f]);
    total += size_t(counts[f]);
  }
  if (total != indices.size())
    throw Error(where + ": the faces have " + std::to_string(total) + " corners but the mesh lists " +
                std::to_string(indices.size()));

  xatlas::MeshDecl decl;
  decl.vertexPositionData = points.cdata();
  decl.vertexPositionStride = sizeof(GfVec3f);
  decl.vertexCount = uint32_t(points.size());
  decl.indexData = indices.cdata();
  decl.indexFormat = xatlas::IndexFormat::UInt32;
  decl.indexCount = uint32_t(indices.size());
  decl.faceVertexCount = corners.data();
  decl.faceCount = uint32_t(counts.size());
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
    if (out.indexCount != indices.size())
      throw Error(where + ": xatlas gave " + std::to_string(out.indexCount) + " face corners back for " +
                  std::to_string(indices.size()));
    Unfolded r;
    r.st.resize(indices.size());
    const float w = float(atlas->width), h = float(atlas->height);
    for (uint32_t k = 0; k < out.indexCount; ++k) {
      const xatlas::Vertex& v = out.vertexArray[out.indexArray[k]];
      r.st[k] = GfVec2f(v.uv[0] / w, 1.0f - v.uv[1] / h);  // xatlas counts rows down; st's t counts up
    }
    r.charts = int(atlas->chartCount);
    r.used = atlas->utilization ? atlas->utilization[0] : 0.0f;
    return r;
  }
  throw Error(where + ": the mesh's pieces don't fit one " + std::to_string(size) + " px picture");
}

}  // namespace r3d
