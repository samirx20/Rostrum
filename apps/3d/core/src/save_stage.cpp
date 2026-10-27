// `save` (inspect.h save_stage). Flattened: the whole composed stage in one file. Plain: the root layer as it is,
// except that a layer living only in this process (an import of another format: convert.h's converted layer, or any
// other in-memory layer a reference points at) is written beside the file, in "<file name>_imports\", as
// "<its name>-<16 hex>.usdc", and the reference points there by a relative path. The hex is a hash of the source
// file's path, size and modification time (rostrum:source), else of the layer's content: the same import saved again
// is the same file, written once. The saved file then opens again on its own, here or on another machine.
#include <pxr/base/tf/errorMark.h>
#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/usdUtils/dependencies.h>

#include <cstdio>
#include <filesystem>
#include <functional>
#include <map>

#include "error.h"
#include "inspect.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace fs = std::filesystem;

namespace r3d {

namespace {

std::string key_of(const SdfLayerHandle& layer) {
  const VtDictionary data = layer->GetCustomLayerData();
  const auto it = data.find("rostrum:source");
  std::string text;
  if (it != data.end() && it->second.IsHolding<std::string>()) text = it->second.UncheckedGet<std::string>();
  else layer->ExportToString(&text);
  char hex[17];
  std::snprintf(hex, sizeof hex, "%016llx", static_cast<unsigned long long>(std::hash<std::string>{}(text)));
  return hex;
}

// The in-memory layer `id` written into `folder` once; its path relative to the saved file.
std::string keep(const std::string& id, const fs::path& folder, const std::string& sub) {
  const SdfLayerHandle layer = SdfLayer::Find(id);
  if (!layer) throw Error("save: the import layer " + id + " is gone; import the file again");
  std::string stem = fs::u8path(layer->GetDisplayName()).stem().u8string();
  if (stem.empty()) stem = "layer";
  const std::string name = stem + "-" + key_of(layer) + ".usdc";
  std::error_code ec;
  fs::create_directories(folder / fs::u8path(sub), ec);
  const fs::path out = folder / fs::u8path(sub) / fs::u8path(name);
  if (!fs::exists(out, ec) && !layer->Export(out.u8string()))
    throw Error("save: could not write the import " + out.u8string());
  return "./" + sub + "/" + name;
}

}  // namespace

void save_stage(const UsdStageRefPtr& stage, const std::string& file, bool flatten) {
  TfErrorMark mark;
  bool ok;
  if (flatten) {
    ok = stage->Export(file);
  } else {
    const SdfLayerRefPtr copy = SdfLayer::CreateAnonymous(".usda");
    copy->TransferContent(stage->GetRootLayer());
    const fs::path at = fs::absolute(fs::u8path(file));
    const std::string sub = at.stem().u8string() + "_imports";
    std::map<std::string, std::string> kept;
    UsdUtilsModifyAssetPaths(copy, [&](const std::string& path) {
      if (!SdfLayer::IsAnonymousLayerIdentifier(path)) return path;
      auto found = kept.find(path);
      if (found == kept.end()) found = kept.emplace(path, keep(path, at.parent_path(), sub)).first;
      return found->second;
    });
    ok = copy->Export(file);
  }
  if (!ok || !mark.IsClean()) throw Error("save.file: could not write " + file);
}

}  // namespace r3d
