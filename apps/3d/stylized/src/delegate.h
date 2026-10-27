// P-3D-3: the Rostrum Stylized render delegate (Hydra 1 prims, OpenGL raster pass).
#pragma once

#include "scene.h"

#include <pxr/imaging/hd/renderDelegate.h>
#include <pxr/imaging/hd/resourceRegistry.h>

#include <map>
#include <memory>

PXR_NAMESPACE_OPEN_SCOPE

class HdRostrumDelegate final : public HdRenderDelegate {
public:
    explicit HdRostrumDelegate(HdRenderSettingsMap const &settings);
    ~HdRostrumDelegate() override = default;

    TfTokenVector const &GetSupportedRprimTypes() const override;
    TfTokenVector const &GetSupportedSprimTypes() const override;
    TfTokenVector const &GetSupportedBprimTypes() const override;
    HdResourceRegistrySharedPtr GetResourceRegistry() const override { return _registry; }
    HdRenderParam *GetRenderParam() const override { return nullptr; }

    HdRenderPassSharedPtr CreateRenderPass(HdRenderIndex *index,
                                           HdRprimCollection const &collection) override;
    HdInstancer *CreateInstancer(HdSceneDelegate *, SdfPath const &) override { return nullptr; }
    void DestroyInstancer(HdInstancer *) override {}
    HdRprim *CreateRprim(TfToken const &typeId, SdfPath const &id) override;
    void DestroyRprim(HdRprim *prim) override;
    HdSprim *CreateSprim(TfToken const &typeId, SdfPath const &id) override;
    HdSprim *CreateFallbackSprim(TfToken const &typeId) override;
    void DestroySprim(HdSprim *prim) override;
    HdBprim *CreateBprim(TfToken const &typeId, SdfPath const &id) override;
    HdBprim *CreateFallbackBprim(TfToken const &typeId) override;
    void DestroyBprim(HdBprim *prim) override;
    void CommitResources(HdChangeTracker *) override {}

    HdAovDescriptor GetDefaultAovDescriptor(TfToken const &name) const override;
    TfTokenVector GetMaterialRenderContexts() const override;

    RostrumScene &Scene() { return _scene; }
    // every renderer setting named "rostrum:*" as a float (bools 0/1), for the shaders' uniforms
    std::map<std::string, float> LookSettings() const;

private:
    HdResourceRegistrySharedPtr _registry;
    RostrumScene _scene;
};

PXR_NAMESPACE_CLOSE_SCOPE
