// P-3D-3: registers the "Rostrum Stylized" Hydra renderer (HdRostrumPlugin), loaded by name
// next to HdStormRendererPlugin and HdCyclesPlugin.
#include "delegate.h"

#include <pxr/imaging/hd/rendererCreateArgs.h>
#include <pxr/imaging/hd/rendererPlugin.h>
#include <pxr/imaging/hd/rendererPluginRegistry.h>

PXR_NAMESPACE_OPEN_SCOPE

class HdRostrumPlugin final : public HdRendererPlugin {
public:
    HdRenderDelegate *CreateRenderDelegate() override { return new HdRostrumDelegate({}); }
    HdRenderDelegate *CreateRenderDelegate(HdRenderSettingsMap const &settings) override
    {
        return new HdRostrumDelegate(settings);
    }
    void DeleteRenderDelegate(HdRenderDelegate *d) override { delete d; }
    bool IsSupported(HdRendererCreateArgs const &args, std::string *why) const override
    {
        if (!args.gpuEnabled && why) *why = "Rostrum Stylized draws with OpenGL and needs the GPU";
        return args.gpuEnabled;
    }
    bool IsSupported(bool gpuEnabled) const override { return gpuEnabled; }
};

TF_REGISTRY_FUNCTION(TfType)
{
    HdRendererPluginRegistry::Define<HdRostrumPlugin>();
}

PXR_NAMESPACE_CLOSE_SCOPE
