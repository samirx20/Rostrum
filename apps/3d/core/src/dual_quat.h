// Dual-quaternion blending of rigid bone moves (CL6): a point leaning on two bones turns with the blended turn round
// the blended pivot, instead of the average of the two places linear blending gives, so a sharp bend (a high-raised
// arm) keeps its thickness at the joint rather than pinching in. Plain doubles, no state. A move whose 3×3 part is
// not a turn (a scale or a shear) can't be written as one: rigid() says so and the caller blends linearly.
#pragma once

#include <array>
#include <cmath>

namespace r3d::clay {

// real part (w, x, y, z) then dual part (w, x, y, z); a unit one is the move p' = R·p + t
using DualQuat = std::array<double, 8>;

// m row by row is a turn: orthonormal (to 1e-4) and not mirrored
inline bool rigid(const double m[9]) {
  for (int i = 0; i < 3; ++i)
    for (int j = 0; j < 3; ++j) {
      const double d = m[3 * i] * m[3 * j] + m[3 * i + 1] * m[3 * j + 1] + m[3 * i + 2] * m[3 * j + 2];
      if (std::fabs(d - (i == j ? 1.0 : 0.0)) > 1e-4) return false;
    }
  const double det = m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) +
                     m[2] * (m[3] * m[7] - m[4] * m[6]);
  return det > 0;
}

// the turn m (row by row, rigid) and shift t as a unit dual quaternion
inline DualQuat dual_quat(const double m[9], const double t[3]) {
  double w, x, y, z;
  const double tr = m[0] + m[4] + m[8];
  if (tr > 0) {
    const double s = std::sqrt(tr + 1.0) * 2;
    w = 0.25 * s, x = (m[7] - m[5]) / s, y = (m[2] - m[6]) / s, z = (m[3] - m[1]) / s;
  } else if (m[0] > m[4] && m[0] > m[8]) {
    const double s = std::sqrt(1.0 + m[0] - m[4] - m[8]) * 2;
    w = (m[7] - m[5]) / s, x = 0.25 * s, y = (m[1] + m[3]) / s, z = (m[2] + m[6]) / s;
  } else if (m[4] > m[8]) {
    const double s = std::sqrt(1.0 + m[4] - m[0] - m[8]) * 2;
    w = (m[2] - m[6]) / s, x = (m[1] + m[3]) / s, y = 0.25 * s, z = (m[5] + m[7]) / s;
  } else {
    const double s = std::sqrt(1.0 + m[8] - m[0] - m[4]) * 2;
    w = (m[3] - m[1]) / s, x = (m[2] + m[6]) / s, y = (m[5] + m[7]) / s, z = 0.25 * s;
  }
  const double l = std::sqrt(w * w + x * x + y * y + z * z);
  w /= l, x /= l, y /= l, z /= l;
  // dual part = ½ (0, t) · real
  return {w, x, y, z,
          -0.5 * (t[0] * x + t[1] * y + t[2] * z),
          0.5 * (w * t[0] + t[1] * z - t[2] * y),
          0.5 * (w * t[1] + t[2] * x - t[0] * z),
          0.5 * (w * t[2] + t[0] * y - t[1] * x)};
}

// sum += weight × q, q's sign flipped when it points away from `pivot`'s real part (the same turn, the short way)
inline void add_weighted(DualQuat& sum, const DualQuat& q, double weight, const DualQuat& pivot) {
  const double dot = q[0] * pivot[0] + q[1] * pivot[1] + q[2] * pivot[2] + q[3] * pivot[3];
  const double s = dot < 0 ? -weight : weight;
  for (int i = 0; i < 8; ++i) sum[i] += s * q[i];
}

// a blended sum made a move again: m (row by row) and t; false when the sum has no turn left (weights cancelled)
inline bool to_move(const DualQuat& q, double m[9], double t[3]) {
  const double l = std::sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
  if (l < 1e-12) return false;
  const double w = q[0] / l, x = q[1] / l, y = q[2] / l, z = q[3] / l;
  const double ew = q[4] / l, ex = q[5] / l, ey = q[6] / l, ez = q[7] / l;
  m[0] = 1 - 2 * (y * y + z * z), m[1] = 2 * (x * y - w * z), m[2] = 2 * (x * z + w * y);
  m[3] = 2 * (x * y + w * z), m[4] = 1 - 2 * (x * x + z * z), m[5] = 2 * (y * z - w * x);
  m[6] = 2 * (x * z - w * y), m[7] = 2 * (y * z + w * x), m[8] = 1 - 2 * (x * x + y * y);
  // t = 2 · dual · conj(real): w·e⃗ − e_w·v⃗ + v⃗ × e⃗
  t[0] = 2 * (w * ex - ew * x + (y * ez - z * ey));
  t[1] = 2 * (w * ey - ew * y + (z * ex - x * ez));
  t[2] = 2 * (w * ez - ew * z + (x * ey - y * ex));
  return true;
}

}  // namespace r3d::clay
