// Rigid bodies (brief 25) and cloth (brief 26b; ENGINE_CONTRACT.md § Simulation): the `simulate` request's physics, with Jolt Physics
// (third_party/jolt, MIT). This half knows nothing of USD: sim_request.cpp reads each body's shape and start pose from
// the held stage and hands them here as plain numbers; the rows come back in world space.
// One thread, Jolt's cross-platform determinism: the same bodies always give the same rows (the result is stored once,
// keyed by its inputs, and only read when scrubbing or rendering).
#pragma once
#include <array>
#include <functional>
#include <string>
#include <vector>

#include "error.h"

namespace r3d::sim {

constexpr int kVersion = 19; // this file's own behaviour; any change that moves a result bumps it (part of the key)
std::string jolt_version();  // "5.6.0"

using V3 = std::array<double, 3>;
using Q = std::array<double, 4>;  // x y z w

struct Body {
  std::string item;
  int copy = -1;                // a copies item's copy number; -1 for a plain item
  bool falls = true;            // false: stays still (a collider)
  double mass = 0;              // kg; 0 = from its size, as solid plastic (1100 kg/m³)
  double bounce = 0.2, friction = 0.6;
  bool asleep = false;          // Starts: Asleep until hit
  int wake = 0;                 // Falls from: frames after the start it holds still (others land on it), then falls
  bool appears = false;         // a copy in a stream: not there at all until its wake frame (collides with nothing), then falls
  enum Shape { Exact, Box, Sphere } shape = Exact;
  std::vector<V3> points;       // its surface, in its own frame (metres, its scale already in): hull, box, sphere
  std::vector<V3> triangles;    // a still body's Exact shape: three points per triangle, same frame
  V3 pos{};                     // its frame's origin at the start (world)
  Q rot{0, 0, 0, 1};            // its frame's turn at the start (world)
  V3 velocity{};                // world m/s at the start
  std::string name() const { return copy < 0 ? item : item + " copy " + std::to_string(copy); }
};

// A shape that drapes (brief 26b): a Jolt soft body, one particle per point, edges + bend constraints from its triangles.
struct Cloth {
  std::string item;
  double weight = 0.2;          // kg per m² (each point carries a third of its triangles' weight)
  double stiffness = 0.3;       // 0 folds like silk, 0.3 hangs in folds like cotton, 1 bends like thin card
  double friction = 0.6;
  double air = 1;               // air drag: 0 none (falls like a stone), 1 room air, up to 4 (a parachute)
  double wind = 0;              // Breeze (cloth_wind.h): m/s of moving air in slow gusts, 0 still air
  double windTurn = 0;          // its direction, degrees about up: 0 towards +x, 90 towards -z
  enum Pin { None, Top, Bottom, Left, Right, Front, Back } pinned = None;  // that side of its world bounds at the start
  std::vector<V3> points;                       // world, at the start (after refine)
  std::vector<std::array<int, 3>> triangles;    // into points
  std::vector<std::array<float, 2>> st;         // per point (u v), carried to the stored file
  bool refined = false;                         // refine made it finer
  int wake = 0;                                 // Falls from: frames after the start it holds its first shape (others land on it), then falls
  // A garment (PR7): pairs of points sewn together (one piece's edge to another's), pulled closed over `sewTime` seconds
  // from the start (each pair's gap shrinking evenly to nothing), then held welded. A cloth with seams arrives already fine
  // (the app triangulates its pattern), so refine doesn't split it: it only drops what has no area and renumbers the pairs.
  std::vector<std::array<int, 2>> seams;
  double sewTime = 0.5;
  std::string name() const { return item; }
};

// Makes a cloth's mesh fine enough to fold, in whatever space its points are: a single four-point face (a plane) becomes a
// 96 × 96 grid; anything else has every triangle split in four until no edge is longer than 1/96 of its size (at most
// kMaxClothTriangles); a cloth with seams is only triangulated. Drops faces with no area and points no face uses (seam
// pairs follow the renumbering; a pair on a dropped point is dropped). Deterministic. (64 folded in 2–3 cm facets:
// broad rubbery bulges with a stepped outline; 96 gives fabric-sized wrinkles at about twice the simulation time.)
constexpr int kClothGrid = 96;
constexpr size_t kMaxClothTriangles = 40000;
void refine(Cloth& c, const std::vector<std::vector<int>>& faces);

struct Setup {
  int start = 0, end = 0;
  double fps = 24;
  bool ground = true;
  double groundY = 0;
};

// A body that can't be simulated: which, at which frame, and what to do. serve.cpp sends the fields with the error.
struct Failure : Error {
  Failure(const Body& b, int frame_, const std::string& problem, const std::string& fix_)
      : Error(b.name() + " " + problem + " at frame " + std::to_string(frame_) + ": " + fix_),
        item(b.item), copy(b.copy), frame(frame_), fix(fix_) {}
  Failure(const Cloth& c, int frame_, const std::string& problem, const std::string& fix_)
      : Error(c.name() + " " + problem + " at frame " + std::to_string(frame_) + ": " + fix_),
        item(c.item), copy(-1), frame(frame_), fix(fix_) {}
  std::string item;
  int copy;
  int frame;
  std::string fix;
};

struct Pose {
  V3 pos;
  Q rot;
};

struct Result {
  std::vector<int> rows;              // index into the bodies given, for each falling body (the rows' order)
  std::vector<std::vector<Pose>> frames;  // [frame - start][row], world
  std::vector<std::vector<float>> cloth;  // [cloth] frames × points × xyz, world
  int atRest = 0;                     // falling bodies resting at the last frame
  double ms = 0, frameMs = 0;         // whole run, and per frame of the shot (mean)
};

// Runs the bodies and cloths from `start` to `end`. `progress(i, of, frame)` after each frame. Throws Failure (a body
// starts inside another, flies away, falls past everything; a cloth tears apart, flies apart, falls past everything, or its
// pinned edge holds all of it) or Error (a shape that can't be built).
Result run(const Setup& setup, const std::vector<Body>& bodies, const std::vector<Cloth>& cloths,
           const std::function<void(int, int, int)>& progress);

}  // namespace r3d::sim
