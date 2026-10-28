#include "skin.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>
#include <vector>

#include <pxr/base/gf/matrix3d.h>
#include <pxr/base/gf/matrix4d.h>
#include <pxr/usd/usdSkel/utils.h>
#include <tbb/parallel_for.h>

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

// CL7b: how wide the band where two pieces' shares cross is: the spread's blur, × the limb's blend
constexpr double kShareWidth = 1.5;
constexpr int kShareRings = 2;   // outside cells round the clay with shares too (a surface point sits between cells)
constexpr int kShareMost = 256;  // spreading steps at most (a very fine grid's band comes out a little narrower)
// the share spreads only round the limb's joint: within this × blend of it, or the whole patch where its root meets
// the body (make_shares); elsewhere (an arm resting on the belly, a hanging forearm by the hip) each cell keeps its
// own piece, sharpened (shares_at), so a touching limb neither drags the body along nor leaves "+" marks
constexpr double kShareReach = 3.0;
// 3d-gaps: a limb's root, the cells of the piece it hangs from past its joint along its first bone and within this ×
// its radius (blend / 1.5) of that bone, are the limb's own. The finder's limb starts where it leaves the body, often
// well past the joint; the clay between counted as the body's and stayed behind as the arm turned about the joint, so
// a raised arm tore from the shoulder. Now its share is whole from the joint out and the shared band lies round the
// joint, where a turn moves the surface least
constexpr double kRootWidth = 1.0;
// 3d-gaps2: the spread round a limb's joint stays inside a tube this × its radius round its first bone (and round the
// joint itself): the root rule alone let the share spread from the joint into whatever clay sat beside it, so the head
// next to a raised arm turned with it and creased. 1.5 (renders at 1-3, root 0.8-1.5): no head crease, the shoulder bends
constexpr double kShareTube = 1.5;

double fade(double x) {  // 1 up to 1, smoothly down to 0 at 2
  if (x <= 1) return 1;
  if (x >= 2) return 0;
  const double t = 2 - x;
  return t * t * (3 - 2 * t);
}

}  // namespace

