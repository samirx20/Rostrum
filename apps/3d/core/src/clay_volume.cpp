// Clay: the volume's steps (clay_volume.h). A piece works here; a unit of dabs is handed to clay_band.cpp.
// Moved from proofs/3d-clay (clay.cpp: Clay::run, apply_stroke, the live stroke), plus undo records.
#include "clay_volume.h"

#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <optional>

#include "clay_box.h"
#include "clay_coarse.h"
#include "clay_shapes.h"
#include "error.h"

namespace r3d::clay {

using namespace detail;

namespace {
std::once_flag g_init;
bool prof_on() {  // ROSTRUM3D_CLAY_PROFILE=1: each dab's stages on stderr (3d-v3, a check's tool)
  static const bool on = std::getenv("ROSTRUM3D_CLAY_PROFILE") != nullptr;
  return on;
}
double ms_since(std::chrono::steady_clock::time_point t0) {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}
}  // namespace

const ChunkRecord::Chunk* ChunkRecord::find(const Coord& o) const {
  if (!on) return nullptr;
  const auto it = seen_.find({o.x(), o.y(), o.z()});
  return it == seen_.end() ? nullptr : &chunks_[it->second];
}

void ChunkRecord::keep(const Tree& t, const Tree* maskTree, const Coord& o) {
  if (!on || !seen_.emplace(std::make_tuple(o.x(), o.y(), o.z()), chunks_.size()).second) return;
  Chunk c;
  c.o = o;
  if (const Leaf* l = t.probeConstLeaf(o)) {
    c.leaf = true;
    c.values.assign(l->buffer().data(), l->buffer().data() + Leaf::SIZE);
    c.mask = l->getValueMask();
  } else {
    c.value = t.getValue(o);
  }
  if (maskTree) {
    c.maskKept = true;
    if (const Leaf* l = maskTree->probeConstLeaf(o))
      c.maskValues.assign(l->buffer().data(), l->buffer().data() + Leaf::SIZE);
  }
  chunks_.push_back(std::move(c));
}

void ChunkRecord::clear() {
  chunks_.clear();
  seen_.clear();
}

size_t ChunkRecord::bytes() const {
  size_t n = 0;
  for (const Chunk& c : chunks_)
    n += sizeof(Chunk) + (c.values.size() + c.maskValues.size()) * sizeof(float) + 48;  // + the map's node
  return n;
}

Volume::~Volume() = default;

Volume::Volume(float voxel) : voxel_(voxel) {
  std::call_once(g_init, [] { openvdb::initialize(); });
  grid_ = openvdb::FloatGrid::create(kBand);
  grid_->setTransform(openvdb::math::Transform::createLinearTransform(voxel));
  grid_->setGridClass(openvdb::GRID_LEVEL_SET);
  grid_->setName("clay");
  mask_ = openvdb::FloatGrid::create(0.0f);
  mask_->setTransform(grid_->transform().copy());
  mask_->setName("mask");
}

void Volume::own_buffers() { bufs_ = std::make_unique<Buffers>(); }

StepTiming Volume::apply(const Step& s) { return run(&s, 1); }

StepTiming Volume::apply_stroke(const std::vector<Step>& dabs) { return units(dabs, nullptr, nullptr); }

StepTiming Volume::apply_stroke_shared(const std::vector<Step>& dabs, Buffers& bufs, std::shared_mutex& lock) {
  return units(dabs, &bufs, &lock);
}

// Where the stroke began, for a stroke applied by apply_stroke (thread-local: a parallel replay runs several strokes
// at once on one volume); a live stroke uses live_.
namespace {
thread_local ChunkRecord* tl_start = nullptr;
}

StepTiming Volume::units(const std::vector<Step>& dabs, Buffers* bufs, std::shared_mutex* lock) {
  // A stroke, dab after dab, exactly as it was sculpted live (Volume::dab): one dab, one re-levelling. CL2b: units of
  // several dabs between re-levellings (and a whole stroke as one unit without accumulate) gave a different clay from
  // the one drawn live: a person saw a ridge, and letting go left half of it, or nothing. Live = end = replay now holds
  // by construction. The chunks as they were when the stroke began are kept aside for Build up off (as live_ is live).
  StepTiming t;
  ChunkRecord start;
  start.on = true;
  ChunkRecord* const before = tl_start;
  tl_start = &start;
  try {
    for (const Step& d : dabs) {
      const StepTiming u = run(&d, 1, bufs, lock);
      t.ms += u.ms;
      t.voxels += u.voxels;
    }
  } catch (...) {
    tl_start = before;
    throw;
  }
  tl_start = before;
  return t;
}

void Volume::begin_stroke() {
  live_.clear();
  live_.on = true;
}

StepTiming Volume::dab(const Step& s) { return run(&s, 1); }

StepTiming Volume::end_stroke(const std::vector<Step>& dabs) {
  const auto t0 = std::chrono::steady_clock::now();
  live_.on = false;
  // 3d-v3: the live clay IS the stroke applied as one unit (units() runs the same dabs one by one from the same start,
  // CL2b), so letting go keeps it: no put-back and no second pass over every dab (the release pause), and no block
  // is re-meshed. ROSTRUM3D_CLAY_VERIFY=1 still does both and says on stderr when the two clays differ.
  static const bool verify = std::getenv("ROSTRUM3D_CLAY_VERIFY") != nullptr;
  StepTiming t;
  if (verify) {
    const uint64_t liveHash = hash();
    put_back(live_);  // the clay as it was before the stroke (the record, if one is on, already holds these chunks)
    live_.clear();
    t = apply_stroke(dabs);
    if (hash() != liveHash) std::fprintf(stderr, "clay: live stroke != replay (%zu dabs)\n", dabs.size());
  }
  live_.clear();
  t.ms = ms_since(t0);
  return t;
}

void Volume::cancel_stroke() {
  live_.on = false;
  put_back(live_);
  live_.clear();
}

void Volume::record_into(ChunkRecord* rec) {
  record_ = rec;
  if (rec) rec->on = true;
}

void Volume::restore(const ChunkRecord& rec) { put_back(rec); }

void Volume::note_change(const Coord& o) {
  constexpr size_t kMostChanges = size_t(1) << 20;  // ~12 MB of origins; past it a coarse copy is made again
  if (changesAll_) return;
  changes_.push_back(o);
  if (changes_.size() > kMostChanges) {
    changesAll_ = true;
    std::vector<Coord>().swap(changes_);
  }
}

bool Volume::take_changes(std::vector<Coord>& out) {
  out.clear();
  const bool listed = !changesAll_;
  out.swap(changes_);
  changesAll_ = false;
  if (!listed) out.clear();
  return listed;
}

void Volume::keep(const Coord& o) {
  note_change(o);
  (tl_start ? *tl_start : live_).keep(grid_->tree(), &mask_->tree(), o);
  if (record_) record_->keep(grid_->tree(), &mask_->tree(), o);
}

void Volume::put_back(const ChunkRecord& rec) {
  Tree& tree = grid_->tree();
  Tree& maskTree = mask_->tree();
  for (const ChunkRecord::Chunk& c : rec.chunks()) {
    if (c.leaf) {
      Leaf* l = tree.touchLeaf(c.o);
      std::memcpy(l->buffer().data(), c.values.data(), sizeof(float) * Leaf::SIZE);
      l->setValueMask(c.mask);
    } else {
      tree.addTile(1, c.o, c.value, false);
    }
    if (c.maskKept) {  // the mask chunk as it was: its leaf, or no leaf
      if (!c.maskValues.empty()) {
        Leaf* l = maskTree.touchLeaf(c.o);
        std::memcpy(l->buffer().data(), c.maskValues.data(), sizeof(float) * Leaf::SIZE);
        l->setValuesOn();
      } else if (maskTree.probeConstLeaf(c.o)) {
        maskTree.addTile(1, c.o, 0.0f, false);
      }
    }
    note_change(c.o);
    const int lo[3] = {c.o[0], c.o[1], c.o[2]}, hi[3] = {c.o[0] + 7, c.o[1] + 7, c.o[2] + 7};
    mark_dirty(lo, hi);  // chunk by chunk, as a step marks them
  }
}

void Volume::mark_dirty(const int lo[3], const int hi[3]) {
  // block b reads voxels [32b - 2, 32b + 33] (normals included)
  for (int bz = floor_div(lo[2] - 2, kBlock); bz <= floor_div(hi[2] + 2, kBlock); ++bz)
    for (int by = floor_div(lo[1] - 2, kBlock); by <= floor_div(hi[1] + 2, kBlock); ++by)
      for (int bx = floor_div(lo[0] - 2, kBlock); bx <= floor_div(hi[0] + 2, kBlock); ++bx)
        dirty_.insert(BlockKey{bx, by, bz});
  // part q reads voxels [16q - 2, 16q + 17]
  for (int bz = floor_div(lo[2] - 2, kPart); bz <= floor_div(hi[2] + 2, kPart); ++bz)
    for (int by = floor_div(lo[1] - 2, kPart); by <= floor_div(hi[1] + 2, kPart); ++by)
      for (int bx = floor_div(lo[0] - 2, kPart); bx <= floor_div(hi[0] + 2, kPart); ++bx)
        dirtyParts_.insert(BlockKey{bx, by, bz});
}

std::set<BlockKey> Volume::take_dirty() {
  std::set<BlockKey> d;
  d.swap(dirty_);
  dirtyParts_.clear();
  return d;
}

std::set<BlockKey> Volume::take_dirty_parts() {
  std::set<BlockKey> d;
  d.swap(dirtyParts_);
  dirty_.clear();
  return d;
}

StepTiming Volume::run(const Step* steps, size_t n, Buffers* bufs, std::shared_mutex* lock) {
  const auto t0 = std::chrono::steady_clock::now();
  Buffers& S = bufs ? *bufs : bufs_ ? *bufs_ : buffers();
  GridLock<true> readLock(lock);  // (a parallel replay) the grid is read up to the dabs, written after them
  const float iv = 1.0f / voxel_;
  auto vox = [&](V3 p) { return V3{p.x * iv, p.y * iv, p.z * iv}; };
  const bool piece = steps[0].kind == Kind::Piece;  // a piece is always alone (n == 1)
  const Step& s0 = steps[0];

  // the shapes (voxel units), mirrored copies included
  std::vector<Shape> pieceShapes;
  std::vector<std::vector<DabShape>> dabShapes(n);
  std::vector<float> shift(n, 0), reachOf(n, 0);
  float k = 0;
  struct NearBall {  // a piece this one doesn't touch (voxel units): within k of it the blend eases down to `most`
    V3 c;
    float r, most;
  };
  std::vector<NearBall> nearBalls;
  if (piece) {
    if (!s0.field) {
      const float r = s0.radius * iv;
      pieceShapes.push_back({vox(s0.a), vox(s0.b), r});
      if (s0.mirror) pieceShapes.push_back({vox(mirror_x(s0.a)), vox(mirror_x(s0.b)), r});
    }
    // a blend joins the piece to clay already there; on an empty clay (a new clay's first ball) there is nothing to
    // join, so none: the ball is its exact size, and only its thin shell is worked (CL1b: with the blend, a new 10 cm
    // clay widened and re-levelled a 30-million-voxel box and took 5 s to appear)
    k = grid_->tree().empty() ? 0.0f : s0.blend * iv;
    if (k > 0 && s0.pairs)
      for (const auto& q : *s0.pairs)
        if (q[4] * iv < k) nearBalls.push_back({V3{q[0] * iv, q[1] * iv, q[2] * iv}, q[3] * iv, q[4] * iv});
  } else {
    for (size_t j = 0; j < n; ++j) {
      const Step& s = steps[j];
      const float r = s.radius * iv;
      V3 bvec = s.op == Op::Pull ? vox(s.b) : s.b;  // Pull: a vector in voxels (at most kDispCap); Crease: a direction
      if (s.op == Op::Pull && len3(bvec) > kDispCap) bvec = mul(bvec, kDispCap / len3(bvec));
      dabShapes[j].push_back({vox(s.a), s.n, bvec, r});
      if (s.mirror) dabShapes[j].push_back({vox(mirror_x(s.a)), mirror_x(s.n), mirror_x(bvec), r});
      shift[j] = dab_shift(s, iv);
      reachOf[j] = r + kBand + 1 + shift[j];
    }
  }
  // big dabs: on a 2x coarser copy of the band (clay_coarse.cpp)
  if (!piece && coarse_ && coarse_dab(s0, iv)) {
    readLock.unlock();
    CoarseUnit cu;
    cu.tree = &grid_->tree();
    cu.mask = &mask_->tree();
    cu.bufs = &S;
    cu.start = tl_start ? tl_start : &live_;
    cu.lock = lock;
    cu.steps = steps;
    cu.n = n;
    cu.shapes = &dabShapes;
    cu.shift = &shift;
    cu.keep = [this](const Coord& o) { keep(o); };
    cu.dirty = [this](const int* lo, const int* hi) { mark_dirty(lo, hi); };
    run_coarse(cu);
    StepTiming t;
    t.voxels = cu.written * 512;
    t.ms = ms_since(t0);
    return t;
  }
  // how wide the distances must be before the step: a blend reads them up to k past the band (a dab moves the
  // surface less than the trusted band and needs nothing wider)
  const float wpre = piece && k > 0 ? kBand + std::min(k, kBlendCap) + 1.5f : 0.0f;
  const int rch = int(std::ceil(std::max(wpre, kBand) / 8.0f));
  const int nearR = (!piece && n > 1) ? 2 : 1;  // a unit of dabs can move the surface up to a chunk
  float lo[3] = {1e30f, 1e30f, 1e30f}, hi[3] = {-1e30f, -1e30f, -1e30f};
  auto grow = [&](V3 p, float r) {
    lo[0] = std::min(lo[0], p.x - r), lo[1] = std::min(lo[1], p.y - r), lo[2] = std::min(lo[2], p.z - r);
    hi[0] = std::max(hi[0], p.x + r), hi[1] = std::max(hi[1], p.y + r), hi[2] = std::max(hi[2], p.z + r);
  };
  if (piece && s0.field) {  // CL3: a drawn / spun / item shape (clay_shapes.h), and its mirrored copy
    const Field& f = *s0.field;
    grow(f.lo, k + kBand + 1);
    grow(f.hi, k + kBand + 1);
    if (s0.mirror) {
      grow(V3{-f.hi.x, f.lo.y, f.lo.z}, k + kBand + 1);
      grow(V3{-f.lo.x, f.hi.y, f.hi.z}, k + kBand + 1);
    }
  } else if (piece) {
    for (const Shape& sh : pieceShapes) {
      grow(sh.a, sh.r + k + kBand + 1);
      grow(sh.b, sh.r + k + kBand + 1);
    }
  } else {
    for (size_t j = 0; j < n; ++j)
      for (const DabShape& d : dabShapes[j]) grow(d.c, reachOf[j]);
  }
  const int ring = 8 * (std::max(rch, nearR) + 1);
  const Coord ilo(floor8(int(std::floor(lo[0]))), floor8(int(std::floor(lo[1]))), floor8(int(std::floor(lo[2]))));
  const Coord ihi(ceil8(int(std::ceil(hi[0])) + 1), ceil8(int(std::ceil(hi[1])) + 1), ceil8(int(std::ceil(hi[2])) + 1));
  Box b;
  b.lo = ilo - Coord(ring);
  b.nx = ihi.x() - ilo.x() + 2 * ring;
  b.ny = ihi.y() - ilo.y() + 2 * ring;
  b.nz = ihi.z() - ilo.z() + 2 * ring;
  b.cnx = b.nx / 8;
  b.cny = b.ny / 8;
  b.cnz = b.nz / 8;
  // CL7b: a step's box is worked in 7 buffers of 4 bytes a grain, allocated whole. Past this it fails loudly, saying
  // why, instead of the bare "bad allocation" a 0.2 mm drawn shape gave (21 GB a buffer)
  constexpr double kMostBoxBytes = 4.0e9;
  const double boxBytes = 28.0 * double(b.size());
  if (boxBytes > kMostBoxBytes) {
    char msg[320];
    std::snprintf(msg, sizeof msg,
                  "clay: this step at %.2g mm detail needs %.1f GB of work memory (the most is %.0f GB). Set a coarser "
                  "detail (Detail: Fixed, a bigger size), or let Detail follow the camera (it keeps a clay within this)",
                  voxel_ * 1e3, boxBytes / 1e9, kMostBoxBytes / 1e9);
    throw Error(msg);
  }
  S.fit(b.size());
  float* V = S.a.get();
  float* NX = S.b.get();
  float* O = S.orig.get();
  float* A = S.after.get();
  float* St = S.start.get();  // the clay where the stroke began (accumulate off)
  uint8_t* F = S.fixed.get();
  const int nch = b.chunks();
  Tree& tree = grid_->tree();

  const double tpA = prof_on() ? ms_since(t0) : 0;
  // A. which chunks hold a leaf (the surface is only ever near one); the others are one value
  std::vector<uint8_t> leaf(nch);
  std::vector<float> uval(nch);
  tbb::parallel_for(0, nch, [&](int ci) {
    int x, y, z;
    b.corner(ci, x, y, z);
    const Coord o = b.lo + Coord(x, y, z);
    leaf[ci] = tree.probeConstLeaf(o) != nullptr;
    uval[ci] = leaf[ci] ? 0.0f : tree.getValue(o);
  });
  const std::vector<uint8_t> nearLeaf = dilate(leaf, b.cnx, b.cny, b.cnz, nearR);

  // B. the chunks the step works on, and the ones a piece turns into one value (wholly inside it)
  const int rc = ring / 8;
  const float hd = 6.1f;  // a chunk's centre to its farthest voxel
  std::vector<uint8_t> work(nch, 0);
  std::vector<int8_t> whole(nch, 0);  // -1 / +1: becomes all inside / all outside
  tbb::parallel_for(0, nch, [&](int ci) {
    const int cx = ci % b.cnx, cy = (ci / b.cnx) % b.cny, cz = ci / (b.cnx * b.cny);
    if (cx < rc || cy < rc || cz < rc || cx >= b.cnx - rc || cy >= b.cny - rc || cz >= b.cnz - rc) return;
    const V3 c{b.lo.x() + 8.0f * cx + 3.5f, b.lo.y() + 8.0f * cy + 3.5f, b.lo.z() + 8.0f * cz + 3.5f};
    if (piece) {
      float d = 1e30f;
      if (s0.field) d = FieldEval(*s0.field, s0.mirror)(c);
      for (const Shape& sh : pieceShapes) d = std::min(d, seg_dist(c, sh.a, sh.b) - sh.r);
      if (d < -(hd + kBand + 1)) {
        const float target = s0.op == Op::Add ? -kBand : kBand;
        if (leaf[ci] || uval[ci] != target) whole[ci] = s0.op == Op::Add ? -1 : 1;
      } else if (d < hd + k + kBand + 1) {
        work[ci] = 1;
      }
    } else if (nearLeaf[ci]) {
      for (size_t j = 0; j < n && !work[ci]; ++j)
        for (const DabShape& d : dabShapes[j]) {
          const V3 e = vsub(c, d.c);
          const float lim = reachOf[j] + hd;
          if (vdot(e, e) < lim * lim) work[ci] = 1;
        }
    }
  });
  const std::vector<int> workList = listed(work);
  const std::vector<uint8_t> pre = wpre > 0 ? dilate(work, b.cnx, b.cny, b.cnz, rch) : work;
  const std::vector<int> preList = listed(pre);
  const std::vector<int> extList = listed(dilate(pre, b.cnx, b.cny, b.cnz, 1));

  std::vector<uint8_t> touched(nch, 0);  // chunks a dab worked on (only they are written back)
  float* M = nullptr;                     // the mask, when the unit uses one (E0)
  std::vector<uint8_t> maskTouched;       // chunks a Mask dab painted (their mask is written back)
  bool needStart = false;
  for (size_t j = 0; j < n && !piece; ++j) needStart |= !steps[j].accumulate;

  const double tpC = prof_on() ? ms_since(t0) : 0;
  double tpE = 0;
  // 3d-v4: where the stroke began, taken here on the calling thread. C reads it inside a parallel loop, and read there
  // tl_start was the worker thread's own (null): a replay's chunks done by other threads used live_ (off: none) and
  // took the current values as the start, so a Build up off stroke replayed differently from live, and differently
  // run to run ("live stroke != replay" with ROSTRUM3D_CLAY_VERIFY=1)
  const ChunkRecord* const startRec = tl_start ? tl_start : &live_;
  // C. fill the listed chunks from the grid (and, for strokes without accumulate, where the stroke began: a live
  //    stroke's chunks as they were before its first dab, kept aside)
  par(extList, [&](int ci) {
    int x, y, z;
    b.corner(ci, x, y, z);
    if (leaf[ci]) {
      const float* d = tree.probeConstLeaf(b.lo + Coord(x, y, z))->buffer().data();
      b.each(ci, [&](int xx, int yy, int zz, size_t i) { V[i] = d[leaf_offset(xx, yy, zz)]; });
    } else {
      const float u = uval[ci];
      b.each(ci, [&](int, int, int, size_t i) { V[i] = u; });
    }
    if (needStart) {
      const ChunkRecord::Chunk* kept = startRec->find(b.lo + Coord(x, y, z));
      if (!kept) b.copy(ci, V, St);
      else if (kept->leaf) b.each(ci, [&](int xx, int yy, int zz, size_t i) { St[i] = kept->values[leaf_offset(xx, yy, zz)]; });
      else b.each(ci, [&](int, int, int, size_t i) { St[i] = kept->value; });
    }
  });

  if (piece) {
    readLock.unlock();
    // D. widen the distances to what the blend reads (the stored band is trusted)
    if (wpre > 0) {
      par(extList, [&](int ci) { b.each(ci, [&](int, int, int, size_t i) { F[i] = std::fabs(V[i]) < kBand - 0.5f; }); });
      relevel(b, V, NX, F, wpre, extList, extList, preList);  // swaps V / NX: V stays the current values
    }
    // E. the piece, then back to the stored band: unchanged band voxels stay; changed ones next to the surface are
    //    re-scaled to a distance by their own gradient (value / |gradient|, central differences: smooth, no
    //    voxel-scale ripples); the rest is re-levelled
    const auto P = [&](int x, int y, int z) { return V3{float(b.lo.x() + x), float(b.lo.y() + y), float(b.lo.z() + z)}; };
    par(extList, [&](int ci) { b.copy(ci, V, O); });
    par(extList, [&](int ci) {
      std::optional<FieldEval> fe;  // CL3: one reader per chunk (an item's caches the grid's nodes)
      if (s0.field) fe.emplace(*s0.field, s0.mirror);
      // the near balls that can reach this chunk (a chunk's centre to its farthest voxel is hd)
      int cx, cy, cz;
      b.corner(ci, cx, cy, cz);
      const V3 cc = add(P(cx, cy, cz), V3{3.5f, 3.5f, 3.5f});
      std::vector<const NearBall*> nb;
      for (const NearBall& q : nearBalls)
        if (len(sub(cc, q.c)) - q.r < k + hd) nb.push_back(&q);
      b.each(ci, [&](int x, int y, int z, size_t i) {
        const V3 p = P(x, y, z);
        float d = 1e30f;
        if (fe) d = (*fe)(p);
        for (const Shape& sh : pieceShapes) d = std::min(d, seg_dist(p, sh.a, sh.b) - sh.r);
        float kp = k;  // the blend here: as asked, easing down to a near ball's most within k of it (smooth in p)
        for (const NearBall* q : nb) {
          const float t = std::max(0.0f, len(sub(p, q->c)) - q->r) / k;
          if (t < 1.0f) kp = std::min(kp, q->most + (k - q->most) * t * t * (3.0f - 2.0f * t));
        }
        if (s0.op == Op::Add) V[i] = smin(O[i], d, kp);
        else if (s0.op == Op::Carve) V[i] = -smin(-O[i], d, kp);
      });
    });
    par(extList, [&](int ci) { b.copy(ci, V, A); });
    par(extList, [&](int ci) {  // seeds and fixed voxels, reading neighbours from A (a copy of V)
      b.each(ci, [&](int x, int y, int z, size_t i) {
        const float v = A[i];
        uint8_t f = 0;
        if (v == O[i]) {
          f = std::fabs(v) < kBand - 1.0f;
        } else if (x > 0 && y > 0 && z > 0 && x < b.nx - 1 && y < b.ny - 1 && z < b.nz - 1) {
          const float xm = A[b.at(x - 1, y, z)], xp = A[b.at(x + 1, y, z)];
          const float ym = A[b.at(x, y - 1, z)], yp = A[b.at(x, y + 1, z)];
          const float zm = A[b.at(x, y, z - 1)], zp = A[b.at(x, y, z + 1)];
          const bool crossing = (xm < 0) != (v < 0) || (xp < 0) != (v < 0) || (ym < 0) != (v < 0) ||
                                (yp < 0) != (v < 0) || (zm < 0) != (v < 0) || (zp < 0) != (v < 0);
          if (crossing) {
            const float gx = 0.5f * (xp - xm), gy = 0.5f * (yp - ym), gz = 0.5f * (zp - zm);
            const float g = std::min(2.0f, std::max(0.5f, std::sqrt(gx * gx + gy * gy + gz * gz)));
            V[i] = v / g;
            f = 2;
          }
        }
        F[i] = f;
      });
    });
    relevel(b, V, NX, F, kBand, extList, extList, workList);
  } else {
    // E0. the mask, where the unit paints or reads one (a clay with no mask and no Mask dab: none, as in CL1)
    bool painting = false;
    for (size_t j = 0; j < n; ++j) painting |= steps[j].op == Op::Mask;
    if (painting || has_mask()) {
      M = S.mask.get();
      maskTouched.assign(nch, 0);
      const Tree& mt = mask_->tree();
      par(extList, [&](int ci) {
        int x, y, z;
        b.corner(ci, x, y, z);
        if (const Leaf* l = mt.probeConstLeaf(b.lo + Coord(x, y, z))) {
          const float* d = l->buffer().data();
          b.each(ci, [&](int xx, int yy, int zz, size_t i) { M[i] = d[leaf_offset(xx, yy, zz)]; });
        } else {
          b.each(ci, [&](int, int, int, size_t i) { M[i] = 0.0f; });
        }
      });
    }
    readLock.unlock();
    // E. dabs one after another, each over its own narrow band (clay_band.cpp)
    DabUnit u;
    u.b = &b;
    u.V = V;
    u.NX = NX;
    u.St = St;
    u.steps = steps;
    u.n = n;
    u.shapes = &dabShapes;
    u.reach = &reachOf;
    u.shift = &shift;
    u.leaf = &leaf;
    u.work = &work;
    u.extList = &extList;
    u.touched = &touched;
    u.M = M;
    u.maskTouched = &maskTouched;
    tpE = prof_on() ? ms_since(t0) : 0;
    run_dabs(u);
  }

  const double tpG = prof_on() ? ms_since(t0) : 0;
  // G. write back: worked chunks (uniform ones become tiles), and the chunks a piece filled or emptied
  std::vector<int8_t> cls(nch, 2);  // +1 all outside, -1 all inside, 0 mixed, 2 not written
  std::vector<int> writeList;
  if (piece) writeList = workList;
  else
    for (int ci : workList)
      if (touched[ci]) writeList.push_back(ci);
  par(writeList, [&](int ci) {
    bool allOut = true, allIn = true;
    b.each(ci, [&](int, int, int, size_t i) {
      allOut &= V[i] >= kBand;
      allIn &= V[i] <= -kBand;
    });
    cls[ci] = allOut ? 1 : allIn ? -1 : 0;
  });
  for (int ci = 0; ci < nch; ++ci)
    if (whole[ci]) cls[ci] = whole[ci];
  GridLock<false> writeLock(lock);
  std::vector<Leaf*> leaves(nch, nullptr);
  std::vector<int> mixed;
  // the blocks whose surface may have changed are marked chunk by chunk (3d-v3: a mirrored dab's bounding box marked
  // every block between its two sides, 54 a dab)
  auto dirty_chunk = [&](const Coord& o) {
    const int lo[3] = {o[0], o[1], o[2]}, hi[3] = {o[0] + 7, o[1] + 7, o[2] + 7};
    mark_dirty(lo, hi);
  };
  for (int ci = 0; ci < nch; ++ci) {
    if (cls[ci] == 2) continue;
    int x, y, z;
    b.corner(ci, x, y, z);
    const Coord o = b.lo + Coord(x, y, z);
    if (cls[ci] == 0) {
      keep(o);
      leaves[ci] = tree.touchLeaf(o);
      mixed.push_back(ci);
    } else {
      const float val = cls[ci] * kBand;
      if (!leaf[ci] && uval[ci] == val) continue;  // already that tile: nothing changed here
      keep(o);
      tree.addTile(1, o, val, false);
    }
    dirty_chunk(o);
  }
  par(mixed, [&](int ci) {
    Leaf* lf = leaves[ci];
    b.each(ci, [&](int x, int y, int z, size_t i) {
      const float v = V[i];
      const int off = leaf_offset(x, y, z);
      if (std::fabs(v) < kBand) lf->setValueOn(off, v);
      else lf->setValueOff(off, sgn(v) * kBand);
    });
  });

  // G2. the mask chunks Mask dabs painted: a leaf, or no leaf when all 0 (after the clay's: a chunk both write is
  //     kept, clay and mask, before either changes)
  if (M) {
    Tree& mt = mask_->tree();
    std::vector<int> maskList;
    for (int ci : workList)
      if (maskTouched[ci]) maskList.push_back(ci);
    std::vector<uint8_t> blank(nch, 0);
    par(maskList, [&](int ci) {
      bool zero = true;
      b.each(ci, [&](int, int, int, size_t i) { zero &= M[i] == 0.0f; });
      blank[ci] = zero;
    });
    std::vector<Leaf*> mleaves(nch, nullptr);
    std::vector<int> mfill;
    for (int ci : maskList) {
      int x, y, z;
      b.corner(ci, x, y, z);
      const Coord o = b.lo + Coord(x, y, z);
      if (blank[ci]) {
        if (!mt.probeConstLeaf(o)) continue;  // no mask here before either
        keep(o);
        mt.addTile(1, o, 0.0f, false);
      } else {
        keep(o);
        mleaves[ci] = mt.touchLeaf(o);
        mfill.push_back(ci);
      }
      dirty_chunk(o);
    }
    par(mfill, [&](int ci) {
      Leaf* lf = mleaves[ci];
      b.each(ci, [&](int x, int y, int z, size_t i) { lf->setValueOn(leaf_offset(x, y, z), M[i]); });
    });
  }

  writeLock.unlock();

  // a piece's buffers (a big box, wide blends) can be hundreds of MB: give them back rather than keep them for the dabs
  if (piece || b.size() > (size_t(16) << 20)) S.release();

  StepTiming t;
  t.voxels = writeList.size() * 512;
  if (prof_on() && !piece)
    std::fprintf(stderr, "clayprof box=%.2f setup=%.2f fill=%.2f dabs=%.2f write=%.2f nch=%d work=%zu ext=%zu written=%zu\n",
                 tpA, tpC - tpA, tpE - tpC, tpG - tpE, ms_since(t0) - tpG, nch, workList.size(), extList.size(), writeList.size());
  t.ms = ms_since(t0);
  return t;
}

}  // namespace r3d::clay
