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
  double varyStart = 0;         // s: a falling copy waits up to this much longer before it falls (from the seed)
  std::string seenBy;           // camera id: only the copies it sees are drawn ("" = all)
  int seenW = 1920, seenH = 1080;
};

// a copy a person (or copies.hold) put somewhere: in the copies item's own space, never moved by the layout.
// (v1.25) A keyed copy (Turn into keys on a falling copies item, copies.key) is a held one whose x y z rx ry rz may each be
// left out (the layout's value) or move: `track[i]` one value per frame of the shot (empty: still). `s` left out: the
// layout's size.
struct Held {
  int copy = 0;
  double v[7] = {0, 0, 0, 0, 0, 0, 1};    // x y z rx ry rz s
  bool given[7] = {true, true, true, true, true, true, true};
  std::vector<double> track[6];
  bool keyed() const;
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

// A stored simulation of the copies (brief 25, the node's `sim`): rows `row`.. of `bodies.bin` (frames × `of` rows × 7
// floats: x y z qx qy qz qw in the copies item's space), frames `start`..`end`. `step` holds each pose 2 or 3 frames (On 2s,
// On 3s, counted from the shot's start); `smooth` keeps every nth pose and blends between (Simplify).
struct SimTrack {
  std::string file;
  int row = 0, rows = 0, of = 0, start = 0, end = 0, step = 1, smooth = 1;
  std::vector<float> data;
  bool on() const { return !file.empty(); }
  // copy c's pose at shot frame f (c < rows)
  void pose(int c, int f, int shot_start, PXR_NS::GfVec3f* pos, PXR_NS::GfQuatf* rot) const;
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
  SimTrack sim;                               // the stored fall, when it has one
  bool late = false;                          // on a clay: laid out after the clays' sync (lay_out_late)
};

// Reads the node (props, held, effectors), defines the instancer at `path` and builds the sources under it.
// The layout waits for lay_out_all (a surface may be built after this item).
void build(Item& it, const PXR_NS::JsArray& children, const PXR_NS::JsArray& held, const PXR_NS::JsArray& effectors,
           const PXR_NS::JsObject* sim, const PXR_NS::SdfPath& path);
// After every item is built: each copies item's surface read, laid out and written. One whose surface is a clay (its
// Xform among `clays`) waits (`late`): a clay's surface reaches the held stage only in the clay store's sync.
void lay_out_all(const PXR_NS::UsdStageRefPtr& stage, std::vector<State>& all, const PXR_NS::SdfPathVector& clays);
// A copies item that waited for its clay surface, laid out and written on the held stage once the clays are synced.
void lay_out_late(const PXR_NS::UsdStageRefPtr& stage, State& s);

// The live `copies` request: `props` (any of the node's props) and, when given, `held` replace the state's; the copies
// are laid out again and written on `stage` in one change. Returns the time taken, ms.
double relay(const PXR_NS::UsdStageRefPtr& stage, State& s, const PXR_NS::JsObject& props, const PXR_NS::JsValue* held);

// The copies at `frame` (layout + keyed copies + effectors, in the copies item's space) and the item's world place then:
// what a simulation starts from.
std::vector<Copy> at_frame(const PXR_NS::UsdStageRefPtr& stage, const State& s, int frame, PXR_NS::GfMatrix4d* world);
// The copies as drawn at `frame`: at_frame, or with a stored fall (s.sim) where each simulated copy fell (no effectors),
// as `write` puts them on the stage. Pick and the seen test use this.
std::vector<Copy> drawn_at(const PXR_NS::UsdStageRefPtr& stage, const State& s, int frame, PXR_NS::GfMatrix4d* world);
// Each copy's points for the seen test at `frame` (world): its base and its bounds' centre, two per copy.
std::vector<PXR_NS::GfVec3d> seen_points(const PXR_NS::UsdStageRefPtr& stage, const State& s, int frame);
// Everything the copies take at `frame` as drawn (drawn_at), world, aligned: each copy's source bounds moved with it
// (framing a copies item, the `copies_box` request). Empty when there are no copies.
PXR_NS::GfRange3d world_box(const PXR_NS::UsdStageRefPtr& stage, const State& s, int frame);
// The frames copy `copy` waits before it falls, on top of its item's Falls from: up to varyStart seconds, from the seed.
int start_delay(const Params& p, int copy, double fps);
// Writes invisibleIds from s.shown.
void write_shown(const PXR_NS::UsdStageRefPtr& stage, const State& s);

// The copy under a picked world point at `frame`: `hint` (Hydra's instance index) when it holds the point, else the
// copy whose bounds hold it (nearest centre); -1 when none.
int copy_at(const PXR_NS::UsdStageRefPtr& stage, const State& s, int frame, const PXR_NS::GfVec3d& point, int hint,
            int proto);

}  // namespace copies
}  // namespace r3d
