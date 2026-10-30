#include "implicit_shapes.h"

#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hdsi/implicitSurfaceSceneIndex.h>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

void register_implicit_shapes() {
  static const bool once = [] {
    const HdDataSourceBaseHandle to_mesh =
        HdRetainedTypedSampledDataSource<TfToken>::New(HdsiImplicitSurfaceSceneIndexTokens->toMesh);
    const HdContainerDataSourceHandle args = HdRetainedContainerDataSource::New(
        HdPrimTypeTokens->sphere, to_mesh, HdPrimTypeTokens->cube, to_mesh, HdPrimTypeTokens->cylinder, to_mesh,
        HdPrimTypeTokens->cone, to_mesh, HdPrimTypeTokens->capsule, to_mesh, HdPrimTypeTokens->plane, to_mesh);
    for (const char* renderer : {"Cycles", "Rostrum Stylized"})  // display names (their plugInfo.json)
      HdSceneIndexPluginRegistry::GetInstance().RegisterSceneIndexForRenderer(
          renderer,
          [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle& a) {
            return HdsiImplicitSurfaceSceneIndex::New(in, a);
          },
          args, 0, HdSceneIndexPluginRegistry::InsertionOrderAtStart);
    return true;
  }();
  (void)once;
}

}  // namespace r3d
