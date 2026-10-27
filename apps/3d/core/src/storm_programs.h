// Storm's shader programs kept alive between pictures (3d-v2). Storm draws a scene with a glass (its see-through
// pass, OIT) with one draw batch and two shaders in turn, and the batch holds only the last one. Storm's clean-up
// (resource garbage collection) drops every program nobody holds, and it runs after any picture in which a mesh
// changed size or shape, which is every clay dab. So each dab threw away the glass pass's other shader and compiled
// and linked it again: ~8 ms of a dab's 17 ms Storm draw on the sample scene (clay_dab_bench.py, USD's trace). Holding
// every program Storm has made keeps them; Storm still frees everything else as before.
#pragma once
#include <pxr/pxr.h>

#include <memory>
#include <unordered_set>

PXR_NAMESPACE_OPEN_SCOPE
class HdRenderer;
class HdRenderDelegate;
PXR_NAMESPACE_CLOSE_SCOPE

namespace r3d {

class StormPrograms {
 public:
  // after a picture: hold every program Storm's registry has (the engine's renderer, Hydra 2.0, or its render
  // delegate, Hydra 1.0; whichever it has). Not Storm: nothing.
  void keep(PXR_NS::HdRenderer* renderer, PXR_NS::HdRenderDelegate* delegate);

 private:
  std::unordered_set<std::shared_ptr<void>> held_;
};

}  // namespace r3d
