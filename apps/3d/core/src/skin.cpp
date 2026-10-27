#include "skin.h"

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include <pxr/base/gf/matrix3d.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/usd/usdSkel/utils.h>

#include "json_read.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {
namespace {

std::vector<double> numbers(const JsValue& v, size_t n, const std::string& where, const char* accepted) {
  if (!v.IsArray() || v.GetJsArray().size() != n) fail(where, "is not " + std::to_string(n) + " numbers", accepted);
  std::vector<double> out;
  for (const JsValue& x : v.GetJsArray()) {
    if (!is_number(x) || !std::isfinite(to_number(x))) fail(where, "holds something that is not a number", accepted);
    out.push_back(to_number(x));
  }
  return out;
}

double segment_distance(const GfVec3d& p, const GfVec3d& a, const GfVec3d& b) {
  const GfVec3d ab = b - a;
  const double len2 = GfDot(ab, ab);
  const double s = len2 > 0 ? std::clamp(GfDot(p - a, ab) / len2, 0.0, 1.0) : 0.0;
  return (p - (a + ab * s)).GetLength();
}

// [m00..m22, tx,ty,tz] (column vectors: p' = M·p + t) as USD's row-vector matrix.
GfMatrix4d as_usd(const BoneMove& v) {
  GfMatrix4d g(1.0);
  for (int r = 0; r < 3; ++r)
    for (int c = 0; c < 3; ++c) g[r][c] = v[c * 3 + r];
  g[3][0] = v[9], g[3][1] = v[10], g[3][2] = v[11];
  return g;
}

SkinParts read_parts(const JsObject& o, size_t bones, const std::string& where) {
  Reader s(o, where);
  SkinParts p;
  const std::vector<double> origin = numbers(s.get("origin", "[x, y, z]"), 3, s.at("origin"), "[x, y, z]");
  std::copy(origin.begin(), origin.end(), p.origin.begin());
  p.cell = s.num_min("cell", 0, false);
  const std::vector<double> dims = numbers(s.get("dims", "[nx, ny, nz]"), 3, s.at("dims"), "[nx, ny, nz]");
  size_t total = 1;
  for (int i = 0; i < 3; ++i) {
    if (dims[i] < 1 || dims[i] > 1024 || dims[i] != std::floor(dims[i]))
      fail(s.at("dims"), "is not three whole numbers 1..1024", "[nx, ny, nz]");
    p.dims[i] = int(dims[i]);
    total *= size_t(p.dims[i]);
  }
  const JsArray& runs = s.list("cells");
  if (runs.size() % 2) fail(s.at("cells"), "has an odd count", "[value, count, value, count, …]");
  p.cells.reserve(total);
  for (size_t i = 0; i < runs.size(); i += 2) {
    if (!is_number(runs[i]) || !is_number(runs[i + 1]))
      fail(s.at("cells"), "holds something that is not a number", "whole numbers");
    const double v = to_number(runs[i]), n = to_number(runs[i + 1]);
    if (v < 0 || v > 255 || n < 1 || double(p.cells.size()) + n > double(total))
      fail(s.at("cells"), "has a run out of range", "value 0..255, counts adding up to nx × ny × nz");
    p.cells.insert(p.cells.end(), size_t(n), static_cast<unsigned char>(v));
  }
  if (p.cells.size() != total) fail(s.at("cells"), "does not cover the grid", "counts adding up to nx × ny × nz");
  const JsArray& jpieces = s.list("pieces");
  if (jpieces.empty()) fail(s.at("pieces"), "is empty", "one {from, first, blend} per piece, the body first");
  for (size_t i = 0; i < jpieces.size(); ++i) {
    const std::string at = s.at("pieces") + "[" + std::to_string(i) + "]";
    if (!jpieces[i].IsObject()) fail(at, "is not an object", "{from, first, blend}");
    Reader r(jpieces[i].GetJsObject(), at);
    SkinParts::Piece pc;
    pc.from = r.count("from", -1, int(bones) - 1);
    pc.first = r.count("first", -1, int(bones) - 1);
    pc.blend = r.num_min("blend", 0, true);
    r.finish();
    p.pieces.push_back(pc);
  }
  const JsArray& jbone = s.list("bone");
  if (jbone.size() != bones) fail(s.at("bone"), "does not hold one piece per bone", std::to_string(bones) + " numbers");
  for (const JsValue& v : jbone) {
    if (!is_number(v) || to_number(v) < 0 || to_number(v) >= double(p.pieces.size()))
      fail(s.at("bone"), "names a piece that isn't there", "0.." + std::to_string(p.pieces.size() - 1));
    p.bone.push_back(int(to_number(v)));
  }
  s.finish();
  return p;
}

double fade(double x) {  // 1 up to 1, smoothly down to 0 at 2
  if (x <= 1) return 1;
  if (x >= 2) return 0;
  const double t = 2 - x;
  return t * t * (3 - 2 * t);
}

}  // namespace

