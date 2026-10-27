// Rigid bodies (brief 25; ENGINE_CONTRACT.md § Simulation): the `simulate` request's physics, with Jolt Physics
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

constexpr int kVersion = 1;  // this file's own behaviour; any change that moves a result bumps it (part of the key)
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
  enum Shape { Exact, Box, Sphere } shape = Exact;
  std::vector<V3> points;       // its surface, in its own frame (metres, its scale already in): hull, box, sphere
  std::vector<V3> triangles;    // a still body's Exact shape: three points per triangle, same frame
  V3 pos{};                     // its frame's origin at the start (world)
  Q rot{0, 0, 0, 1};            // its frame's turn at the start (world)
  V3 velocity{};                // world m/s at the start
  std::string name() const { return copy < 0 ? item : item + " copy " + std::to_string(copy); }
};

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
  int atRest = 0;                     // falling bodies resting at the last frame
  double ms = 0, frameMs = 0;         // whole run, and per frame of the shot (mean)
};

// Runs the bodies from `start` to `end`. `progress(i, of, frame)` after each frame. Throws Failure (a body starts
// inside another, flies away, falls past everything) or Error (a shape that can't be built).
Result run(const Setup& setup, const std::vector<Body>& bodies, const std::function<void(int, int, int)>& progress);

}  // namespace r3d::sim
