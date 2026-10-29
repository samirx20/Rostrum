// Clay: a clay bent by its bones (clay_skin.h).
#include "clay_skin.h"

#include <tbb/blocked_range.h>
#include <tbb/parallel_for.h>

#include <algorithm>
#include <cfloat>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <vector>
#include <utility>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

namespace {
// CL5b: a clay point's influences under this share of its total are dropped and the rest renormalised, so a block
// far from a bone doesn't follow it at all and isn't re-written when only that bone moves (1/d⁴ alone left every
// block leaning a little on every bone: a 2-bone test re-posed 6699 of 6704 blocks). Clay only: a mesh's skin keeps
// skin.cpp's weights as they are. gaps6: every influence is lowered by the share (those under it reach 0), so a
// weight crossing it fades instead of stepping to 0 (the step drew a crease across the belly under a raised arm).
// ROSTRUM3D_CLAY_SKIN_PRUNE sets it (0..0.5, to measure).
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

// CL6: posed clay blends its bone moves as dual quaternions (dual_quat.h), so a point shared by the body and a
// high-raised arm turns round the shoulder instead of being pulled to the average of its two places (the pinch under
// the arm). ROSTRUM3D_CLAY_SKIN_LINEAR=1 goes back to the linear blend (to compare).
bool linear_only() {
  static const bool v = [] {
    const char* env = std::getenv("ROSTRUM3D_CLAY_SKIN_LINEAR");
    return env && std::atoi(env) != 0;
  }();
  return v;
}

// 3e-3d: dual quaternions keep a joint's thickness but swell its inner side: a high-raised arm grew a lump between
// the shoulder and the neck (the Hello judges: "the waving arm grows out of a lumpy shoulder bulge"); linear blending
// pinches the same place in. Each posed point takes this share of the linear blend and the rest of the dual one, so
// the two errors cancel round the joint while a point on one bone (both blends the same) is unchanged. 0.75 (renders of
// the Hello figure at 65° and 110°: 0 balloons the shoulder, 0.5 still bulges at 110°, 1 is clean but a little thin).
// ROSTRUM3D_CLAY_SKIN_LINEAR_SHARE sets it (0 = dual quaternions alone, 1 = linear alone).
double linear_share() {
  static const double v = [] {
    const char* env = std::getenv("ROSTRUM3D_CLAY_SKIN_LINEAR_SHARE");
    return env ? std::clamp(std::atof(env), 0.0, 1.0) : 0.75;
  }();
  return v;
}

// gaps6: a point's weights are the average of the weights round it (a ball of this × the rig's mean bone length), so
// they change evenly across a joint instead of in a step a few millimetres wide: at a 150° raise the body points under
// the arm that leant ~30 % on it were swung far out while their neighbours stayed, and the surface folded into a torn
// fringe in the armpit (Hello, both judges). Smooth weights stretch the surface there instead. Position-only (no mesh
// neighbours), so a point shared by two blocks gets the same weights in both and no seam opens. 0 = off (to compare);
// ROSTRUM3D_CLAY_SKIN_SMOOTH sets it (0..1).
double smooth_share() {
  static const double v = [] {
    const char* env = std::getenv("ROSTRUM3D_CLAY_SKIN_SMOOTH");
    return env ? std::clamp(std::atof(env), 0.0, 1.0) : 0.25;
  }();
  return v;
}

// hello-fast: the smooth weights are worked out on a lattice of this × the ball's radius and blended per point from the
// 8 corners of its cell, not for every point (Hello's ~29 skin samples a point cost 4-16 s per new shape). The lattice
// is fixed in clay space, so a point shared by two blocks still gets the same weights in both, and a corner is worked
// out once per rig. 0 = every point on its own (to compare); ROSTRUM3D_CLAY_SKIN_GRID sets it (0..1).
double grid_share() {
  static const double v = [] {
    const char* env = std::getenv("ROSTRUM3D_CLAY_SKIN_GRID");
    return env ? std::clamp(std::atof(env), 0.0, 1.0) : 0.25;
  }();
  return v;
}

// a lattice corner's key: its 3 cell numbers, 21 bits each (±1 million steps)
std::uint64_t corner_key(std::int64_t x, std::int64_t y, std::int64_t z) {
  constexpr std::int64_t off = 1 << 20, mask = (1 << 21) - 1;
  return (std::uint64_t((x + off) & mask) << 42) | (std::uint64_t((y + off) & mask) << 21) | std::uint64_t((z + off) & mask);
}

// most corners kept per rig; past it the kept ones are dropped and worked out again as needed (~60 MB)
constexpr size_t kGridMost = 1000000;

// the sample offsets of the averaging ball (radius 1): its middle, 6 along the axes, 8 towards the corners, half way
// in and all the way out (the inner ones keep a thin limb's weights from being swamped by the far side's)
const std::vector<std::array<float, 3>>& ball() {
  static const std::vector<std::array<float, 3>> v = [] {
    std::vector<std::array<float, 3>> o{{0, 0, 0}};
    const float c = 1.0f / std::sqrt(3.0f);
    for (float r : {0.5f, 1.0f}) {
      for (int a = 0; a < 3; ++a)
        for (float s : {-r, r}) {
          std::array<float, 3> d{0, 0, 0};
          d[a] = s;
          o.push_back(d);
        }
      for (int i = 0; i < 8; ++i) o.push_back({(i & 1 ? c : -c) * r, (i & 2 ? c : -c) * r, (i & 4 ? c : -c) * r});
    }
    return o;
  }();
  return v;
}

double mean_bone(const std::vector<std::array<double, 6>>& rest) {
  double sum = 0;
  for (const auto& r : rest) sum += std::sqrt((r[3] - r[0]) * (r[3] - r[0]) + (r[4] - r[1]) * (r[4] - r[1]) + (r[5] - r[2]) * (r[5] - r[2]));
  return rest.empty() ? 0.0 : sum / double(rest.size());
}

// a point's influence with the largest weight (the pivot its dual quaternions are lined up with)
int heaviest(const int* idx, const float* w, int k) {
  int best = 0;
  for (int j = 1; j < k; ++j)
    if (w[j] > w[best]) best = j;
  return idx[best];
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
  dq_.assign(rig_->rest.size(), DualQuat{1, 0, 0, 0, 0, 0, 0, 0});
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
  const double radius = smooth_share() * mean_bone(rig_->rest);
  const double step = grid_share() * radius;
  if (step > 0) grid_weights(xyz, n, radius, step, b.idx.data(), b.w.data());
  tbb::parallel_for(tbb::blocked_range<size_t>(0, n, 512), [&](const tbb::blocked_range<size_t>& r) {
    if (step > 0) {
      // (weighed above, on the lattice)
    } else if (radius > 0) {
      smooth_weights(xyz + 3 * r.begin(), r.size(), radius, b.idx.data() + r.begin() * k, b.w.data() + r.begin() * k);
    } else {
      skin_weights(xyz + 3 * r.begin(), r.size(), rig_->rest, b.idx.data() + r.begin() * k, b.w.data() + r.begin() * k,
                   behind_head(), rig_->parts.get());
    }
    const float cut = prune_share();  // the weights are normalised: a share is the weight itself
    for (size_t i = r.begin(); i < r.end(); ++i) {
      float* w = b.w.data() + i * k;
      float sum = 0;
      for (int j = 0; j < k; ++j) {
        w[j] = std::max(0.0f, w[j] - cut);  // less by the cut, not dropped under it: no step where one crosses it
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

void Skinning::smooth_weights(const float* xyz, size_t n, double radius, int* idx, float* w) const {
  const int k = skin_influences(bones());
  const auto& offs = ball();
  const size_t S = offs.size();
  std::vector<float> at(n * S * 3);
  for (size_t i = 0; i < n; ++i)
    for (size_t s = 0; s < S; ++s)
      for (int c = 0; c < 3; ++c) at[(i * S + s) * 3 + c] = xyz[3 * i + c] + float(radius) * offs[s][c];
  std::vector<int> sidx(n * S * k);
  std::vector<float> sw(n * S * k);
  skin_weights(at.data(), n * S, rig_->rest, sidx.data(), sw.data(), behind_head(), rig_->parts.get());
  std::vector<double> sum(bones(), 0.0);
  std::vector<std::pair<double, int>> top(bones());
  for (size_t i = 0; i < n; ++i) {
    std::fill(sum.begin(), sum.end(), 0.0);
    for (size_t j = i * S * k; j < (i + 1) * S * k; ++j) sum[size_t(sidx[j])] += sw[j];
    for (size_t b = 0; b < bones(); ++b) top[b] = {sum[b], int(b)};
    std::partial_sort(top.begin(), top.begin() + k, top.end(), std::greater<>());
    double total = 0;
    for (int j = 0; j < k; ++j) total += top[j].first;
    for (int j = 0; j < k; ++j) {
      idx[i * k + j] = top[j].second;
      w[i * k + j] = float(total > 0 ? top[j].first / total : (j == 0 ? 1.0 : 0.0));
    }
  }
}

void Skinning::grid_weights(const float* xyz, size_t n, double radius, double step, int* idx, float* w) const {
  const int k = skin_influences(bones());
  // each point's cell and where it sits in it (0..1 per axis)
  std::vector<std::int64_t> cell(n * 3);
  std::vector<float> frac(n * 3);
  std::vector<std::uint64_t> keys(n * 8);
  tbb::parallel_for(tbb::blocked_range<size_t>(0, n, 4096), [&](const tbb::blocked_range<size_t>& r) {
    for (size_t i = r.begin(); i < r.end(); ++i) {
      for (int c = 0; c < 3; ++c) {
        const double u = double(xyz[3 * i + c]) / step, f = std::floor(u);
        cell[3 * i + c] = std::int64_t(f);
        frac[3 * i + c] = float(u - f);
      }
      for (int j = 0; j < 8; ++j)
        keys[i * 8 + j] = corner_key(cell[3 * i] + (j & 1), cell[3 * i + 1] + ((j >> 1) & 1), cell[3 * i + 2] + ((j >> 2) & 1));
    }
  });
  std::vector<std::uint64_t> want(keys);
  std::sort(want.begin(), want.end());
  want.erase(std::unique(want.begin(), want.end()), want.end());
  // the corners not kept yet, worked out (in parallel, outside the lock: the same corner always comes out the same)
  std::vector<std::uint64_t> missing;
  {
    std::lock_guard<std::mutex> lock(gridMu_);
    for (std::uint64_t key : want)
      if (!grid_.count(key)) missing.push_back(key);
  }
  if (!missing.empty()) {
    const std::int64_t off = 1 << 20, mask = (1 << 21) - 1;
    std::vector<float> at(missing.size() * 3);
    for (size_t i = 0; i < missing.size(); ++i) {
      const std::uint64_t key = missing[i];
      at[3 * i] = float(double(std::int64_t((key >> 42) & mask) - off) * step);
      at[3 * i + 1] = float(double(std::int64_t((key >> 21) & mask) - off) * step);
      at[3 * i + 2] = float(double(std::int64_t(key & mask) - off) * step);
    }
    std::vector<int> cidx(missing.size() * k);
    std::vector<float> cw(missing.size() * k);
    tbb::parallel_for(tbb::blocked_range<size_t>(0, missing.size(), 32), [&](const tbb::blocked_range<size_t>& r) {
      smooth_weights(at.data() + 3 * r.begin(), r.size(), radius, cidx.data() + r.begin() * k, cw.data() + r.begin() * k);
    });
    std::lock_guard<std::mutex> lock(gridMu_);
    if (grid_.size() + missing.size() > kGridMost) grid_.clear();
    for (size_t i = 0; i < missing.size(); ++i) {
      Corner c{};
      for (int j = 0; j < k; ++j) c.idx[j] = cidx[i * k + j], c.w[j] = cw[i * k + j];
      grid_[missing[i]] = c;
    }
  }
  // this block's corners, copied once (no lock while blending)
  std::vector<Corner> corners(want.size());
  {
    std::lock_guard<std::mutex> lock(gridMu_);
    for (size_t i = 0; i < want.size(); ++i) corners[i] = grid_.at(want[i]);
  }
  tbb::parallel_for(tbb::blocked_range<size_t>(0, n, 1024), [&](const tbb::blocked_range<size_t>& r) {
    std::pair<double, int> in[8 * kSkinMost];
    for (size_t i = r.begin(); i < r.end(); ++i) {
      int m = 0;
      for (int j = 0; j < 8; ++j) {
        const float fx = frac[3 * i], fy = frac[3 * i + 1], fz = frac[3 * i + 2];
        const double t = double(j & 1 ? fx : 1 - fx) * double(j & 2 ? fy : 1 - fy) * double(j & 4 ? fz : 1 - fz);
        if (t <= 0) continue;
        const Corner& c = corners[size_t(std::lower_bound(want.begin(), want.end(), keys[i * 8 + j]) - want.begin())];
        for (int q = 0; q < k; ++q) {
          if (c.w[q] <= 0) continue;
          int at = 0;
          while (at < m && in[at].second != c.idx[q]) ++at;
          if (at == m) in[m++] = {0.0, c.idx[q]};
          in[at].first += t * c.w[q];
        }
      }
      if (m == 0) in[m++] = {1.0, 0};  // (never: a corner's weights add up to 1)
      const int keep = std::min(m, k);
      std::partial_sort(in, in + keep, in + m, std::greater<>());
      double total = 0;
      for (int j = 0; j < keep; ++j) total += in[j].first;
      for (int j = 0; j < k; ++j) {
        idx[i * k + j] = j < keep ? in[j].second : in[0].second;
        w[i * k + j] = j < keep && total > 0 ? float(in[j].first / total) : (j == 0 ? 1.0f : 0.0f);
      }
    }
  });
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
      const int* ix = b.idx.data() + i * k;
      const float* iw = b.w.data() + i * k;
      std::pair<int, double> in[kSkinMost];
      for (int j = 0; j < k; ++j) in[j] = {ix[j], iw[j]};
      const Affine a = blend(in, k, heaviest(ix, iw, k));
      const GfVec3d q = a.point(GfVec3d(x, y, z));
      pp[i] = GfVec3f(float(q[0]), float(q[1]), float(q[2]));
      if (rn) {  // a turn is its own normal matrix; the linear share's slight shear is left in (as the linear blend did)
        GfVec3d nn = dual_ ? a.dir(GfVec3d(rn[i][0], rn[i][1], rn[i][2])) : GfVec3d(0);
        if (!dual_)
          for (int j = 0; j < k; ++j) {
            if (iw[j] <= 0) continue;
            const auto& m = nmat_[ix[j]];
            const double u = rn[i][0], v = rn[i][1], t = rn[i][2];
            nn += iw[j] * GfVec3d(m[0] * u + m[1] * v + m[2] * t, m[3] * u + m[4] * v + m[5] * t, m[6] * u + m[7] * v + m[8] * t);
          }
        pn[i] = nn.Normalize() > 1e-20 ? GfVec3f(nn) : rn[i];
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
  dual_ = !linear_only();
  for (size_t b = 0; b < bones() && dual_; ++b) dual_ = rigid(aff_[b].m);
  if (dual_)
    for (size_t b = 0; b < bones(); ++b) dq_[b] = dual_quat(aff_[b].m, aff_[b].t);
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
  if (!b.weighted) return Affine{};
  const int k = skin_influences(bones());
  std::pair<int, double> in[3 * kSkinMost];  // the corners' influences, as pose_block draws them
  for (int c = 0; c < 3; ++c) {
    const int v = b.indices[tri * 3 + c];
    for (int j = 0; j < k; ++j) in[c * k + j] = {b.idx[size_t(v) * k + j], bary[c] * b.w[size_t(v) * k + j]};
  }
  const int v0 = b.indices[tri * 3];
  return blend(in, 3 * k, heaviest(b.idx.data() + size_t(v0) * k, b.w.data() + size_t(v0) * k, k));
}

Affine Skinning::blend(const std::pair<int, double>* in, int count, int pivot) const {
  Affine lin;
  for (double& v : lin.m) v = 0;
  for (int j = 0; j < count; ++j) {
    const auto [bi, ww] = in[j];
    if (ww <= 0) continue;
    const Affine& a = aff_[bi];
    for (int i = 0; i < 9; ++i) lin.m[i] += ww * a.m[i];
    for (int i = 0; i < 3; ++i) lin.t[i] += ww * a.t[i];
  }
  if (!dual_) return lin;
  DualQuat sum{};
  for (int j = 0; j < count; ++j)
    if (in[j].second > 0) add_weighted(sum, dq_[in[j].first], in[j].second, dq_[pivot]);
  Affine dq;
  if (!to_move(sum, dq.m, dq.t)) dq = Affine{};
  const double s = linear_share();
  for (int i = 0; i < 9; ++i) dq.m[i] += s * (lin.m[i] - dq.m[i]);
  for (int i = 0; i < 3; ++i) dq.t[i] += s * (lin.t[i] - dq.t[i]);
  return dq;
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