void SkinParts::make_shares(const std::vector<std::array<double, 6>>& rest) {
  share.clear();
  joint.assign(pieces.size(), {0, 0, 0, 0});
  const int P = int(pieces.size());
  if (P < 2) return;
  const int nx = dims[0], ny = dims[1], nz = dims[2];
  const size_t N = cells.size();
  auto at = [&](int x, int y, int z) { return (size_t(z) * size_t(ny) + size_t(y)) * size_t(nx) + size_t(x); };
  auto in = [&](int x, int y, int z) { return x >= 0 && y >= 0 && z >= 0 && x < nx && y < ny && z < nz; };
  // each limb's joint and reach: kShareReach × its blend, or farther, to cover the whole patch where its root meets
  // the clay round it (its cells beside another piece's, 26-connected, the patch with the cell nearest the joint) and
  // a blend beyond; other patches (a forearm resting on the hip) stay sharp
  for (int n = 1; n < P; ++n) {
    const Piece& pc = pieces[size_t(n)];
    if (pc.first < 0 || size_t(pc.first) >= rest.size() || !(pc.blend > 0)) continue;
    const double* h = rest[size_t(pc.first)].data();
    double reach = kShareReach * pc.blend;
    std::vector<int> face(N, -1);  // the patch cells: 0 found, 1 in the root's patch
    size_t first = N;
    double dfirst = 1e300;
    auto dist = [&](size_t i) {
      const int x = int(i % size_t(nx)), y = int((i / size_t(nx)) % size_t(ny)), z = int(i / (size_t(nx) * size_t(ny)));
      const double dx = origin[0] + (x + 0.5) * cell - h[0], dy = origin[1] + (y + 0.5) * cell - h[1],
                   dz = origin[2] + (z + 0.5) * cell - h[2];
      return std::sqrt(dx * dx + dy * dy + dz * dz);
    };
    for (int z = 0; z < nz; ++z)
      for (int y = 0; y < ny; ++y)
        for (int x = 0; x < nx; ++x) {
          if (cells[at(x, y, z)] != n) continue;
          const int nb[6][3] = {{x - 1, y, z}, {x + 1, y, z}, {x, y - 1, z}, {x, y + 1, z}, {x, y, z - 1}, {x, y, z + 1}};
          bool other = false;
          for (const auto& q : nb)
            if (in(q[0], q[1], q[2])) {
              const int v = cells[at(q[0], q[1], q[2])];
              other = other || (v != 255 && v != n);
            }
          if (!other) continue;
          const size_t i = at(x, y, z);
          face[i] = 0;
          if (const double d = dist(i); d < dfirst) dfirst = d, first = i;
        }
    if (first < N) {
      std::vector<size_t> todo{first};
      face[first] = 1;
      double farthest = dfirst;
      while (!todo.empty()) {
        const size_t i = todo.back();
        todo.pop_back();
        farthest = std::max(farthest, dist(i));
        const int x = int(i % size_t(nx)), y = int((i / size_t(nx)) % size_t(ny)), z = int(i / (size_t(nx) * size_t(ny)));
        for (int dz = -1; dz <= 1; ++dz)
          for (int dy = -1; dy <= 1; ++dy)
            for (int dx = -1; dx <= 1; ++dx) {
              if (!in(x + dx, y + dy, z + dz)) continue;
              const size_t j = at(x + dx, y + dy, z + dz);
              if (face[j] == 0) face[j] = 1, todo.push_back(j);
            }
      }
      reach = std::max(reach, farthest + pc.blend);
    }
    joint[size_t(n)] = {h[0], h[1], h[2], reach};
  }
  // the cells that get shares: inside ones (1), then kShareRings rings of outside ones round them (2, 3 …)
  std::vector<unsigned char> valued(N, 0);
  for (size_t i = 0; i < N; ++i) valued[i] = cells[i] != 255;
  std::vector<std::vector<size_t>> rings(kShareRings);
  for (int r = 0; r < kShareRings; ++r) {
    for (int z = 0; z < nz; ++z)
      for (int y = 0; y < ny; ++y)
        for (int x = 0; x < nx; ++x) {
          if (valued[at(x, y, z)]) continue;
          bool touches = false;
          for (int dz = -1; dz <= 1 && !touches; ++dz)
            for (int dy = -1; dy <= 1 && !touches; ++dy)
              for (int dx = -1; dx <= 1 && !touches; ++dx)
                touches = in(x + dx, y + dy, z + dz) && valued[at(x + dx, y + dy, z + dz)];
          if (touches) rings[size_t(r)].push_back(at(x, y, z));
        }
    for (size_t i : rings[size_t(r)]) valued[i] = static_cast<unsigned char>(2 + r);
  }
  share.assign(size_t(P - 1) * N, std::numeric_limits<float>::quiet_NaN());
  tbb::parallel_for(1, P, [&](int n) {
    float* out = share.data() + size_t(n - 1) * N;
    const Piece& pc = pieces[size_t(n)];
    std::vector<char> own(N, 0);  // the limb's cells and its root (kRootWidth): all its share, never spread
    for (size_t i = 0; i < N; ++i) own[i] = cells[i] == n;
    if (pc.first >= 0 && size_t(pc.first) < rest.size() && pc.blend > 0) {
      const double* s = rest[size_t(pc.first)].data();
      const double ab[3] = {s[3] - s[0], s[4] - s[1], s[5] - s[2]}, len2 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2];
      const int parent = pc.from >= 0 && size_t(pc.from) < bone.size() ? bone[size_t(pc.from)] : 0;
      const double width = kRootWidth * pc.blend / 1.5;
      if (len2 > 0)
        for (size_t i = 0; i < N; ++i) {
          if (cells[i] != parent) continue;
          const int x = int(i % size_t(nx)), y = int((i / size_t(nx)) % size_t(ny)), z = int(i / (size_t(nx) * size_t(ny)));
          const double q[3] = {origin[0] + (x + 0.5) * cell - s[0], origin[1] + (y + 0.5) * cell - s[1],
                               origin[2] + (z + 0.5) * cell - s[2]};
          const double t = (q[0] * ab[0] + q[1] * ab[1] + q[2] * ab[2]) / len2;
          if (t < 0) continue;
          const double c = std::min(t, 1.0), dx = q[0] - c * ab[0], dy = q[1] - c * ab[1], dz = q[2] - c * ab[2];
          own[i] = dx * dx + dy * dy + dz * dz <= width * width;
        }
    }
    std::vector<float> f(N, 0.0f);
    for (size_t i = 0; i < N; ++i) f[i] = own[i] ? 1.0f : 0.0f;
    if (joint[size_t(n)][3] > 0) {
      // spread through the inside round the joint only: each step an inside cell there takes the mean of itself and
      // its inside neighbours (a blur of about sqrt(2 × steps / 7) cells along the clay, never across air); the
      // cells beyond the reach stay as they are, and so do the limb's own (3d-28: the spread goes out into the body
      // only; spreading the body back into a thin arm left the upper arm a third the body's, torn from the shoulder)
      const double* at_joint = joint[size_t(n)].data();
      const double sigma = std::max(kShareWidth * pc.blend / cell, 0.5), reach = at_joint[3];
      const int steps = std::min(kShareMost, int(std::lround(3.5 * sigma * sigma)));
      int lo[3], hi[3];
      for (int a = 0; a < 3; ++a) {
        lo[a] = std::max(0, int(std::floor((at_joint[a] - reach - origin[a]) / cell)) - 1);
        hi[a] = std::min(dims[a] - 1, int(std::ceil((at_joint[a] + reach - origin[a]) / cell)) + 1);
      }
      auto by_joint = [&](int x, int y, int z) {
        const double dx = origin[0] + (x + 0.5) * cell - at_joint[0], dy = origin[1] + (y + 0.5) * cell - at_joint[1],
                     dz = origin[2] + (z + 0.5) * cell - at_joint[2];
        if (dx * dx + dy * dy + dz * dz > reach * reach) return false;
        const double* s = rest[size_t(pc.first)].data();
        const double ab[3] = {s[3] - s[0], s[4] - s[1], s[5] - s[2]}, len2 = ab[0] * ab[0] + ab[1] * ab[1] + ab[2] * ab[2];
        const double q[3] = {origin[0] + (x + 0.5) * cell - s[0], origin[1] + (y + 0.5) * cell - s[1], origin[2] + (z + 0.5) * cell - s[2]};
        const double t = len2 > 0 ? std::clamp((q[0] * ab[0] + q[1] * ab[1] + q[2] * ab[2]) / len2, 0.0, 1.0) : 0.0;
        const double ex = q[0] - t * ab[0], ey = q[1] - t * ab[1], ez = q[2] - t * ab[2], w = kShareTube * pc.blend / 1.5;
        return ex * ex + ey * ey + ez * ez <= w * w;
      };
      std::vector<float> g = f;
      for (int it = 0; it < steps; ++it) {
        for (int z = lo[2]; z <= hi[2]; ++z)
          for (int y = lo[1]; y <= hi[1]; ++y)
            for (int x = lo[0]; x <= hi[0]; ++x) {
              const size_t i = at(x, y, z);
              if (cells[i] == 255 || own[i] || !by_joint(x, y, z)) continue;
              double sum = f[i];
              int cnt = 1;
              const int nb[6][3] = {{x - 1, y, z}, {x + 1, y, z}, {x, y - 1, z},
                                    {x, y + 1, z}, {x, y, z - 1}, {x, y, z + 1}};
              for (const auto& q : nb)
                if (in(q[0], q[1], q[2]) && cells[at(q[0], q[1], q[2])] != 255) sum += f[at(q[0], q[1], q[2])], ++cnt;
              g[i] = float(sum / cnt);
            }
        std::swap(f, g);
      }
    }
    for (size_t i = 0; i < N; ++i)
      if (valued[i] == 1) out[i] = f[i];
    for (int r = 0; r < kShareRings; ++r)  // an outside cell: the mean of its neighbours valued before its ring
      for (size_t i : rings[size_t(r)]) {
        const int x = int(i % size_t(nx)), y = int((i / size_t(nx)) % size_t(ny)), z = int(i / (size_t(nx) * size_t(ny)));
        double sum = 0;
        int cnt = 0;
        for (int dz = -1; dz <= 1; ++dz)
          for (int dy = -1; dy <= 1; ++dy)
            for (int dx = -1; dx <= 1; ++dx) {
              if (!in(x + dx, y + dy, z + dz)) continue;
              const size_t j = at(x + dx, y + dy, z + dz);
              if (valued[j] && valued[j] < 2 + r) sum += out[j], ++cnt;
            }
        out[i] = cnt ? float(sum / cnt) : 0.0f;
      }
  });
}

