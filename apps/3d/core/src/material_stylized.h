// The Stylized look's settings of one material (ENGINE_CONTRACT.md § 2, Materials: Lines, Light to colour, Halftone)
// and the `rostrum_stylized` shader that carries them on outputs:rostrum:surface (the "rostrum" render context, read by
// the stylized renderer, apps/3d/stylized). Written for every material, so the Stylized look always finds one.
#pragma once
#include <string>

#include <pxr/base/gf/vec3f.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>
#include <pxr/usd/usdShade/shader.h>

#include "json_read.h"

namespace r3d {

struct StylizedLook {
  bool lines = false;
  float linesWidth = 1.5f;
  PXR_NS::GfVec3f linesColor{0.0f};
  float linesTaper = 0.5f, linesWobble = 0.3f, linesCreaseAngle = 40.0f;
  bool lightToColor = false;
  PXR_NS::GfVec3f litColor{1.0f}, midColor{0.45f}, shadowColor{0.07f};
  float shadowBelow = 0.15f, litFrom = 0.5f, lightSoftness = 0.1f;
  bool lightSmooth = false;  // lightEdges "smooth" (else "steps")
  bool halftone = false;
  bool halftoneLines = false;  // halftoneShape "lines" (else "dots")
  float halftoneSize = 6.0f, halftoneAngle = 45.0f;
  PXR_NS::GfVec3f halftoneColor{0.0f};
};

// The material props of Lines, Light to colour and Halftone (all present, as every material field). Throws r3d::Error
// "<id>.<field>" for a wrong type or an unknown choice; ranges are the Python field table's.
StylizedLook read_stylized(Reader& p);

// Is `key` one of the fields only the Stylized look shows (Lines, Halftone)? A live `material` request changing only
// these sets the shader's inputs in place.
bool stylized_only_field(const std::string& key);

// The material's `Stylized` shader (info:id rostrum_stylized) with every input, connected to outputs:rostrum:surface.
// `base_image`: the PreviewBaseColor UsdUVTexture when a base colour image is set (its `rgb` feeds baseColor), else
// an invalid shader and baseColor holds `base`.
void author_stylized(const PXR_NS::UsdStageRefPtr& stage, const PXR_NS::SdfPath& material, const StylizedLook& look,
                     const PXR_NS::GfVec3f& base, PXR_NS::UsdShadeShader base_image,
                     const PXR_NS::GfVec3f& emission, float opacity);

// Sets only the Lines / Halftone inputs of an existing Stylized shader (the live request's quick path).
void set_stylized_inputs(PXR_NS::UsdShadeShader& s, const StylizedLook& look);

}  // namespace r3d
