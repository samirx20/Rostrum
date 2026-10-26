// The render-thread side of the in-process viewport proof: the USD stage, the clay (apps/3d/core's clay_* files,
// compiled in unchanged) and Storm. No Qt here and no Qt in what it includes: pxr + epoxy on one side, Qt on the
// other (view.cpp), so neither's GL headers or macros meet.
//
// Threading (the README's open design point): everything in here is owned by Qt Quick's render thread. The GUI thread
// never touches the stage; it queues its pointer events, synchronize() hands them over while the GUI thread is
// paused, and render() applies them (dab -> mesh -> USD) and then draws, in that order, on one thread. So Hydra never
// reads a stage someone else is editing, and the GUI thread never waits for a dab.
#pragma once
#include <memory>
#include <string>
#include <vector>

namespace pview {

struct Cam {
  double yaw = 0, pitch = 0.25, dist = 0.7;  // radians, metres; orbit about `target`
  double target[3] = {0, 0, 0};
  double fovDeg = 40;
};

struct Input {
  enum Kind { Begin, Move, End, Orbit } kind = Move;  // Orbit: a camera move, only measured
  float x = 0, y = 0;  // item pixels, top-left origin
  double tSent = 0;    // ms (steady clock) when the driver sent the OS-level event into Qt
  double tRecv = 0;    // ms when the item's mouse handler got it (GUI thread)
};

struct Options {
  int items = 0;               // extra prims around the clay (the orbit scene: 300)
  bool head = false;           // the clay proof's scripted head (head.cpp, grain 0.625 mm) instead of a plain ball
  float clayRadius = 0.15f;    // metres
  float detail = 0.002f;       // metres per voxel
  float brushRadius = 0.012f;  // metres
  float strength = 0.5f;
  bool finish = true;          // glFinish after Storm's draw (the times then include the GPU's own work)
};

// times of one render() call, ms
struct FrameTimes {
  int inputs = 0, dabs = 0, blocks = 0;
  double dab = 0, mesh = 0, usd = 0, storm = 0;
};

double now_ms();  // steady clock
std::string probe_raw_wgl();  // the core's way of making a GL context, its GL_VERSION

class Scene {
 public:
  explicit Scene(const Options& o);  // stage + clay ball; call on the render thread with Qt's GL context current
  ~Scene();
  // apply pointer inputs (left drag sculpts) seen through `cam` in a w x h item
  void apply(const std::vector<Input>& in, const Cam& cam, int w, int h, FrameTimes& t);
  // draw the stage with Storm into GL texture `colorTex` (the item's RGBA8 colour buffer)
  void draw(unsigned colorTex, int w, int h, const Cam& cam, FrameTimes& t);
  // the last draw's pixels, top row first (RGBA8)
  std::vector<unsigned char> read(int w, int h);
  std::string gl_renderer() const;
  int clay_blocks() const;

 private:
  struct Impl;
  std::unique_ptr<Impl> p_;
};

}  // namespace pview
