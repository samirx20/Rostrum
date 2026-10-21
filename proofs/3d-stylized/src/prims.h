// P-3D-3: Hydra prims (mesh, material, light) that copy what the stage says into RostrumScene.
#pragma once

#include "scene.h"

#include <pxr/imaging/hd/light.h>
#include <pxr/imaging/hd/material.h>
#include <pxr/imaging/hd/mesh.h>

PXR_NAMESPACE_OPEN_SCOPE

class HdRostrumMesh final : public HdMesh {
public:
    HdRostrumMesh(SdfPath const &id, RostrumScene *scene) : HdMesh(id), _scene(scene) {}
    ~HdRostrumMesh() override;
    HdDirtyBits GetInitialDirtyBitsMask() const override { return HdChangeTracker::AllSceneDirtyBits; }
    void Sync(HdSceneDelegate *sd, HdRenderParam *, HdDirtyBits *bits, TfToken const &) override;
    TfTokenVector const &GetBuiltinPrimvarNames() const override;

protected:
    HdDirtyBits _PropagateDirtyBits(HdDirtyBits bits) const override { return bits; }
    void _InitRepr(TfToken const &, HdDirtyBits *) override {}

private:
    RostrumScene *_scene;
};

class HdRostrumMaterial final : public HdMaterial {
public:
    HdRostrumMaterial(SdfPath const &id, RostrumScene *scene) : HdMaterial(id), _scene(scene) {}
    ~HdRostrumMaterial() override;
    HdDirtyBits GetInitialDirtyBitsMask() const override { return AllDirty; }
    void Sync(HdSceneDelegate *sd, HdRenderParam *, HdDirtyBits *bits) override;

private:
    RostrumScene *_scene;
};

class HdRostrumLight final : public HdLight {
public:
    HdRostrumLight(SdfPath const &id, TfToken const &type, RostrumScene *scene)
        : HdLight(id), _type(type), _scene(scene) {}
    ~HdRostrumLight() override;
    HdDirtyBits GetInitialDirtyBitsMask() const override { return AllDirty; }
    void Sync(HdSceneDelegate *sd, HdRenderParam *, HdDirtyBits *bits) override;

private:
    TfToken _type;
    RostrumScene *_scene;
};

PXR_NAMESPACE_CLOSE_SCOPE
