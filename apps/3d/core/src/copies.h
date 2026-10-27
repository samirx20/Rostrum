// `copies` items (ENGINE_CONTRACT.md § 2, Copies): a UsdGeomPointInstancer whose children are its sources (the
// prototypes, drawn only through it). The core lays the copies out (line, grid, circle, or scattered on a surface item's
// mesh), varies them from the seed, puts held copies where they were put, and bakes the effectors per frame.
// One place for the layout: the scene build and the live `copies` request both call lay_out + write.
#pragma once
#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/quatf.h>
#include <pxr/base/gf/range3d.h>
#include <pxr/base/gf/vec3f.h>
#include <pxr/base/js/value.h>
#include <pxr/usd/sdf/path.h>
#include <pxr/usd/usd/stage.h>

#include <string>
#include <vector>

namespace r3d {
class Item;
struct ItemsContext;

namespace copies {

struct Params {
  std::string layout = "line";  // line | grid | circle | surface
  int count = 6, columns = 4;
  double spacing[3] = {0.2, 0, 0};
  double radius = 0.5;
  bool faceOut = true;
  std::string surface;          // item id (layout surface)
  bool byDensity = false;
  double density = 10, minSpacing = 0;
  bool alongSurface = true;
  bool onTop = true;  // surface: only its faces that look up (world +Y), where things can rest
  unsigned seed = 0;
  double varyMove = 0, varyTurn = 0, varyScale = 0;
  std::string seenBy;           // camera id: only the copies it sees are drawn ("" = all)
  int seenW = 1920, seenH = 1080;
};

// a copy a person (or copies.hold) put somewhere: in the copies item's own space, never moved by the layout
struct Held {
  int copy = 0;
  double x = 0, y = 0, z = 0, rx = 0, ry = 0, rz = 0, s = 1;
};

// "Change near": per frame, w = falloff(distance(copy, centre) / radius) changes each copy near the centre
struct Effector {
  std::string id;
  enum Kind { Scale, Turn, Push, Colour } kind = Scale;
  bool smooth = true;
  int axis = 1;
  // one value, or one per frame of the shot
  std::vector<PXR_NS::GfVec3f> centre, colour;  // world; linear RGB
  std::vector<double> amount, radius;
  bool moves() const { return centre.size() > 1 || amount.size() > 1 || radius.size() > 1 || colour.size() > 1; }
};

struct Copy {
  PXR_NS::GfVec3f pos;
  PXR_NS::GfQuatf rot = PXR_NS::GfQuatf::GetIdentity();
  float scale = 1;
  int proto = 0;
};

// the surface's triangles in the copies item's space, with world areas (the copies' density is per world m²)
struct Surface {
  std::string id;
  std::vector<PXR_NS::GfVec3f> a, b, c, normal;
  std::vector<double> cumulative;  // running world area
  bool empty() const { return a.empty(); }
};

// One copies item as built, kept by the core between requests (the live `copies` request, pick, the seen test).
struct State {
  std::string id;
  PXR_NS::SdfPath path;
  int start = 0, end = 0;
  Params p;
  std::vector<Held> held;
  std::vector<Effector> effectors;
  std::vector<std::string> sources;           // child ids, in prototype order
  std::vector<PXR_NS::GfRange3d> bounds;      // each source's bounds in the copies item's space, before the copy's move
  Surface surf;
  std::vector<Copy> laid;                     // the copies without effectors, index = copy id
  bool animated = false;                      // effectors baked per frame
  int seen = -1;                              // copies the camera sees (-1: not tested)
  std::vector<bool> shown;                    // per copy: drawn (the seen test); empty = all
};

// Reads the node (props, held, effectors), defines the instancer at `path` and builds the sources under it.
// The layout waits for lay_out_all (a surface may be built after this item).
void build(Item& it, const PXR_NS::JsArray& children, const PXR_NS::JsArray& held, const PXR_NS::JsArray& effectors,
           const PXR_NS::SdfPath& path);
// After every item is built: each copies item's surface read, laid out and written.
void lay_out_all(const PXR_NS::UsdStageRefPtr& stage, std::vector<State>& all);

// The live `copies` request: `props` (any of the node's props) and, when given, `held` replace the state's; the copies
// are laid out again and written on `stage` in one change. Returns the time taken, ms.
double relay(const PXR_NS::UsdStageRefPtr& stage, State& s, const PXR_NS::JsObject& props, const PXR_NS::JsValue* held);

// Each copy's points for the seen test at `frame` (world): its base and its bounds' centre, two per copy.
std::vector<PXR_NS::GfVec3d> seen_points(const PXR_NS::UsdStageRefPtr& stage, const State& s, int frame);
// Writes invisibleIds from s.shown.
void write_shown(const PXR_NS::UsdStageRefPtr& stage, const State& s);

// The copy under a picked world point at `frame`: `hint` (Hydra's instance index) when it holds the point, else the
// copy whose bounds hold it (nearest centre); -1 when none.
int copy_at(const PXR_NS::UsdStageRefPtr& stage, const State& s, int frame, const PXR_NS::GfVec3d& point, int hint,
            int proto);

}  // namespace copies
}  // namespace r3d
