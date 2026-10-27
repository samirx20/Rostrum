// Clay: a clay bent by its bones (clay_skin.h).
#include "clay_skin.h"

#include <tbb/blocked_range.h>
#include <tbb/parallel_for.h>

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstdlib>
#include <utility>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

namespace {
// CL5b: a clay point's influences under this share of its total are dropped and the rest renormalised, so a block
// far from a bone doesn't follow it at all and isn't re-written when only that bone moves (1/d⁴ alone left every
// block leaning a little on every bone: a 2-bone test re-posed 6699 of 6704 blocks). Clay only: a mesh's skin keeps
// skin.cpp's weights as they are. ROSTRUM3D_CLAY_SKIN_PRUNE sets it (0..0.5, to measure).
float prune_share() {
  static const float v = [] {
    const char* env = std::getenv("ROSTRUM3D_CLAY_SKIN_PRUNE");
    const float x = env ? float(std::atof(env)) : 0.02f;
    return std::clamp(x, 0.0f, 0.5f);
  }();
  return v;
}

// CL5c: a clay point behind a bone's head counts as farther from that bone by this × how far behind (skin.h
// skin_weights `behind`): a limb whose head sits on the body's surface no longer drags the body's side along (the
// agent's wave: the raised arm pulled the body's upper side into a heart shape). 3: a body point 3 cm behind the
// shoulder and 7 cm off the arm's axis drops from ~42 % arm to ~3 %; the bend stays over about the limb's thickness
// at the joint (points beside the head, not behind it, are unchanged). ROSTRUM3D_CLAY_SKIN_BEHIND sets it (0..10).
double behind_head() {
  static const double v = [] {
    const char* env = std::getenv("ROSTRUM3D_CLAY_SKIN_BEHIND");
    return env ? std::clamp(std::atof(env), 0.0, 10.0) : 3.0;
  }();
  return v;
}

// the zero-area placeholder prims (an emptied block, the ring kept ready: clay_usd.h): one triangle, its 3 points
// the same. Never kept, posed or cast against
bool placeholder(const VtVec3fArray& p, const VtIntArray& i) {
  return i.size() <= 3 && (p.size() < 3 || (p.size() == 3 && p.cdata()[0] == p.cdata()[1] && p.cdata()[1] == p.cdata()[2]));
}
const BoneMove kRest{1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0};

bool invert3(const double m[9], double out[9]) {
  const double c00 = m[4] * m[8] - m[5] * m[7], c01 = m[5] * m[6] - m[3] * m[8], c02 = m[3] * m[7] - m[4] * m[6];
  const double det = m[0] * c00 + m[1] * c01 + m[2] * c02;
  if (!(std::fabs(det) > 1e-18)) return false;
  const double r = 1.0 / det;
  out[0] = c00 * r, out[1] = (m[2] * m[7] - m[1] * m[8]) * r, out[2] = (m[1] * m[5] - m[2] * m[4]) * r;
  out[3] = c01 * r, out[4] = (m[0] * m[8] - m[2] * m[6]) * r, out[5] = (m[2] * m[3] - m[0] * m[5]) * r;
  out[6] = c02 * r, out[7] = (m[1] * m[6] - m[0] * m[7]) * r, out[8] = (m[0] * m[4] - m[1] * m[3]) * r;
  return true;
}

// the normal matrix (m⁻ᵀ) of a move, row by row; a move that can't be inverted keeps normals as they are
std::array<double, 9> normal_matrix(const Affine& a) {
  double inv[9];
  if (!invert3(a.m, inv)) return {1, 0, 0, 0, 1, 0, 0, 0, 1};
  return {inv[0], inv[3], inv[6], inv[1], inv[4], inv[7], inv[2], inv[5], inv[8]};
}

// the ray's entry into the box, or false when it misses it (or enters past maxDist)
bool slab(const GfVec3d& o, const GfVec3d& d, const GfVec3f& lo, const GfVec3f& hi, double maxDist, double& enter) {
  double t0 = 0, t1 = maxDist;
  for (int c = 0; c < 3; ++c) {
    const double eps = 1e-6 * (1.0 + std::fabs(lo[c]) + std::fabs(hi[c]));
    const double a = double(lo[c]) - eps, b = double(hi[c]) + eps;
    if (std::fabs(d[c]) < 1e-15) {
      if (o[c] < a || o[c] > b) return false;
      continue;
    }
    double ta = (a - o[c]) / d[c], tb = (b - o[c]) / d[c];
    if (ta > tb) std::swap(ta, tb);
    t0 = std::max(t0, ta);
    t1 = std::min(t1, tb);
    if (t0 > t1) return false;
  }
  enter = t0;
  return true;
}
}  // namespace

