// Small builders for the shader nodes of one material (materials.cpp): Cycles nodes (`cycles_<node>`, read by
// Cycles' Hydra plug-in, which matches USD input names to socket names ignoring case and output names to the
// sockets' own names) and UsdPreviewSurface helpers (Storm). Names checked against Cycles' scene/shader_nodes.cpp.
#pragma once
#include <string>
#include <vector>

#include <pxr/usd/sdf/path.h>
#include <pxr/usd/sdf/valueTypeName.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdShade/shader.h>

namespace r3d {

PXR_NS::UsdShadeShader shader(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& mat, const char* name,
                              const char* id);

template <class T>
void set(PXR_NS::UsdShadeShader& s, const char* input, const PXR_NS::SdfValueTypeName& type, const T& value) {
  s.CreateInput(PXR_NS::TfToken(input), type).Set(value);
}

void link(PXR_NS::UsdShadeShader& dst, const char* input, const PXR_NS::SdfValueTypeName& type,
          PXR_NS::UsdShadeShader& src, const char* output, const PXR_NS::SdfValueTypeName& out_type);

// A picture that may change per frame: one file, or one file per frame of the shot (frame start + i).
struct Picture {
  std::vector<std::string> files;  // empty = none; 1 = a still; else one per frame
  int start = 0;
  bool empty() const { return files.empty(); }
};

// cycles_image_texture on the mesh's default UVs; colour = sRGB, anything else = raw numbers ("data").
PXR_NS::UsdShadeShader cycles_image(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& mat,
                                    const char* name, const Picture& pic, bool colour);

// UsdUVTexture reading `st` (a UsdPrimvarReader_float2 of "st").
PXR_NS::UsdShadeShader preview_image(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& mat,
                                     const char* name, const Picture& pic, bool colour, PXR_NS::UsdShadeShader& st);

// The direction brushed metal is brushed in, linked into the principled BSDF's `tangent`:
// "uv" = along the mesh's U (cycles_tangent, uv_map); "around x|y|z" = circles round that axis of the item, through
// its origin (spun brushing). Built from the object-space position (cycles_texture_coordinate.object) crossed with
// the axis, then turned into world space: Cycles' own radial tangent assumes 0..1 "generated" coordinates centred
// on 0.5, which Hydra meshes don't have (Cycles falls back to raw positions), so its circles would be off-centre.
void brush_tangent(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& mat, PXR_NS::UsdShadeShader& bsdf,
                   const std::string& direction);

}  // namespace r3d
