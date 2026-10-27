// Clay: a painted clay's unfolded surface (clay_surface.h).
#include "clay_surface.h"

#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <unordered_map>

#include "error.h"
#include "unfold.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::clay {

namespace {
constexpr char kMagic[4] = {'C', 'L', 'S', '1'};
constexpr uint32_t kVersion = 1;

struct Header {
  char magic[4];
  uint32_t version, size, points, tris, blocks;
};
static_assert(sizeof(Header) == 24, "CLS1's header is 24 bytes");
static_assert(sizeof(GfVec2f) == 2 * sizeof(float), "st is read as float pairs");

double ms_since(std::chrono::steady_clock::time_point t0) {
  return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

uint64_t file_bytes(uint64_t points, uint64_t tris, uint64_t blocks) {
  return sizeof(Header) + 4 * (6 * points + 3 * tris + 6 * tris + 4 * blocks);
}

std::string block_name(const BlockKey& k) {
  return "block (" + std::to_string(k.x) + ", " + std::to_string(k.y) + ", " + std::to_string(k.z) + ")";
}

// the file's uvs when it holds exactly these blocks at `size` (anything else: false, the surface is made again)
bool read_file(const std::string& file, const std::vector<SurfaceBlock>& blocks, int size, uint64_t tris,
               std::vector<float>& uv) {
  namespace fs = std::filesystem;
  const fs::path p = fs::u8path(file);
  std::error_code ec;
  const uintmax_t len = fs::file_size(p, ec);
  if (ec || len < sizeof(Header)) return false;
  std::ifstream in(p, std::ios::binary);
  Header h;
  if (!in.read(reinterpret_cast<char*>(&h), sizeof h)) return false;
  if (std::memcmp(h.magic, kMagic, 4) != 0 || h.version != kVersion || h.size != uint32_t(size) || h.tris != tris ||
      h.blocks != blocks.size() || uint64_t(h.points) > 3 * tris || len != file_bytes(h.points, h.tris, h.blocks))
    return false;
  std::vector<int32_t> list(4 * blocks.size());
  in.seekg(std::streamoff(len - 4 * list.size()));
  if (!list.empty() && !in.read(reinterpret_cast<char*>(list.data()), std::streamsize(4 * list.size()))) return false;
  for (size_t i = 0; i < blocks.size(); ++i) {
    const BlockKey& k = blocks[i].key;
    if (list[4 * i] != k.x || list[4 * i + 1] != k.y || list[4 * i + 2] != k.z ||
        list[4 * i + 3] != int32_t(blocks[i].indices.size() / 3))
      return false;
  }
  uv.resize(size_t(6 * tris));
  in.seekg(std::streamoff(sizeof(Header) + 4 * (6 * uint64_t(h.points) + 3 * tris)));
  return uv.empty() || bool(in.read(reinterpret_cast<char*>(uv.data()), std::streamsize(4 * uv.size())));
}

struct Welded {
  std::vector<float> points, normals;  // xyz each
  std::vector<int32_t> tris;           // 3 per triangle, into points
};

// the blocks' points joined where they sit at exactly the same place (a seam's two sides are bit-identical)
Welded weld(const std::vector<SurfaceBlock>& blocks, uint64_t tris, const std::string& where) {
  struct Key {
    uint32_t x, y, z;
    bool operator==(const Key& o) const { return x == o.x && y == o.y && z == o.z; }
  };
  struct Hash {
    size_t operator()(const Key& k) const {
      uint64_t h = k.x * 0x9E3779B97F4A7C15ull;
      h ^= (h >> 29) ^ (uint64_t(k.y) * 0xC2B2AE3D27D4EB4Full);
      h ^= (h >> 31) ^ (uint64_t(k.z) * 0x165667B19E3779F9ull);
      return size_t(h ^ (h >> 32));
    }
  };
  size_t corners = 0;
  for (const SurfaceBlock& b : blocks) corners += b.points.size();
  Welded w;
  w.points.reserve(3 * corners);
  w.normals.reserve(3 * corners);
  w.tris.reserve(size_t(3 * tris));
  std::unordered_map<Key, int32_t, Hash> at;
  at.reserve(corners);
  std::vector<int32_t> local;
  for (const SurfaceBlock& b : blocks) {
    local.resize(b.points.size());
    for (size_t v = 0; v < b.points.size(); ++v) {
      Key k;
      std::memcpy(&k, b.points[v].data(), sizeof k);
      const auto [it, fresh] = at.emplace(k, int32_t(w.points.size() / 3));
      if (fresh) {
        const GfVec3f n = v < b.normals.size() ? b.normals[v] : GfVec3f(0, 0, 1);
        w.points.insert(w.points.end(), {b.points[v][0], b.points[v][1], b.points[v][2]});
        w.normals.insert(w.normals.end(), {n[0], n[1], n[2]});
      }
      local[v] = it->second;
    }
    for (const int i : b.indices) {
      if (i < 0 || size_t(i) >= b.points.size())
        throw Error(where + ": " + block_name(b.key) + " names point " + std::to_string(i) + " of " +
                    std::to_string(b.points.size()));
      w.tris.push_back(local[size_t(i)]);
    }
  }
  return w;
}

void write_file(const std::string& file, int size, const Welded& w, const std::vector<float>& uv,
                const std::vector<SurfaceBlock>& blocks, const std::string& where) {
  namespace fs = std::filesystem;
  const std::string at = where + ".file";
  const fs::path p = fs::u8path(file);
  std::error_code ec;
  if (p.has_parent_path()) fs::create_directories(p.parent_path(), ec);
  if (ec) throw Error(at + ": could not make the folder for " + file + " (" + ec.message() + ")");
  fs::path tmp = p;
  tmp += ".partial";
  Header h;
  std::memcpy(h.magic, kMagic, 4);
  h.version = kVersion;
  h.size = uint32_t(size);
  h.points = uint32_t(w.points.size() / 3);
  h.tris = uint32_t(w.tris.size() / 3);
  h.blocks = uint32_t(blocks.size());
  std::vector<int32_t> list;
  list.reserve(4 * blocks.size());
  for (const SurfaceBlock& b : blocks) list.insert(list.end(), {b.key.x, b.key.y, b.key.z, int32_t(b.indices.size() / 3)});
  {
    std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
    if (!out) throw Error(at + ": could not write " + file + ".partial");
    const auto put = [&](const void* data, size_t bytes) {
      if (bytes) out.write(static_cast<const char*>(data), std::streamsize(bytes));
    };
    put(&h, sizeof h);
    put(w.points.data(), 4 * w.points.size());
    put(w.normals.data(), 4 * w.normals.size());
    put(w.tris.data(), 4 * w.tris.size());
    put(uv.data(), 4 * uv.size());
    put(list.data(), 4 * list.size());
    out.close();
    if (!out) {
      fs::remove(tmp, ec);
      throw Error(at + ": writing " + file + ".partial failed (is the disk full?)");
    }
  }
  fs::rename(tmp, p, ec);
  if (ec) {
    std::error_code ignored;
    fs::remove(tmp, ignored);
    throw Error(at + ": could not put " + file + " in place (" + ec.message() + ")");
  }
}

// one st per triangle corner of each block, from the uvs of all (6 per triangle, the blocks' triangles in order)
std::vector<VtVec2fArray> split(const std::vector<SurfaceBlock>& blocks, const std::vector<float>& uv) {
  std::vector<VtVec2fArray> out(blocks.size());
  size_t at = 0;
  for (size_t i = 0; i < blocks.size(); ++i) {
    const size_t n = blocks[i].indices.size();
    VtVec2fArray st(n);
    if (n) std::memcpy(st.data(), uv.data() + 2 * at, n * sizeof(GfVec2f));
    at += n;
    out[i] = std::move(st);
  }
  return out;
}
}  // namespace

std::vector<VtVec2fArray> clay_surface(const std::vector<SurfaceBlock>& blocks, int size, const std::string& file,
                                       const std::string& where, SurfaceStats* stats) {
  if (size < 64 || size > 16384)
    throw Error(where + ".size: " + std::to_string(size) + " is out of range. Accepted: 64..16384");
  uint64_t tris = 0;
  for (size_t i = 0; i < blocks.size(); ++i) {
    if (blocks[i].indices.size() % 3)
      throw Error(where + ": " + block_name(blocks[i].key) + " is not made of triangles");
    if (i && !(blocks[i - 1].key < blocks[i].key))
      throw Error(where + ": the blocks are not in order (" + block_name(blocks[i].key) + ")");
    tris += blocks[i].indices.size() / 3;
  }
  if (tris > uint64_t(INT32_MAX) / 3) throw Error(where + ": the surface is too big to unfold");
  SurfaceStats st;
  st.triangles = size_t(tris);
  std::vector<float> uv;
  auto t0 = std::chrono::steady_clock::now();
  if (read_file(file, blocks, size, tris, uv)) {
    st.fileMs = ms_since(t0);
    if (stats) *stats = st;
    return split(blocks, uv);
  }
  st.made = true;
  const Welded w = weld(blocks, tris, where);
  st.points = w.points.size() / 3;
  st.weldMs = ms_since(t0);
  t0 = std::chrono::steady_clock::now();
  if (tris > 0) {  // an empty clay: an empty file, so the Python side sees the surface (with nothing on it)
    UnfoldedTris u = unfold_triangles(w.points.data(), st.points, w.tris.data(), size_t(tris), size, where);
    uv = std::move(u.st);
    st.charts = u.charts;
  }
  st.unfoldMs = ms_since(t0);
  t0 = std::chrono::steady_clock::now();
  write_file(file, size, w, uv, blocks, where);
  st.fileMs = ms_since(t0);
  if (stats) *stats = st;
  return split(blocks, uv);
}

}  // namespace r3d::clay
