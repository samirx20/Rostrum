// The stylized render pass. Draws with OpenGL on the host's current context:
// shadow maps -> G-buffer (+ material row) -> shade (light, then the material: plain / light to
// colour / halftone) -> ink edges (materials with Lines) -> ink -> AOVs.
#pragma once

#include "gl.h"

#include <pxr/imaging/hd/renderPass.h>
#include <pxr/imaging/hd/renderPassState.h>

#include <memory>

PXR_NAMESPACE_OPEN_SCOPE

class HdRostrumDelegate;
struct RostrumGpu;

class HdRostrumRenderPass final : public HdRenderPass {
public:
    HdRostrumRenderPass(HdRenderIndex *index, HdRprimCollection const &collection,
                        HdRostrumDelegate *delegate);
    ~HdRostrumRenderPass() override;
    bool IsConverged() const override { return true; }

protected:
    void _Execute(HdRenderPassStateSharedPtr const &state, TfTokenVector const &renderTags) override;

private:
    void _Draw(HdRenderPassStateSharedPtr const &state, int w, int h);
    HdRostrumDelegate *_delegate;
    std::unique_ptr<RostrumGpu> _gpu;
};

PXR_NAMESPACE_CLOSE_SCOPE