int SkinParts::piece_at(const double p[3]) const {
  double c[3];
  int i[3];
  for (int a = 0; a < 3; ++a) {
    c[a] = (p[a] - origin[a]) / cell - 0.5;  // in cell-centre units
    i[a] = int(std::floor(c[a] + 0.5));
  }
  auto at = [&](int x, int y, int z) -> int {
    if (x < 0 || y < 0 || z < 0 || x >= dims[0] || y >= dims[1] || z >= dims[2]) return 255;
    return cells[(size_t(z) * size_t(dims[1]) + size_t(y)) * size_t(dims[0]) + size_t(x)];
  };
  const int own = at(i[0], i[1], i[2]);
  if (own != 255) return own;
  int best = -1;
  double dbest = 1e300;
  for (int dz = -1; dz <= 1; ++dz)
    for (int dy = -1; dy <= 1; ++dy)
      for (int dx = -1; dx <= 1; ++dx) {
        const int v = at(i[0] + dx, i[1] + dy, i[2] + dz);
        if (v == 255) continue;
        const double ex = i[0] + dx - c[0], ey = i[1] + dy - c[1], ez = i[2] + dz - c[2];
        const double d = ex * ex + ey * ey + ez * ez;
        if (d < dbest) best = v, dbest = d;
      }
  return best;
}

double SkinParts::gate(int piece, int b, const double p[3], const std::vector<std::array<double, 6>>& rest) const {
  if (piece < 0 || piece >= int(pieces.size())) return 1;
  const int mine = bone[size_t(b)];
  if (mine == piece) return 1;
  const Piece& own = pieces[size_t(piece)];
  const Piece& other = pieces[size_t(mine)];
  const double* joint = nullptr;
  double blend = 0;
  if (piece > 0 && b == own.from && own.first >= 0) {  // the body bone this limb hangs from
    joint = rest[size_t(own.first)].data(), blend = own.blend;
  } else if (mine > 0 && b == other.first && other.from >= 0 && bone[size_t(other.from)] == piece) {
    joint = rest[size_t(b)].data(), blend = other.blend;  // a limb hanging from this piece, at its joint
  } else {
    return 0;
  }
  const double dx = p[0] - joint[0], dy = p[1] - joint[1], dz = p[2] - joint[2];
  return fade(std::sqrt(dx * dx + dy * dy + dz * dz) / std::max(blend, 1e-9));
}

BoneMove read_bone_move(const JsValue& v, const std::string& where) {
  const std::vector<double> n = numbers(v, 12, where, "[m00, m01, m02, m10, m11, m12, m20, m21, m22, tx, ty, tz]");
  BoneMove m;
  std::copy(n.begin(), n.end(), m.begin());
  return m;
}

SkinRig read_skin(const JsObject& skin, const std::string& where) {
  Reader s(skin, where);
  const JsArray& jrest = s.list("rest");
  const JsArray& jpose = s.list("pose");
  const JsObject* jparts = s.has("parts") ? &s.object("parts") : nullptr;
  s.finish();
  if (jrest.empty()) fail(s.at("rest"), "is empty", "one [head x y z, tail x y z] per bone");
  if (jpose.empty()) fail(s.at("pose"), "is empty", "one list of bone moves per frame of the shot");
  SkinRig rig;
  for (size_t b = 0; b < jrest.size(); ++b) {
    const std::vector<double> r =
        numbers(jrest[b], 6, s.at("rest") + "[" + std::to_string(b) + "]", "[hx, hy, hz, tx, ty, tz]");
    std::array<double, 6> a;
    std::copy(r.begin(), r.end(), a.begin());
    rig.rest.push_back(a);
  }
  for (size_t f = 0; f < jpose.size(); ++f) {
    const std::string at = s.at("pose") + "[" + std::to_string(f) + "]";
    if (!jpose[f].IsArray() || jpose[f].GetJsArray().size() != rig.rest.size())
      fail(at, "does not hold one move per bone", std::to_string(rig.rest.size()) + " lists of 12 numbers");
    std::vector<BoneMove> frame;
    for (size_t b = 0; b < rig.rest.size(); ++b)
      frame.push_back(read_bone_move(jpose[f].GetJsArray()[b], at + "[" + std::to_string(b) + "]"));
    rig.pose.push_back(std::move(frame));
  }
  if (jparts) rig.parts = std::make_shared<const SkinParts>(read_parts(*jparts, rig.rest.size(), s.at("parts")));
  return rig;
}

