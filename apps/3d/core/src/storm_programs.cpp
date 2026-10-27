// StormPrograms (storm_programs.h). Storm has no public way to reach its program registry, so the two private members
// on the way (the adapter's render delegate, the registry's programs) are read through the standard's explicit
// instantiation rule (a pointer to a private member may be named there), not by redefining `private`.
#include "storm_programs.h"

#include <pxr/imaging/hd/renderDelegateAdapterRenderer.h>
#include <pxr/imaging/hd/renderer.h>
#include <pxr/imaging/hdSt/glslProgram.h>
#include <pxr/imaging/hdSt/resourceRegistry.h>

PXR_NAMESPACE_USING_DIRECTIVE

namespace {

template <typename Tag, typename Tag::type Member>
struct Reach {
  friend typename Tag::type reach(Tag) { return Member; }
};

struct ProgramsOf {
  using type = HdInstanceRegistry<HdStGLSLProgramSharedPtr> HdStResourceRegistry::*;
  friend type reach(ProgramsOf);
};
template struct Reach<ProgramsOf, &HdStResourceRegistry::_glslProgramRegistry>;

struct DelegateOf {
  using type = const HdPluginRenderDelegateUniqueHandle HdRenderDelegateAdapterRenderer::*;
  friend type reach(DelegateOf);
};
template struct Reach<DelegateOf, &HdRenderDelegateAdapterRenderer::_renderDelegate>;

constexpr size_t kMostHeld = 2048;  // a bound: a long session's old programs go now and then (one recompile each)

}  // namespace

namespace r3d {

void StormPrograms::keep(HdRenderer* renderer, HdRenderDelegate* delegate) {
  if (!delegate && renderer)
    if (auto* a = dynamic_cast<HdRenderDelegateAdapterRenderer*>(renderer)) delegate = (a->*reach(DelegateOf{})).Get();
  if (!delegate) return;
  auto reg = std::dynamic_pointer_cast<HdStResourceRegistry>(delegate->GetResourceRegistry());
  if (!reg) return;  // not Storm
  auto& programs = (*reg).*reach(ProgramsOf{});
  if (held_.size() > kMostHeld) held_.clear();
  for (auto it = programs.begin(); it != programs.end(); ++it)  // a few dozen: nothing next to a picture
    if (it->second.value) held_.insert(it->second.value);
}

}  // namespace r3d