Affine Affine::of(const BoneMove& b) {
  Affine a;
  for (int i = 0; i < 9; ++i) a.m[i] = b[i];
  for (int i = 0; i < 3; ++i) a.t[i] = b[9 + i];
  return a;
}

GfVec3d Affine::dir(const GfVec3d& d) const {
  return GfVec3d(m[0] * d[0] + m[1] * d[1] + m[2] * d[2], m[3] * d[0] + m[4] * d[1] + m[5] * d[2],
                 m[6] * d[0] + m[7] * d[1] + m[8] * d[2]);
}

GfVec3d Affine::point(const GfVec3d& p) const { return dir(p) + GfVec3d(t[0], t[1], t[2]); }

GfVec3d Affine::normal(const GfVec3d& n) const {
  double inv[9];
  if (!invert3(m, inv)) return n;
  GfVec3d out(inv[0] * n[0] + inv[3] * n[1] + inv[6] * n[2], inv[1] * n[0] + inv[4] * n[1] + inv[7] * n[2],
              inv[2] * n[0] + inv[5] * n[1] + inv[8] * n[2]);
  if (out.Normalize() < 1e-15) return n;
  return out;
}

bool Affine::inverse(Affine& out) const {
  if (!invert3(m, out.m)) return false;
  const GfVec3d ti = out.dir(GfVec3d(t[0], t[1], t[2]));
  out.t[0] = -ti[0], out.t[1] = -ti[1], out.t[2] = -ti[2];
  return true;
}

Skinning::Skinning(std::shared_ptr<const SkinRig> rig) : rig_(std::move(rig)) {
  moves_.assign(rig_->rest.size(), kRest);
  aff_.assign(rig_->rest.size(), Affine{});
  nmat_.assign(rig_->rest.size(), std::array<double, 9>{1, 0, 0, 0, 1, 0, 0, 0, 1});
}

void Skinning::set_rig(std::shared_ptr<const SkinRig> rig) { rig_ = std::move(rig); }

std::vector<BlockKey> Skinning::keys() const {
  std::vector<BlockKey> out;
  for (const auto& kv : blocks_) out.push_back(kv.first);
  return out;
}

void Skinning::weigh(Block& b) const {
  const size_t n = b.rest.size();
  const int k = skin_influences(bones());
  b.idx.assign(n * k, 0);
  b.w.assign(n * k, 0.0f);
  const float* xyz = reinterpret_cast<const float*>(b.rest.cdata());
  tbb::parallel_for(tbb::blocked_range<size_t>(0, n, 512), [&](const tbb::blocked_range<size_t>& r) {
    skin_weights(xyz + 3 * r.begin(), r.size(), rig_->rest, b.idx.data() + r.begin() * k, b.w.data() + r.begin() * k,
                 behind_head());
    const float cut = prune_share();  // the weights are normalised: a share is the weight itself
    for (size_t i = r.begin(); i < r.end(); ++i) {
      float* w = b.w.data() + i * k;
      float sum = 0;
      for (int j = 0; j < k; ++j) {
        if (w[j] < cut) w[j] = 0;
        sum += w[j];
      }
      if (sum > 0)
        for (int j = 0; j < k; ++j) w[j] /= sum;
      else
        w[0] = 1;  // (never: the nearest bone holds at least 1/k)
    }
  });
  std::vector<char> on(bones(), 0);
  for (size_t i = 0; i < b.idx.size(); ++i)
    if (b.w[i] > 0) on[b.idx[i]] = 1;
  b.bones.clear();
  for (size_t i = 0; i < on.size(); ++i)
    if (on[i]) b.bones.push_back(int(i));
  b.weighted = true;
}

