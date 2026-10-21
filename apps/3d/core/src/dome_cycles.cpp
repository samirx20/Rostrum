#include "dome_cycles.h"

#include <pxr/imaging/hd/filteringSceneIndex.h>
#include <pxr/imaging/hd/overlayContainerDataSource.h>
#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hd/xformSchema.h>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {

// USD row vectors: a dome-local direction d is seen by Cycles as d · W⁻¹. With W' = T · W, Cycles' local direction is
// (USD local) · T⁻¹ = (USD local) · Tᵀ, which must be (z, x, y) of the USD local one (dome_cycles.h).
const GfMatrix4d kTurn(0, 0, 1, 0,   // row x
                       1, 0, 0, 0,   // row y
                       0, 1, 0, 0,   // row z
                       0, 0, 0, 1);

// the dome's own matrix, turned for Cycles, at every time it is sampled
class TurnedMatrix : public HdMatrixDataSource {
 public:
  HD_DECLARE_DATASOURCE(TurnedMatrix);
  VtValue GetValue(Time t) override { return VtValue(GetTypedValue(t)); }
  GfMatrix4d GetTypedValue(Time t) override { return kTurn * (in_ ? in_->GetTypedValue(t) : GfMatrix4d(1)); }
  bool GetContributingSampleTimesForInterval(Time a, Time b, std::vector<Time>* out) override {
    return in_ && in_->GetContributingSampleTimesForInterval(a, b, out);
  }

 private:
  explicit TurnedMatrix(HdMatrixDataSourceHandle in) : in_(std::move(in)) {}
  HdMatrixDataSourceHandle in_;
};

class DomeTurn final : public HdSingleInputFilteringSceneIndexBase {
 public:
  static HdSceneIndexBaseRefPtr New(const HdSceneIndexBaseRefPtr& in) { return TfCreateRefPtr(new DomeTurn(in)); }

  HdSceneIndexPrim GetPrim(const SdfPath& path) const override {
    HdSceneIndexPrim prim = _GetInputSceneIndex()->GetPrim(path);
    if (prim.primType != HdPrimTypeTokens->domeLight || !prim.dataSource) return prim;
    const HdXformSchema x = HdXformSchema::GetFromParent(prim.dataSource);
    HdContainerDataSourceHandle xform = HdXformSchema::Builder()
                                            .SetMatrix(TurnedMatrix::New(x.GetMatrix()))
                                            .SetResetXformStack(x.GetResetXformStack())
                                            .Build();
    prim.dataSource = HdOverlayContainerDataSource::New(
        HdRetainedContainerDataSource::New(HdXformSchemaTokens->xform, xform), prim.dataSource);
    return prim;
  }
  SdfPathVector GetChildPrimPaths(const SdfPath& path) const override {
    return _GetInputSceneIndex()->GetChildPrimPaths(path);
  }

 protected:
  void _PrimsAdded(const HdSceneIndexBase&, const HdSceneIndexObserver::AddedPrimEntries& e) override {
    _SendPrimsAdded(e);
  }
  void _PrimsRemoved(const HdSceneIndexBase&, const HdSceneIndexObserver::RemovedPrimEntries& e) override {
    _SendPrimsRemoved(e);
  }
  void _PrimsDirtied(const HdSceneIndexBase&, const HdSceneIndexObserver::DirtiedPrimEntries& e) override {
    _SendPrimsDirtied(e);  // the turn is applied when read, so a moved dome stays turned
  }

 private:
  explicit DomeTurn(const HdSceneIndexBaseRefPtr& in) : HdSingleInputFilteringSceneIndexBase(in) {}
};

}  // namespace

void register_cycles_dome_fix() {
  static const bool once = [] {
    HdSceneIndexPluginRegistry::GetInstance().RegisterSceneIndexForRenderer(
        "Cycles",
        [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle&) {
          return DomeTurn::New(in);
        },
        nullptr, 0, HdSceneIndexPluginRegistry::InsertionOrderAtStart);
    return true;
  }();
  (void)once;
}

}  // namespace r3d
