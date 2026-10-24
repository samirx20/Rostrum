// Pieces shared by the item types that make a UsdGeomMesh (stage_items.cpp `mesh`, stage_combine.cpp
// `combine`): the shape a mesh's props describe, and writing a MeshData onto a prim.
#pragma once
#include <string>

#include <pxr/base/js/value.h>
#include <pxr/base/tf/token.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/prim.h>
#include <pxr/usd/usdGeom/mesh.h>

#include "extrude.h"
#include "item_track.h"
#include "primitives.h"

namespace r3d {

// The mesh a `mesh` item's props describe, in its own space. `groups` gets the faces of each part
// (front, bevel, side, back) for an outline; other shapes leave it empty.
MeshData shape(Reader& p, FaceGroups& groups);
// Marks the mesh fields the chosen shape doesn't use as known (the compiler sends every field).
void mesh_known(Reader& p);
// Points, vertex normals, counts, indices, face-varying st and extent; no subdivision.
void write_mesh(PXR_NS::UsdGeomMesh m, const MeshData& d);
// Binds material `mat` ("" = none) to `prim`; `where` names the field in errors (stage_items.cpp).
void bind_material(Item& it, const PXR_NS::UsdPrim& prim, const std::string& mat, const std::string& where,
                   const PXR_NS::TfToken& strength);
// An editable mesh's `faceMaterials` as a "materialBind" partition of GeomSubsets over the drawn faces `d`
// (after smoothing, through d.base_face); "" = the mesh's material `mat`. Nothing when every face is the item's.
void bind_face_materials(Item& it, PXR_NS::UsdGeomMesh m, const MeshData& d, const std::string& mat);
// A `combine` item at `path`: one mesh made from its children, which are inputs only (stage_combine.cpp).
void build_combine(Item& it, const PXR_NS::JsArray& children, const PXR_NS::SdfPath& path);

}  // namespace r3d
