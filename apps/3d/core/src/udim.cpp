#include "udim.h"

#include <filesystem>

namespace fs = std::filesystem;

namespace r3d::udim {
namespace {

constexpr int kFirst = 1001, kLast = 1099;

// `path` with its `<UDIM>` replaced by `tile`.
std::string tile_path(const std::string& path, int tile) {
  std::string out = path;
  const size_t at = out.find(kToken);
  return out.replace(at, std::string(kToken).size(), std::to_string(tile));
}

bool exists(const std::string& path) {
  std::error_code ec;
  return fs::is_regular_file(fs::u8path(path), ec);
}

}  // namespace

bool is_set(const std::string& path) { return path.find(kToken) != std::string::npos; }

std::vector<int> tile_numbers(const std::string& path) {
  std::vector<int> out;
  if (!is_set(path)) return out;
  for (int t = kFirst; t <= kLast; ++t)
    if (exists(tile_path(path, t))) out.push_back(t);
  return out;
}

std::vector<std::string> tiles(const std::string& path) {
  std::vector<std::string> out;
  for (int t : tile_numbers(path)) out.push_back(tile_path(path, t));
  return out;
}

std::string as_set(const std::string& path) {
  if (is_set(path)) return path;
  const fs::path p = fs::u8path(path);
  const std::string stem = p.stem().u8string();  // "name.1001" or "name_1001"
  if (stem.size() < 6) return path;
  const char sep = stem[stem.size() - 5];
  const std::string digits = stem.substr(stem.size() - 4);
  if ((sep != '.' && sep != '_') || digits.find_first_not_of("0123456789") != std::string::npos) return path;
  const int tile = std::stoi(digits);
  if (tile < kFirst || tile > kLast) return path;
  const std::string ext = p.extension().u8string();  // the digits replaced in the text, so separators stay as given
  const std::string set = path.substr(0, path.size() - ext.size() - 4) + kToken + ext;
  for (int t : tile_numbers(set))
    if (t != tile) return set;
  return path;
}

}  // namespace r3d::udim