void Skinning::pose_block(Block& b) const {
  const size_t n = b.rest.size();
  if (!posed_) {
    b.posed = b.rest;
    b.posedN = b.restN;
  } else {
    if (!b.weighted) weigh(b);
    const int k = skin_influences(bones());
    const bool normals = b.restN.size() == n;
    VtVec3fArray pts(n), nrm(normals ? n : 0);
    const GfVec3f* rp = b.rest.cdata();
    const GfVec3f* rn = normals ? b.restN.cdata() : nullptr;
    GfVec3f* pp = pts.data();
    GfVec3f* pn = normals ? nrm.data() : nullptr;
    for (size_t i = 0; i < n; ++i) {
      const double x = rp[i][0], y = rp[i][1], z = rp[i][2];
      double px = 0, py = 0, pz = 0, nx = 0, ny = 0, nz = 0;
      for (int j = 0; j < k; ++j) {
        const float ww = b.w[i * k + j];
        if (ww <= 0) continue;
        const int bi = b.idx[i * k + j];
        const Affine& a = aff_[bi];
        px += ww * (a.m[0] * x + a.m[1] * y + a.m[2] * z + a.t[0]);
        py += ww * (a.m[3] * x + a.m[4] * y + a.m[5] * z + a.t[1]);
        pz += ww * (a.m[6] * x + a.m[7] * y + a.m[8] * z + a.t[2]);
        if (rn) {
          const auto& q = nmat_[bi];
          const double u = rn[i][0], v = rn[i][1], s = rn[i][2];
          nx += ww * (q[0] * u + q[1] * v + q[2] * s);
          ny += ww * (q[3] * u + q[4] * v + q[5] * s);
          nz += ww * (q[6] * u + q[7] * v + q[8] * s);
        }
      }
      pp[i] = GfVec3f(float(px), float(py), float(pz));
      if (rn) {
        const double l = std::sqrt(nx * nx + ny * ny + nz * nz);
        pn[i] = l > 1e-20 ? GfVec3f(float(nx / l), float(ny / l), float(nz / l)) : rn[i];
      }
    }
    b.posed = std::move(pts);
    b.posedN = normals ? std::move(nrm) : b.restN;
  }
  GfVec3f lo(FLT_MAX), hi(-FLT_MAX);
  const GfVec3f* pp = b.posed.cdata();  // (cdata: a shared array is never copied to be read)
  for (size_t i = 0; i < n; ++i)
    for (int c = 0; c < 3; ++c) lo[c] = std::min(lo[c], pp[i][c]), hi[c] = std::max(hi[c], pp[i][c]);
  if (n == 0) lo = hi = GfVec3f(0.0f);
  b.lo = lo;
  b.hi = hi;
}

bool Skinning::keep(const BlockKey& k, const VtVec3fArray& points, const VtVec3fArray& normals,
                    const VtIntArray& indices) {
  if (placeholder(points, indices)) {
    blocks_.erase(k);
    return false;
  }
  Block& b = blocks_[k];
  b.rest = points;
  b.restN = normals;
  b.indices = indices;
  b.weighted = false;
  b.idx.clear();
  b.w.clear();
  b.bones.clear();
  // weighed now, at rest or not (CL5b): the first move of a drag must not weigh the whole clay
  weigh(b);
  pose_block(b);
  return true;
}

void Skinning::drop(const BlockKey& k) { blocks_.erase(k); }

bool Skinning::rest(const BlockKey& k, VtVec3fArray& points, VtVec3fArray& normals, VtIntArray& indices) const {
  auto it = blocks_.find(k);
  if (it == blocks_.end()) return false;
  points = it->second.rest;
  normals = it->second.restN;
  indices = it->second.indices;
  return true;
}

bool Skinning::posed_surface(const BlockKey& k, VtVec3fArray& points, VtVec3fArray& normals,
                             VtVec3fArray& extent) const {
  auto it = blocks_.find(k);
  if (it == blocks_.end()) return false;
  points = it->second.posed;
  normals = it->second.posedN;
  extent = VtVec3fArray{it->second.lo, it->second.hi};
  return true;
}

std::vector<BlockKey> Skinning::pose(const std::vector<BoneMove>& moves) {
  if (moves.size() != bones()) return {};
  std::vector<char> changed(bones(), 0);
  bool any = false;
  for (size_t b = 0; b < bones(); ++b)
    if (moves[b] != moves_[b]) changed[b] = 1, any = true;
  if (!any) return {};
  bool posed = false;
  for (size_t b = 0; b < bones(); ++b) {
    moves_[b] = moves[b];
    aff_[b] = Affine::of(moves[b]);
    nmat_[b] = normal_matrix(aff_[b]);
    posed = posed || moves[b] != kRest;
  }
  posed_ = posed;
  // the blocks one of whose bones moved. A block not weighed yet was kept while every bone was at rest and none
  // moved since (any pose away from rest weighs them all): it is weighed now, and drawn at rest until then.
  std::vector<std::pair<BlockKey, Block*>> todo;
  std::vector<Block*> weighOnly;
  for (auto& [key, b] : blocks_) {
    if (!b.weighted) {
      if (!posed_) continue;  // at rest, and drawn at rest
      weighOnly.push_back(&b);
      todo.emplace_back(key, &b);  // its bones are known once weighed: checked below
      continue;
    }
    for (int bi : b.bones)
      if (changed[bi]) {
        todo.emplace_back(key, &b);
        break;
      }
  }
  tbb::parallel_for(size_t(0), weighOnly.size(), [&](size_t i) { weigh(*weighOnly[i]); });
  std::vector<std::pair<BlockKey, Block*>> moved;
  for (const auto& kb : todo) {
    bool hit = false;
    for (int bi : kb.second->bones) hit = hit || changed[bi];
    if (hit) moved.push_back(kb);
  }
  tbb::parallel_for(size_t(0), moved.size(), [&](size_t i) { pose_block(*moved[i].second); });
  std::vector<BlockKey> out;
  for (const auto& kb : moved) out.push_back(kb.first);
  return out;
}

