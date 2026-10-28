// The format table and the session cache of converted layers (convert.h). The readers are in convert_gltf.cpp,
// convert_obj.cpp, convert_fbx.cpp and convert_abc.cpp; what they share to write USD is in convert_usd.h.
#include "convert.h"

#include <pxr/usd/usd/prim.h>

#include <algorithm>
#include <cctype>
#include <exception>
#include <filesystem>
#include <map>
#include <mutex>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace fs = std::filesystem;

namespace r3d {

// the readers (each in its convert_<format>.cpp)
void convert_gltf(const std::string& file, const UsdStageRefPtr& out);
void convert_obj(const std::string& file, const UsdStageRefPtr& out);
void convert_fbx(const std::string& file, const UsdStageRefPtr& out);
void convert_abc(const std::string& file, const UsdStageRefPtr& out);

namespace {

std::mutex& lock() {
  static std::mutex m;
  return m;
}

std::vector<Format>& table() {
  static std::vector<Format> t = {
      {"glTF", {".gltf", ".glb"}, convert_gltf},
      {"OBJ", {".obj"}, convert_obj},
      {"FBX", {".fbx"}, convert_fbx},
      {"Alembic", {".abc"}, convert_abc},
  };
  return t;
}

// A converted layer and the file state it was made from.
struct Cached {
  std::uintmax_t size = 0;
  fs::file_time_type stamp;
  SdfLayerRefPtr layer;
};

std::map<std::string, Cached>& cache() {
  static std::map<std::string, Cached> c;
  return c;
}

std::string file_name(const std::string& file) { return fs::u8path(file).filename().u8string(); }

}  // namespace

const std::vector<Format>& formats() { return table(); }

void add_format(Format f) {
  std::lock_guard<std::mutex> hold(lock());
  table().push_back(std::move(f));
}

std::string extension_of(const std::string& file) {
  std::string e = fs::u8path(file).extension().u8string();
  std::transform(e.begin(), e.end(), e.begin(), [](unsigned char c) { return char(std::tolower(c)); });
  return e;
}

bool is_usd(const std::string& file) {
  const std::string e = extension_of(file);
  return e == ".usd" || e == ".usda" || e == ".usdc" || e == ".usdz";
}

const Format* format_for(const std::string& file) {
  const std::string e = extension_of(file);
  for (const Format& f : formats())
    if (std::find(f.extensions.begin(), f.extensions.end(), e) != f.extensions.end()) return &f;
  return nullptr;
}

std::string accepted_files() {
  std::vector<std::string> all = {".usd", ".usda", ".usdc", ".usdz"};
  for (const Format& f : formats()) all.insert(all.end(), f.extensions.begin(), f.extensions.end());
  std::string s = "a ";
  for (size_t i = 0; i < all.size(); ++i) s += (i == 0 ? "" : i + 1 == all.size() ? " or " : ", ") + all[i];
  return s + " file";
}

SdfLayerRefPtr converted_layer(const std::string& file) {
  const Format* format = format_for(file);
  if (!format) throw Error("can't import " + file_name(file) + ": it isn't " + accepted_files());
  std::error_code ec;
  const fs::path path = fs::u8path(file);
  const std::uintmax_t size = fs::file_size(path, ec);
  if (ec) throw Error("could not read " + file_name(file) + ": there is no such file");
  const fs::file_time_type stamp = fs::last_write_time(path, ec);
  const std::string key = fs::absolute(path, ec).lexically_normal().u8string();

  // One lock for the lookup and the conversion: the engine and the in-window view may ask for the same file at
  // once, and it is converted only once.
  std::lock_guard<std::mutex> hold(lock());
  auto found = cache().find(key);
  if (found != cache().end() && found->second.size == size && found->second.stamp == stamp)
    return found->second.layer;

  UsdStageRefPtr stage = UsdStage::CreateInMemory(fs::u8path(file).stem().u8string() + ".usda");
  try {
    format->convert(file, stage);  // readers throw the bare reason; the file's name is put in front here
  } catch (const std::exception& e) {
    throw Error("could not read " + file_name(file) + ": " + e.what());
  }
  if (!stage->GetDefaultPrim()) throw Error("could not read " + file_name(file) + ": it holds nothing to import");
  VtDictionary data = stage->GetRootLayer()->GetCustomLayerData();  // what a plain save names its copy by (save_stage.cpp)
  data["rostrum:source"] = VtValue(key + "|" + std::to_string(size) + "|" +
                                   std::to_string(stamp.time_since_epoch().count()));
  stage->GetRootLayer()->SetCustomLayerData(data);
  Cached c{size, stamp, stage->GetRootLayer()};
  cache()[key] = c;
  return c.layer;
}

}  // namespace r3d
