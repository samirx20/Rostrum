// Clay: reading the volume (clay_volume.h): block surfaces, sampling, cast and snap, the hash, the .vdb cache file.
// Moved from proofs/3d-clay (clay.cpp).
#include <openvdb/io/File.h>
#include <tbb/parallel_for.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <set>
#include <stdexcept>

#include "clay_box.h"
#include "clay_volume.h"

namespace r3d::clay {

using namespace detail;

void Volume::mesh(const BlockKey& k, BlockMesh& out) const {
  // thread-local buffers, filled without a nested parallel loop (a nested loop let TBB run another block on this
  // thread while it waited, reusing these buffers: holes at block seams, different every run)
  thread_local std::vector<float> wide(size_t(kWide) * kWide * kWide), dense(size_t(kDense) * kDense * kDense);
  read_region(grid_->tree(), Coord(k.x * kBlock - 2, k.y * kBlock - 2, k.z * kBlock - 2), kWide, kWide, kWide,
              wide.data());
  for (int z = 0; z < kDense; ++z)
    for (int y = 0; y < kDense; ++y)
      std::memcpy(&dense[size_t(kDense) * (y + size_t(kDense) * z)],
                  &wide[1 + size_t(kWide) * ((y + 1) + size_t(kWide) * (z + 1))], kDense * sizeof(float));
  // the mask on the dense lattice, only when some of it is near this block (else no mask channel: no primvar)
  const float* maskDense = nullptr;
  if (has_mask()) {
    thread_local std::vector<float> m(size_t(kDense) * kDense * kDense);
    read_region(mask_->tree(), Coord(k.x * kBlock - 1, k.y * kBlock - 1, k.z * kBlock - 1), kDense, kDense, kDense,
                m.data());
    if (std::any_of(m.begin(), m.end(), [](float v) { return v != 0.0f; })) maskDense = m.data();
  }
  mesh_block(dense.data(), wide.data(), k, voxel_, out, maskDense);
}

void Volume::mesh_part(const BlockKey& q, BlockMesh& out) const {
  // as mesh(), reading only the octant's samples (clay_mesh.h): wide [16 o, 16 o + 19], dense [16 o, 16 o + 17]
  const BlockKey k{floor_div(q.x, 2), floor_div(q.y, 2), floor_div(q.z, 2)};
  const int part = (q.x & 1) | ((q.y & 1) << 1) | ((q.z & 1) << 2);
  const int o[3] = {(q.x & 1) * kPart, (q.y & 1) * kPart, (q.z & 1) * kPart};
  constexpr int nw = kPart + 4, nd = kPart + 2;
  thread_local std::vector<float> wide(size_t(kWide) * kWide * kWide), dense(size_t(kDense) * kDense * kDense),
      sub(size_t(nw) * nw * nw);
  read_region(grid_->tree(), Coord(k.x * kBlock - 2 + o[0], k.y * kBlock - 2 + o[1], k.z * kBlock - 2 + o[2]), nw, nw,
              nw, sub.data());
  for (int z = 0; z < nw; ++z)
    for (int y = 0; y < nw; ++y)
      std::memcpy(&wide[o[0] + size_t(kWide) * ((o[1] + y) + size_t(kWide) * (o[2] + z))],
                  &sub[size_t(nw) * (y + size_t(nw) * z)], nw * sizeof(float));
  for (int z = 0; z < nd; ++z)
    for (int y = 0; y < nd; ++y)
      std::memcpy(&dense[o[0] + size_t(kDense) * ((o[1] + y) + size_t(kDense) * (o[2] + z))],
                  &wide[o[0] + 1 + size_t(kWide) * ((o[1] + y + 1) + size_t(kWide) * (o[2] + z + 1))],
                  nd * sizeof(float));
  const float* maskDense = nullptr;
  if (has_mask()) {
    thread_local std::vector<float> m(size_t(kDense) * kDense * kDense), ms(size_t(nd) * nd * nd);
    read_region(mask_->tree(), Coord(k.x * kBlock - 1 + o[0], k.y * kBlock - 1 + o[1], k.z * kBlock - 1 + o[2]), nd,
                nd, nd, ms.data());
    if (std::any_of(ms.begin(), ms.end(), [](float v) { return v != 0.0f; })) {
      for (int z = 0; z < nd; ++z)
        for (int y = 0; y < nd; ++y)
          std::memcpy(&m[o[0] + size_t(kDense) * ((o[1] + y) + size_t(kDense) * (o[2] + z))],
                      &ms[size_t(nd) * (y + size_t(nd) * z)], nd * sizeof(float));
      maskDense = m.data();
    }
  }
  mesh_block(dense.data(), wide.data(), k, voxel_, out, maskDense, part);
}

std::vector<BlockKey> Volume::all_blocks() const {
  std::set<BlockKey> s;
  for (auto it = grid_->tree().cbeginLeaf(); it; ++it) {
    if (it->isEmpty()) continue;  // no active voxel: no surface
    // the leaf's block, and the blocks just below it on each axis: an edge into this leaf can start one voxel
    // before it, and the block of an edge's start owns its quad (clay_mesh.h)
    const Coord o = it->origin();
    const int bx = floor_div(o.x(), kBlock), by = floor_div(o.y(), kBlock), bz = floor_div(o.z(), kBlock);
    s.insert(BlockKey{bx, by, bz});
    s.insert(BlockKey{floor_div(o.x() - 1, kBlock), by, bz});
    s.insert(BlockKey{bx, floor_div(o.y() - 1, kBlock), bz});
    s.insert(BlockKey{bx, by, floor_div(o.z() - 1, kBlock)});
  }
  return {s.begin(), s.end()};
}

float Volume::sample(const V3& p) const {
  const float x = p.x / voxel_, y = p.y / voxel_, z = p.z / voxel_;
  const int ix = int(std::floor(x)), iy = int(std::floor(y)), iz = int(std::floor(z));
  const float fx = x - ix, fy = y - iy, fz = z - iz;
  float c[8];
  read_region(grid_->tree(), Coord(ix, iy, iz), 2, 2, 2, c);
  const float c00 = c[0] + (c[1] - c[0]) * fx, c10 = c[2] + (c[3] - c[2]) * fx;
  const float c01 = c[4] + (c[5] - c[4]) * fx, c11 = c[6] + (c[7] - c[6]) * fx;
  const float c0 = c00 + (c10 - c00) * fy, c1 = c01 + (c11 - c01) * fy;
  return c0 + (c1 - c0) * fz;
}

bool Volume::snap(const V3& p, V3& on, V3& normal) const {
  // march along the field towards the surface: distance steps while far, then Newton steps along the gradient
  V3 q = p;
  const float h = 0.5f * voxel_;
  for (int it = 0; it < 400; ++it) {
    const float v = sample(q);
    const float gx = (sample({q.x + h, q.y, q.z}) - sample({q.x - h, q.y, q.z}));
    const float gy = (sample({q.x, q.y + h, q.z}) - sample({q.x, q.y - h, q.z}));
    const float gz = (sample({q.x, q.y, q.z + h}) - sample({q.x, q.y, q.z - h}));
    const float gl = std::sqrt(gx * gx + gy * gy + gz * gz);
    if (gl < 1e-6f) return false;  // far from any surface (the field is flat out there)
    normal = {gx / gl, gy / gl, gz / gl};
    if (std::fabs(v) < 0.02f) {
      on = q;
      return true;
    }
    const float step = std::max(-kBand + 0.5f, std::min(kBand - 0.5f, v)) * voxel_;
    q = {q.x - normal.x * step, q.y - normal.y * step, q.z - normal.z * step};
  }
  return false;
}

bool Volume::cast(const V3& o, const V3& d, float maxDist, V3& on, V3& normal) const {
  float prev = sample(o);
  if (prev <= 0) return false;  // starts inside the clay
  // march only where the clay is: the ray's part inside the leaves' box (a little wider); outside it the field is
  // flat at +kBand and nothing can be hit
  openvdb::CoordBBox box;
  if (!grid_->tree().evalLeafBoundingBox(box)) return false;  // no clay
  const float pad = (kBand + 2) * voxel_;
  float t0 = 0, t1 = maxDist;
  const float oo[3] = {o.x, o.y, o.z}, dd[3] = {d.x, d.y, d.z};
  for (int a = 0; a < 3; ++a) {
    const float lo = box.min()[a] * voxel_ - pad, hi = (box.max()[a] + 1) * voxel_ + pad;
    if (std::fabs(dd[a]) < 1e-12f) {
      if (oo[a] < lo || oo[a] > hi) return false;
      continue;
    }
    float ta = (lo - oo[a]) / dd[a], tb = (hi - oo[a]) / dd[a];
    if (ta > tb) std::swap(ta, tb);
    t0 = std::max(t0, ta);
    t1 = std::min(t1, tb);
  }
  if (t0 > t1) return false;
  float t = t0;
  if (t > 0) prev = sample({o.x + d.x * t, o.y + d.y * t, o.z + d.z * t});
  while (t < t1) {
    const float step = std::max(0.5f, 0.9f * std::fabs(prev)) * voxel_;
    const float tn = t + step;
    const V3 q{o.x + d.x * tn, o.y + d.y * tn, o.z + d.z * tn};
    const float v = sample(q);
    if (v <= 0) {  // crossed: the zero between t and tn, linearly, then onto the surface
      const float th = t + step * prev / (prev - v);
      return snap({o.x + d.x * th, o.y + d.y * th, o.z + d.z * th}, on, normal);
    }
    t = tn;
    prev = v;
  }
  return false;
}

uint64_t Volume::hash() const {
  uint64_t h = 1469598103934665603ull;  // FNV-1a over the leaves in tree order
  auto mix = [&](const void* p, size_t n) {
    const auto* c = static_cast<const unsigned char*>(p);
    for (size_t i = 0; i < n; ++i) {
      h ^= c[i];
      h *= 1099511628211ull;
    }
  };
  for (auto it = grid_->tree().cbeginLeaf(); it; ++it) {
    const Coord o = it->origin();
    mix(o.data(), sizeof(int) * 3);
    mix(it->buffer().data(), sizeof(float) * Leaf::SIZE);
    const auto& m = it->getValueMask();
    for (openvdb::Index w = 0; w < Leaf::NodeMaskType::WORD_COUNT; ++w) {
      const auto word = m.template getWord<openvdb::Index64>(w);
      mix(&word, sizeof(word));
    }
  }
  // then the mask's leaves (origin, values), in tree order: a clay without a mask hashes as in CL1
  for (auto it = mask_->tree().cbeginLeaf(); it; ++it) {
    const Coord o = it->origin();
    mix(o.data(), sizeof(int) * 3);
    mix(it->buffer().data(), sizeof(float) * Leaf::SIZE);
  }
  return h;
}

size_t Volume::memory_bytes() const { return size_t(grid_->memUsage() + mask_->memUsage()); }
size_t Volume::active_voxels() const { return size_t(grid_->activeVoxelCount()); }
openvdb::FloatGrid::Ptr Volume::copy() const { return grid_->deepCopy(); }
openvdb::FloatGrid::Ptr Volume::copy_mask() const { return has_mask() ? mask_->deepCopy() : nullptr; }

bool Volume::save(const openvdb::FloatGrid::ConstPtr& grid, const std::string& path, std::string* error,
                  const openvdb::FloatGrid::ConstPtr& mask) {
  namespace fs = std::filesystem;
  const std::string partial = path + ".partial";  // written aside and renamed: a failure never leaves a broken cache
  try {
    fs::create_directories(fs::path(path).parent_path());
    {
      openvdb::io::File f(partial);
      f.setCompression(openvdb::io::COMPRESS_NONE);
      openvdb::GridCPtrVec grids{grid};
      if (mask) grids.push_back(mask);  // named "mask" (the volume's)
      f.write(grids);
      f.close();
    }
    fs::rename(partial, path);
    return true;
  } catch (const std::exception& e) {
    std::error_code ec;
    fs::remove(partial, ec);
    if (error) *error = e.what();
    return false;
  }
}

bool Volume::load(const std::string& path, std::string* error) {
  try {
    openvdb::io::File f(path);
    f.open(false);
    auto g = openvdb::gridPtrCast<openvdb::FloatGrid>(f.readGrid("clay"));
    openvdb::FloatGrid::Ptr m;  // the mask, when the clay had one
    if (f.hasGrid("mask")) {
      m = openvdb::gridPtrCast<openvdb::FloatGrid>(f.readGrid("mask"));
      if (!m) throw std::runtime_error("its grid \"mask\" is not a float grid");
    }
    f.close();
    if (!g) throw std::runtime_error("no float grid \"clay\"");
    const float v = float(g->voxelSize()[0]);
    if (std::fabs(v - voxel_) > 1e-6f * voxel_) throw std::runtime_error("its grain size differs from the clay's detail");
    grid_ = g;
    if (m) mask_ = m;
    else mask_->tree().clear();
    dirty_.clear();
    dirtyParts_.clear();
    live_.clear();
    live_.on = false;
    changesAll_ = true;  // a coarse copy is made again
    std::vector<Coord>().swap(changes_);
    return true;
  } catch (const std::exception& e) {
    if (error) *error = e.what();
    return false;
  }
}

}  // namespace r3d::clay
