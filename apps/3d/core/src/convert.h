// Imports of other formats (glTF / GLB, OBJ, FBX, Alembic): each file is turned once into a USD layer, which an
// `import` item then references exactly like a USD file (stage_items.cpp build_import) and inspect_usd describes.
//
// What a converted layer holds (every converter keeps to this, so everything downstream is today's USD import):
//  - one default prim, an Xform named after the file (a valid identifier), holding the file's node tree as Xforms and
//    Meshes (names made valid and unique among siblings; positions, face counts / indices, normals, `st` UVs);
//  - its materials as UsdPreviewSurface under <default prim>/Materials, bound to the meshes (a part's material picker
//    overrides them);
//  - the layer's metadata: upAxis "Y" (the converter turns Z-up sources upright), metersPerUnit = the file's own unit
//    (geometry is never rescaled here: the Python side scales the import and says so), and in customLayerData
//    "rostrum:format" ("glTF", "OBJ", "FBX", "Alembic") and "rostrum:unitsKnown" (false when the format has no unit,
//    e.g. OBJ: then metersPerUnit is 1);
//  - an animation (Alembic; node animation where a reader has it) as time samples, one time code per source frame,
//    with the layer's startTimeCode / endTimeCode / timeCodesPerSecond set (USD maps it onto the scene's frame rate).
#pragma once

#include <pxr/usd/sdf/layer.h>
#include <pxr/usd/usd/stage.h>

#include <string>
#include <vector>

namespace r3d {

// Fills `out` (a fresh in-memory stage) from `file`; throws r3d::Error with a plain reason when the file can't be read.
using Converter = void (*)(const std::string& file, const pxr::UsdStageRefPtr& out);

struct Format {
  std::string name;                      // "glTF", shown to people and agents
  std::vector<std::string> extensions;   // lower case, with the dot: {".gltf", ".glb"}
  Converter convert;
};

// The readers in the core (convert.cpp lists them); a plug-in adds its own with add_format.
const std::vector<Format>& formats();
void add_format(Format f);

// The lower-case extension of `file` (".glb").
std::string extension_of(const std::string& file);
bool is_usd(const std::string& file);
// The format that reads `file`, or nullptr (USD files and unknown extensions).
const Format* format_for(const std::string& file);
// "a .usd, .usda, .usdc, .usdz, .gltf, .glb, .obj, .fbx or .abc file": what an import accepts, for error messages.
std::string accepted_files();

// The USD layer for a non-USD `file`: converted on first use, then kept for the session while the file's size and
// modification time stay the same (a newer file is converted again). Its identifier is what a reference points at.
pxr::SdfLayerRefPtr converted_layer(const std::string& file);

}  // namespace r3d