Affine Skinning::blend_at(const Block& b, int tri, const double bary[3]) const {
  Affine out;
  if (!b.weighted) return out;
  for (double& v : out.m) v = 0;
  const int k = skin_influences(bones());
  for (int c = 0; c < 3; ++c) {
    const int v = b.indices[tri * 3 + c];
    for (int j = 0; j < k; ++j) {
      const double ww = bary[c] * b.w[size_t(v) * k + j];
      const Affine& a = aff_[b.idx[size_t(v) * k + j]];
      for (int i = 0; i < 9; ++i) out.m[i] += ww * a.m[i];
      for (int i = 0; i < 3; ++i) out.t[i] += ww * a.t[i];
    }
  }
  return out;
}

bool Skinning::cast(const GfVec3d& o, const GfVec3d& d, double maxDist, PosedHit& hit) const {
  std::vector<std::pair<double, const std::pair<const BlockKey, Block>*>> boxes;
  for (const auto& kb : blocks_) {
    double enter = 0;
    if (kb.second.indices.size() >= 3 && slab(o, d, kb.second.lo, kb.second.hi, maxDist, enter))
      boxes.emplace_back(enter, &kb);
  }
  std::sort(boxes.begin(), boxes.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
  double best = maxDist;
  const std::pair<const BlockKey, Block>* bestBlock = nullptr;
  int bestTri = -1;
  double bu = 0, bv = 0;
  for (const auto& [enter, kb] : boxes) {
    if (enter > best) break;
    const Block& b = kb->second;
    const GfVec3f* p = b.posed.cdata();
    const int* ix = b.indices.cdata();
    const size_t tris = b.indices.size() / 3;
    for (size_t t = 0; t < tris; ++t) {
      const GfVec3d a(p[ix[3 * t]]), e1 = GfVec3d(p[ix[3 * t + 1]]) - a, e2 = GfVec3d(p[ix[3 * t + 2]]) - a;
      const GfVec3d h = GfCross(d, e2);
      const double det = GfDot(e1, h);
      if (std::fabs(det) < 1e-20) continue;  // no area, or edge-on
      const double inv = 1.0 / det;
      const GfVec3d s = o - a;
      const double u = GfDot(s, h) * inv;
      if (u < 0 || u > 1) continue;
      const GfVec3d q = GfCross(s, e1);
      const double v = GfDot(d, q) * inv;
      if (v < 0 || u + v > 1) continue;
      const double tt = GfDot(e2, q) * inv;
      if (tt <= 1e-9 || tt >= best) continue;
      best = tt, bestBlock = kb, bestTri = int(t), bu = u, bv = v;
    }
  }
  if (!bestBlock) return false;
  hit.key = bestBlock->first;
  hit.tri = bestTri;
  hit.t = best;
  hit.bary[0] = 1 - bu - bv, hit.bary[1] = bu, hit.bary[2] = bv;
  hit.point = o + d * best;
  hit.blend = blend_at(bestBlock->second, bestTri, hit.bary);
  return true;
}

std::optional<GfVec3d> Skinning::rest_spot(const BlockKey& k, int tri, const GfVec3d& at) const {
  auto it = blocks_.find(k);
  if (it == blocks_.end()) return std::nullopt;
  const Block& b = it->second;
  if (tri < 0 || size_t(tri) * 3 + 2 >= b.indices.size()) return std::nullopt;
  const int i0 = b.indices[tri * 3], i1 = b.indices[tri * 3 + 1], i2 = b.indices[tri * 3 + 2];
  const GfVec3d a(b.posed[i0]), e1 = GfVec3d(b.posed[i1]) - a, e2 = GfVec3d(b.posed[i2]) - a, s = at - a;
  // barycentric of the spot projected onto the triangle's plane
  const double d00 = GfDot(e1, e1), d01 = GfDot(e1, e2), d11 = GfDot(e2, e2), d20 = GfDot(s, e1), d21 = GfDot(s, e2);
  const double den = d00 * d11 - d01 * d01;
  double v = 0, w = 0;
  if (std::fabs(den) > 1e-30) {
    v = (d11 * d20 - d01 * d21) / den;
    w = (d00 * d21 - d01 * d20) / den;
  }
  const double u = 1 - v - w;
  return GfVec3d(b.rest[i0]) * u + GfVec3d(b.rest[i1]) * v + GfVec3d(b.rest[i2]) * w;
}

}  // namespace r3d::clay