bool SkinParts::shares_at(const double p[3], double* out) const {
  const int P = int(pieces.size());
  if (P < 2) {
    if (P == 1) out[0] = 1;
    return P == 1;
  }
  const size_t N = cells.size();
  int i0[3];
  double t[3];
  for (int a = 0; a < 3; ++a) {  // trilinear between the 8 cell centres round p (clamped to the grid)
    const double c = std::clamp((p[a] - origin[a]) / cell - 0.5, 0.0, double(dims[a] - 1));
    i0[a] = std::min(int(std::floor(c)), std::max(dims[a] - 2, 0));
    t[a] = dims[a] > 1 ? c - i0[a] : 0.0;
  }
  for (int n = 0; n < P; ++n) out[n] = 0;
  double wsum = 0;
  for (int corner = 0; corner < 8; ++corner) {
    size_t i = 0, stride = 1;
    double wt = 1;
    for (int a = 0; a < 3; ++a) {
      const int up = (corner >> a) & 1;
      i += size_t(std::min(i0[a] + up, dims[a] - 1)) * stride;
      stride *= size_t(dims[a]);
      wt *= up ? t[a] : 1 - t[a];
    }
    if (wt <= 0 || std::isnan(share[i])) continue;  // no clay near that cell
    wsum += wt;
    for (int n = 1; n < P; ++n) out[n] += wt * share[size_t(n - 1) * N + i];
  }
  if (wsum < 1e-9) return false;
  double limbs = 0;
  for (int n = 1; n < P; ++n) {
    out[n] /= wsum;
    // beyond the joint's reach the share is sharpened (a crease between a resting limb and the body splits within
    // a fraction of a cell, so a body point beside a limb cell stays the body's); smoothly towards the joint
    const auto& j = joint[size_t(n)];
    const double dx = p[0] - j[0], dy = p[1] - j[1], dz = p[2] - j[2];
    const double k = j[3] > 0 ? std::clamp((j[3] - std::sqrt(dx * dx + dy * dy + dz * dz)) * 3 / j[3], 0.0, 1.0) : 0;
    const double x = std::clamp((out[n] - 0.25) * 2, 0.0, 1.0);
    out[n] = k * out[n] + (1 - k) * x * x * (3 - 2 * x);
    limbs += out[n];
  }
  out[0] = std::max(0.0, 1 - limbs);
  const double total = out[0] + limbs;
  for (int n = 0; n < P; ++n) out[n] /= total;
  return true;
}

