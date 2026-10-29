#include "cryptomatte.h"

#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdGeom/gprim.h>

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <map>
#include <unordered_map>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
constexpr int kRanks = 6;  // 3 layers of 2 (id, share) pairs: Cryptomatte's usual depth

uint32_t rotl(uint32_t x, int r) { return (x << r) | (x >> (32 - r)); }

uint32_t float_bits(float f) {
  uint32_t u;
  std::memcpy(&u, &f, 4);
  return u;
}

std::string hex(uint32_t h) {
  char s[9];
  std::snprintf(s, sizeof s, "%08x", h);
  return s;
}

std::string json_string(const std::string& s) {
  std::string out = "\"";
  for (char c : s) {
    if (c == '"' || c == '\\') out += '\\';
    out += c;
  }
  return out + "\"";
}

// the item a scene path belongs to: /World/<item> (its id), else the path itself
std::string item_of(const SdfPath& p) {
  const auto prefixes = p.GetPrefixes();
  if (prefixes.size() >= 2 && prefixes[0] == SdfPath("/World")) return prefixes[1].GetName();
  return p.GetString();
}
}  // namespace

uint32_t murmur3(const std::string& s) {
  const auto* d = reinterpret_cast<const unsigned char*>(s.data());
  const size_t n = s.size(), blocks = n / 4;
  const uint32_t c1 = 0xcc9e2d51, c2 = 0x1b873593;
  uint32_t h = 0;
  for (size_t i = 0; i < blocks; ++i) {
    uint32_t k = uint32_t(d[i * 4]) | uint32_t(d[i * 4 + 1]) << 8 | uint32_t(d[i * 4 + 2]) << 16 |
                 uint32_t(d[i * 4 + 3]) << 24;
    k = rotl(k * c1, 15) * c2;
    h = rotl(h ^ k, 13) * 5 + 0xe6546b64;
  }
  const unsigned char* tail = d + blocks * 4;
  uint32_t k = 0;
  switch (n & 3) {
    case 3: k ^= uint32_t(tail[2]) << 16; [[fallthrough]];
    case 2: k ^= uint32_t(tail[1]) << 8; [[fallthrough]];
    case 1: k ^= tail[0]; h ^= rotl(k * c1, 15) * c2;
  }
  h ^= uint32_t(n);
  h ^= h >> 16;
  h *= 0x85ebca6b;
  h ^= h >> 13;
  h *= 0xc2b2ae35;
  return h ^ (h >> 16);
}

float hash_to_float(uint32_t h) {
  const uint32_t exponent = (h >> 23) & 255;
  if (exponent == 0 || exponent == 255) h ^= 1u << 23;
  float f;
  std::memcpy(&f, &h, 4);
  return f;
}

const std::vector<std::string>& crypto_aovs() {
  static const std::vector<std::string> names = {"CryptoObject00", "CryptoObject01", "CryptoObject02"};
  return names;
}

std::vector<ExrLayer> cryptomatte(const Aovs& lit, const UsdStageRefPtr& stage) {
  // Cycles' id (its float's bits) of every scene path -> the item's own id; the items in the manifest
  std::unordered_map<uint32_t, float> item_id;
  std::map<std::string, uint32_t> manifest;
  for (UsdPrim p : stage->Traverse(UsdTraverseInstanceProxies())) {
    const std::string item = item_of(p.GetPath());
    const uint32_t h = murmur3(item);
    item_id[float_bits(hash_to_float(murmur3(p.GetPath().GetString())))] = hash_to_float(h);
    if (p.IsA<UsdGeomGprim>()) manifest[item] = h;  // what can be seen: no materials, cameras or lights
  }
  const auto& names = crypto_aovs();
  std::vector<const std::vector<float>*> in;
  for (const auto& n : names) in.push_back(&lit.plane(n));
  const size_t count = in[0]->size() / 4;
  std::vector<std::vector<float>> out(names.size(), std::vector<float>(count * 4, 0.0f));
  for (size_t i = 0; i < count; ++i) {
    std::array<std::pair<float, float>, kRanks> ranks{};  // (id, share), parts of one item added
    int used = 0;
    for (int r = 0; r < kRanks; ++r) {
      const float* px = &(*in[r / 2])[i * 4 + (r % 2) * 2];
      if (!(px[1] > 0.0f)) continue;
      const auto it = item_id.find(float_bits(px[0]));
      const float id = it == item_id.end() ? px[0] : it->second;  // an object no scene path names keeps its id
      int k = 0;
      while (k < used && ranks[k].first != id) ++k;
      if (k == used) ranks[used++] = {id, 0.0f};
      ranks[k].second += px[1];
    }
    std::sort(ranks.begin(), ranks.begin() + used, [](const auto& a, const auto& b) { return a.second > b.second; });
    for (int r = 0; r < used; ++r) {
      float* px = &out[r / 2][i * 4 + (r % 2) * 2];
      px[0] = ranks[r].first;
      px[1] = ranks[r].second;
    }
  }
  std::string json = "{";
  for (const auto& [name, h] : manifest) json += (json.size() > 1 ? "," : "") + json_string(name) + ":\"" + hex(h) + "\"";
  json += "}";
  const std::string key = "cryptomatte/" + hex(murmur3("CryptoObject")).substr(0, 7) + "/";
  std::vector<ExrLayer> layers;
  for (size_t l = 0; l < names.size(); ++l) {
    const std::string& n = names[l];
    layers.push_back(ExrLayer{{n + ".R", n + ".G", n + ".B", n + ".A"}, std::move(out[l]), true, {}});
  }
  layers.front().attributes = {{key + "name", "CryptoObject"}, {key + "hash", "MurmurHash3_32"},
                               {key + "conversion", "uint32_to_float32"}, {key + "manifest", json}};
  return layers;
}

}  // namespace r3d
