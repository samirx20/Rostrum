#include "cloth_stage.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <vector>

#include <pxr/usd/usdGeom/primvarsAPI.h>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {

VtVec3fArray normals_of(const VtVec3fArray& p, const std::vector<int32_t>& tris) {
  VtVec3fArray n(p.size(), GfVec3f(0));
  for (size_t t = 0; t + 2 < tris.size(); t += 3) {
    const GfVec3f &a = p[size_t(tris[t])], &b = p[size_t(tris[t + 1])], &c = p[size_t(tris[t + 2])];
    const GfVec3f face = GfCross(b - a, c - a);  // area-weighted
    for (size_t k = 0; k < 3; ++k) n[size_t(tris[t + k])] += face;
  }
  for (GfVec3f& v : n) {
    const float len = v.GetLength();
    v = len > 1e-20f ? v / len : GfVec3f(0, 1, 0);
  }
  return n;
}

}  // namespace

void cloth_mesh(Item& it, UsdGeomMesh m, const JsObject& o) {
  const std::string where = it.id + ".cloth";
  Reader r(o, where);
  const std::string file = r.str("file");
  const int start = int(r.num("start")), end = int(r.num("end"));
  const int step = r.count("step", 1, 3), smooth = r.count("smooth", 1, 100);
  r.finish();
  if (end < start) fail(where, "end is before start", "start <= end");
  const std::string again = "the stored simulation's cloth file (simulate again)";

  std::ifstream f(std::filesystem::u8path(file), std::ios::binary | std::ios::ate);
  if (!f) fail(where + ".file", "no file " + file, again);
  const size_t bytes = size_t(f.tellg());
  f.seekg(0);
  char magic[4] = {};
  int32_t head[4] = {};
  f.read(magic, 4);
  f.read(reinterpret_cast<char*>(head), sizeof head);
  const int64_t points = head[0], tris = head[1], frames = head[2];
  if (!f || std::memcmp(magic, "RCL1", 4) != 0 || points <= 0 || tris <= 0 || frames != end - start + 1 || head[3] != start)
    fail(where + ".file", file + " is not the cloth of frames " + std::to_string(start) + ".." + std::to_string(end), again);
  const size_t want = 20 + size_t(tris) * 12 + size_t(points) * 8 + size_t(points) * size_t(frames) * 12;
  if (bytes != want)
    fail(where + ".file", file + " holds " + std::to_string(bytes) + " bytes, not " + std::to_string(want), again);
  std::vector<int32_t> index(size_t(tris) * 3);
  std::vector<float> st(size_t(points) * 2), pos(size_t(points) * size_t(frames) * 3);
  f.read(reinterpret_cast<char*>(index.data()), std::streamsize(index.size() * 4));
  f.read(reinterpret_cast<char*>(st.data()), std::streamsize(st.size() * 4));
  f.read(reinterpret_cast<char*>(pos.data()), std::streamsize(pos.size() * 4));
  if (!f) fail(where + ".file", "could not read " + file, again);
  for (int32_t i : index)
    if (i < 0 || i >= points) fail(where + ".file", file + " has a face with point " + std::to_string(i), again);

  // the faces and u v it was simulated with
  m.GetFaceVertexCountsAttr().Set(VtIntArray(size_t(tris), 3));
  m.GetFaceVertexIndicesAttr().Set(VtIntArray(index.begin(), index.end()));
  VtVec2fArray corners(index.size());
  for (size_t k = 0; k < index.size(); ++k) corners[k] = GfVec2f(st[size_t(index[k]) * 2], st[size_t(index[k]) * 2 + 1]);
  UsdGeomPrimvarsAPI(m.GetPrim())
      .CreatePrimvar(TfToken("st"), SdfValueTypeNames->TexCoord2fArray, UsdGeomTokens->faceVarying)
      .Set(corners);
  m.CreateDoubleSidedAttr().Set(true);

  // its points at each frame of the shot
  const int last = end - start;
  const auto frame_points = [&](int k, float t, int k2) {
    VtVec3fArray p(static_cast<size_t>(points));
    const float* a = &pos[size_t(k) * size_t(points) * 3];
    const float* b = &pos[size_t(k2) * size_t(points) * 3];
    for (size_t i = 0; i < p.size(); ++i)
      p[i] = GfVec3f(a[3 * i] + (b[3 * i] - a[3 * i]) * t, a[3 * i + 1] + (b[3 * i + 1] - a[3 * i + 1]) * t,
                     a[3 * i + 2] + (b[3 * i + 2] - a[3 * i + 2]) * t);
    return p;
  };
  const UsdAttribute pts = m.GetPointsAttr(), nrm = m.GetNormalsAttr(), ext = m.CreateExtentAttr();
  for (int fr = it.ctx.start; fr <= it.ctx.end; ++fr) {
    const int held = it.ctx.start + (fr - it.ctx.start) / step * step;  // On 2s / On 3s, from the shot's start
    const int i = std::clamp(held - start, 0, last);
    const int a = i / smooth * smooth, b = std::min(a + smooth, last);  // Simplify: every nth frame, blended between
    const VtVec3fArray p = b == a || i == a ? frame_points(a, 0, a) : frame_points(a, float(i - a) / float(b - a), b);
    const VtVec3fArray n = normals_of(p, index);
    VtVec3fArray box;
    UsdGeomPointBased::ComputeExtent(p, &box);
    if (fr == it.ctx.start) {  // the plain value too: anything reading without a time sees the cloth, not the flat plane
      pts.Set(p);
      nrm.Set(n);
      ext.Set(box);
    }
    if (it.ctx.end == it.ctx.start) break;
    pts.Set(p, UsdTimeCode(fr));
    nrm.Set(n, UsdTimeCode(fr));
    ext.Set(box, UsdTimeCode(fr));
  }
}

}  // namespace r3d