double SkinParts::gate_in(int piece, int b, const double p[3], const std::vector<std::array<double, 6>>& rest) const {
  if (piece < 0 || piece >= int(pieces.size())) return 1;
  const int mine = bone[size_t(b)];
  if (mine == piece) return 1;
  const Piece& own = pieces[size_t(piece)];
  // only the body bone a limb hangs from, seen from the limb (3d-28: a limb's first bone seen from the body is not
  // gated in; it is so much nearer than the body's middle bones that the body round the joint turned rigidly with the
  // arm and left a dented rim; the shares bring the limb into the body smoothly instead)
  if (!(piece > 0 && b == own.from && own.first >= 0)) return 0;
  const double* joint = rest[size_t(own.first)].data();
  const double dx = p[0] - joint[0], dy = p[1] - joint[1], dz = p[2] - joint[2];
  return fade(std::sqrt(dx * dx + dy * dy + dz * dz) / std::max(own.blend, 1e-9));
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
  if (jparts) {
    SkinParts parts = read_parts(*jparts, rig.rest.size(), s.at("parts"));
    parts.make_shares(rig.rest);
    rig.parts = std::make_shared<const SkinParts>(std::move(parts));
  }
  return rig;
}

// Automatic weights: each point leans on its nearest bones by 1 / distance⁴, so a point beside one bone follows it
// and a point at a joint shares it between both bones: the bend is smooth over about the item's thickness.
void skin_weights(const float* xyz, size_t n, const std::vector<std::array<double, 6>>& rest, int* idx, float* w,
                  double behind, const SkinParts* parts) {
  const int bones = int(rest.size()), k = skin_influences(rest.size());
  if (k == 0) return;
  std::vector<std::pair<double, int>> closest(bones), mine(bones);
  std::vector<double> shares(parts ? parts->pieces.size() : 0), pull(bones), mix(bones);
  for (size_t i = 0; i < n; ++i) {
    const GfVec3d p(xyz[3 * i], xyz[3 * i + 1], xyz[3 * i + 2]);
    const double pd[3] = {p[0], p[1], p[2]};
    const bool gated = parts && parts->shares_at(pd, shares.data());  // no clay near: every bone may lean on it
    for (int b = 0; b < bones; ++b) {
      const auto& r = rest[b];
      const GfVec3d a(r[0], r[1], r[2]), t(r[3], r[4], r[5]);
      double dist = segment_distance(p, a, t);
      // behind the head: how far back along the axis (metres), added `behind` times. CL7b: with parts, a limb's bones
      // only; the body's own (the low belly is behind the root bone's head) not, or the belly leant on the chest and
      // swung out with the wave
      if (behind > 0 && !(parts && parts->bone[size_t(b)] == 0)) {
        const GfVec3d ab = t - a;
        const double len = ab.GetLength();
        if (len > 0) dist += behind * std::max(0.0, -GfDot(p - a, ab) / len);
      }
      pull[b] = 1.0 / (std::pow(dist, 4) + 1e-12);
      closest[b] = {pull[b], b};
    }
    if (gated) {  // CL7b: each piece's own weights mixed by the point's shares
      std::fill(mix.begin(), mix.end(), 0.0);
      // the 4 largest of `mine`, normalised, × share into mix
      auto add = [&](double share) {
        std::partial_sort(mine.begin(), mine.begin() + k, mine.end(), std::greater<>());
        double s = 0;
        for (int j = 0; j < k; ++j) s += mine[j].first;
        if (s > 0)
          for (int j = 0; j < k; ++j) mix[mine[j].second] += share * mine[j].first / s;
      };
      for (int pc = 0; pc < int(shares.size()); ++pc) {
        if (shares[size_t(pc)] <= 0) continue;
        // a piece's weights: its own bones', and by how far the point is into a joint's blend (the neighbour bone's
        // gate) those with the neighbour bone too. Mixed by the gate, not multiplied into 1 / distance⁴, so a
        // nearer neighbour bone's share falls evenly over the blend instead of all at its far end (CL7: the body
        // under a raised arm went from 70 % arm to 2 % in 1.6 cm and tore)
        double across = 0;
        for (int b = 0; b < bones; ++b) {
          const double g = parts->gate_in(pc, b, pd, rest);
          if (parts->bone[size_t(b)] != pc) across = std::max(across, g);
          mine[b] = {g * pull[b], b};
        }
        if (across > 0) add(shares[size_t(pc)] * across);
        if (across < 1) {
          for (int b = 0; b < bones; ++b) mine[b] = {parts->bone[size_t(b)] == pc ? pull[b] : 0.0, b};
          add(shares[size_t(pc)] * (1 - across));
        }
      }
      double total = 0;
      for (int b = 0; b < bones; ++b) total += mix[b];
      if (total > 0)  // (always: each piece holds a bone)
        for (int b = 0; b < bones; ++b) closest[b] = {mix[b], b};
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