// Automatic weights: each point leans on its nearest bones by 1 / distance⁴, so a point beside one bone follows it
// and a point at a joint shares it between both bones: the bend is smooth over about the item's thickness.
void skin_weights(const float* xyz, size_t n, const std::vector<std::array<double, 6>>& rest, int* idx, float* w,
                  double behind, const SkinParts* parts) {
  const int bones = int(rest.size()), k = skin_influences(rest.size());
  if (k == 0) return;
  std::vector<std::pair<double, int>> closest(bones);
  for (size_t i = 0; i < n; ++i) {
    const GfVec3d p(xyz[3 * i], xyz[3 * i + 1], xyz[3 * i + 2]);
    const double pd[3] = {p[0], p[1], p[2]};
    const int piece = parts ? parts->piece_at(pd) : -1;  // -1: every bone may lean on it
    for (int b = 0; b < bones; ++b) {
      const auto& r = rest[b];
      const GfVec3d a(r[0], r[1], r[2]), t(r[3], r[4], r[5]);
      double dist = segment_distance(p, a, t);
      if (behind > 0) {  // behind the head: how far back along the axis (metres), added `behind` times
        const GfVec3d ab = t - a;
        const double len = ab.GetLength();
        if (len > 0) dist += behind * std::max(0.0, -GfDot(p - a, ab) / len);
      }
      closest[b] = {(parts ? parts->gate(piece, b, pd, rest) : 1.0) / (std::pow(dist, 4) + 1e-12), b};
    }
    std::partial_sort(closest.begin(), closest.begin() + k, closest.end(), std::greater<>());
    double sum = 0;
    for (int j = 0; j < k; ++j) sum += closest[j].first;
    for (int j = 0; j < k; ++j) {
      idx[i * k + j] = closest[j].second;
      w[i * k + j] = float(closest[j].first / sum);
    }
  }
}

void skin_mesh(UsdGeomMesh m, const MeshData& d, const JsObject& skin, int start, const std::string& where) {
  const SkinRig rig = read_skin(skin, where);
  const int k = skin_influences(rig.rest.size());
  VtIntArray idx(d.points.size() * k);
  VtFloatArray w(d.points.size() * k);
  skin_weights(reinterpret_cast<const float*>(d.points.cdata()), d.points.size(), rig.rest, idx.data(), w.data());
  const bool normals = d.normals.size() == d.points.size();
  for (size_t f = 0; f < rig.pose.size(); ++f) {
    const std::string at = where + ".pose[" + std::to_string(f) + "]";
    std::vector<GfMatrix4d> xf;
    std::vector<GfMatrix3d> nx;
    for (const BoneMove& b : rig.pose[f]) {
      xf.push_back(as_usd(b));
      nx.push_back(xf.back().ExtractRotationMatrix().GetInverse().GetTranspose());
    }
    VtVec3fArray pts = d.points, nrm = d.normals;
    if (!UsdSkelSkinPointsLBS(GfMatrix4d(1.0), xf, idx, w, k, pts))
      fail(at, "the bones could not bend the mesh", "a move per bone that can be inverted");
    if (normals) UsdSkelSkinNormalsLBS(GfMatrix3d(1.0), nx, idx, w, k, nrm);
    const UsdTimeCode t(double(start) + double(f));
    m.GetPointsAttr().Set(pts, t);
    if (normals) m.GetNormalsAttr().Set(nrm, t);
    VtVec3fArray extent;
    if (UsdGeomPointBased::ComputeExtent(pts, &extent)) m.GetExtentAttr().Set(extent, t);
  }
}

}  // namespace r3d
