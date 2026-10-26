// Clay: the steps that make a clay, and the small vector maths they use (no OpenVDB here). Positions are in the
// clay item's own space, metres. Moved from proofs/3d-clay (clay.h, session.h).
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace r3d::clay {

constexpr float kBand = 4.0f;  // half width of the stored distance band, voxels

struct V3 {
  float x = 0, y = 0, z = 0;
};

inline V3 add(V3 a, V3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
inline V3 sub(V3 a, V3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
inline V3 mul(V3 a, float s) { return {a.x * s, a.y * s, a.z * s}; }
inline float dot(V3 a, V3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
inline V3 cross(V3 a, V3 b) { return {a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x}; }
inline float len(V3 a) { return std::sqrt(dot(a, a)); }
inline V3 unit(V3 a) { return mul(a, 1.0f / std::max(1e-12f, len(a))); }

// Add / Carve: raise or dig (pieces and dabs). Smooth: even out. Pull: move the clay under the brush along `b` (the
// drag). Flatten: towards the average surface under the brush (inverted: puff out to a low dome above it). Crease: a
// sharp line, dug and pinched in along `b` (inverted: pinched up to a ridge). Mask: paints the clay's mask (0..1, a
// second grid in the volume; inverted: takes it away); every other dab changes the clay by (1 - mask) as much.
enum class Op : uint8_t { Add, Carve, Smooth, Pull, Flatten, Crease, Mask };
enum class Kind : uint8_t { Piece, Stamp };  // a shape put in (sphere / capsule, with blend), or one brush dab

struct Step {
  Kind kind = Kind::Piece;
  Op op = Op::Add;
  V3 a, b;               // piece: sphere centre a, or capsule a..b (a == b: sphere). stamp: a = point on the surface;
                         // b = Pull's vector or Crease's line direction (unit)
  V3 n;                  // stamp: surface normal at a (out of the clay)
  float radius = 0.1f;   // clay space, metres (a stamp: the brush's radius x radiusScale)
  float blend = 0.0f;    // piece: smooth join distance, metres
  float strength = 0.5f; // stamp: 0..1 (the brush's strength x strengthScale)
  bool mirror = false;   // also at x -> -x (the same step, mirrored, in the same pass)
  uint32_t stroke = 0;   // stamp: the stroke it belongs to; 0 = alone
  bool accumulate = true;  // Add / Carve: off = a stroke raises (digs) at most one dab's height from where it began
  float falloff = 0.5f;  // stamp: 0 soft .. 1 hard edge (0.5: CL1's curve, bit for bit)
  bool invert = false;   // stamp: Flatten puffs out, Crease makes a ridge, Mask takes the mask away
  float radiusScale = 1.0f, strengthScale = 1.0f;  // stamp: pen pressure, as stored in the dab file (CLD2)
};

struct Brush {
  Op op = Op::Add;
  float radius = 0.03f;   // clay space, metres
  float strength = 0.5f;  // 0..1
  bool mirror = false;
  bool accumulate = false;  // off: repeated passes of one stroke don't pile up (Nomad's Accumulate)
  float falloff = 0.5f;     // 0 soft .. 1 hard edge
  float spacing = 0.3f;     // dabs every `spacing` x the radius along the path (0.05..1)
  bool frontOnly = false;   // a dab whose surface faces away from its ray is skipped (never through a thin part)
  bool invert = false;      // Ctrl's opposite (Flatten, Crease, Mask)
};

// pen pressure 0..1 -> a dab's scales (both size and strength follow the pen; no pen = pressure 1 = 1, 1)
inline float pressure_radius_scale(float p) { return std::min(1.0f, std::max(0.1f, p)); }
inline float pressure_strength_scale(float p) { return std::min(1.0f, std::max(0.0f, p)); }

// "add" | "carve" | "smooth" | "pull" | "flatten" | "crease" | "mask" -> Op; false when unknown
bool op_from_name(const char* name, Op& op);
const char* op_name(Op op);

}  // namespace r3d::clay
