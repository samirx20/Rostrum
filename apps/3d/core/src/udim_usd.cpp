#include "udim_usd.h"

#include <pxr/base/tf/token.h>
#include <pxr/base/vt/array.h>
#include <pxr/usd/sdf/assetPath.h>
#include <pxr/usd/sdf/layerUtils.h>
#include <pxr/usd/sdf/propertySpec.h>
#include <pxr/usd/sdf/types.h>
#include <pxr/usd/usd/primRange.h>
#include <pxr/usd/usdShade/shader.h>

#include "udim.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d::udim {

int list_tiles_under(const UsdPrim& root) {
  static const TfToken kUvTexture("UsdUVTexture"), kFile("inputs:file"), kTiles("inputs:tiles");
  int listed = 0;
  for (const UsdPrim& prim : UsdPrimRange(root)) {
    TfToken id;
    if (!prim.IsA<UsdShadeShader>() || !UsdShadeShader(prim).GetShaderId(&id) || id != kUvTexture) continue;
    const UsdAttribute file = prim.GetAttribute(kFile);
    SdfAssetPath asset;
    if (!file || !file.Get(&asset) || !is_set(asset.GetAssetPath()) || prim.GetAttribute(kTiles).HasAuthoredValue())
      continue;
    const std::vector<SdfPropertySpecHandle> stack = file.GetPropertyStack();
    const std::string path = stack.empty() ? asset.GetAssetPath()
                                           : SdfComputeAssetPathRelativeToLayer(stack.front()->GetLayer(),
                                                                                asset.GetAssetPath());
    const std::vector<int> found = tile_numbers(path);
    if (found.empty()) continue;  // no tile on disk: the texture shows as missing, as any missing picture does
    prim.CreateAttribute(kTiles, SdfValueTypeNames->IntArray).Set(VtIntArray(found.begin(), found.end()));
    ++listed;
  }
  return listed;
}

}  // namespace r3d::udim
