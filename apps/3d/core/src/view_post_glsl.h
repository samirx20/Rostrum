// The live viewport's picture passes on the graphics card (view_post.h), as GLSL. Every pass draws one triangle
// over the picture and reads its inputs pixel for pixel (texelFetch), so nothing is filtered or moved.
#pragma once

namespace r3d::glsl {

constexpr const char* kVertex = R"(#version 410 core
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
})";

// view-space position of pixel p from Storm's depth (GL rows, bottom up)
constexpr const char* kViewPos = R"(
uniform sampler2D depthTex;
uniform mat4 invProj;
uniform ivec2 isize;
vec3 viewPos(ivec2 p) {
  p = clamp(p, ivec2(0), isize - 1);
  float d = texelFetch(depthTex, p, 0).r;
  vec4 v = invProj * vec4((vec2(p) + 0.5) / vec2(isize) * 2.0 - 1.0, d * 2.0 - 1.0, 1.0);
  return v.xyz / v.w;
}
bool empty(ivec2 p) { return texelFetch(depthTex, clamp(p, ivec2(0), isize - 1), 0).r >= 1.0; }
)";

// Contact shading: how much of the hemisphere over each point nearby surfaces hide, within `radius` scene units
// (24 samples on a spiral turned per pixel; the combine pass smooths the grain). 1 = open, 0 = closed in.
// The samples crowd towards the point (distance ~ t^1.5, not the even spread of sqrt t): where a thing touches the
// floor the darkness lives in the last few centimetres, and evenly spread samples (up to 160 px out) all but missed
// it, so a ball on the ground looked lit underneath and floating (3d-cl7). Squared at the end: Storm's sky light is
// unshadowed, so this pass is the only thing that takes it away, and a straight estimate came out about half as dark
// as Cycles at a contact.
constexpr const char* kAo = R"(
uniform float radius;     // scene units
uniform float pxPerUnit;  // picture pixels per scene unit at distance 1
out float ao;
void main() {
  ivec2 p = ivec2(gl_FragCoord.xy);
  if (empty(p)) { ao = 1.0; return; }
  vec3 P = viewPos(p);
  vec3 r = viewPos(p + ivec2(1, 0)), l = viewPos(p - ivec2(1, 0)), u = viewPos(p + ivec2(0, 1)), b = viewPos(p - ivec2(0, 1));
  vec3 dx = abs(r.z - P.z) < abs(P.z - l.z) ? r - P : P - l;   // the side that stays on this surface
  vec3 dy = abs(u.z - P.z) < abs(P.z - b.z) ? u - P : P - b;
  vec3 N = normalize(cross(dx, dy));
  if (dot(N, P) > 0.0) N = -N;                                   // facing the camera
  float rpx = min(radius * pxPerUnit / -P.z, 160.0);
  if (rpx < 1.5) { ao = 1.0; return; }
  float turn = 6.2831853 * fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
  const int n = 24;
  float occ = 0.0, r2 = radius * radius;
  for (int i = 0; i < n; ++i) {
    float t = (float(i) + 0.5) / float(n), a = float(i) * 2.3999632 + turn;
    vec3 v = viewPos(p + ivec2(round(vec2(cos(a), sin(a)) * max(rpx * t * sqrt(t), 1.0)))) - P;
    float vv = dot(v, v);
    float near = vv / r2;
    occ += max(0.0, 1.0 - near * near) * max(0.0, dot(v, N) * inversesqrt(vv + 1e-12) - 0.05) / 0.95;
  }
  float open = clamp(1.0 - 2.0 * occ / float(n), 0.0, 1.0);
  ao = open * open;
})";

// The colour with the contact shading laid in: the shading smoothed over 5 x 5 pixels of about the same depth,
// raised to `strength`.
constexpr const char* kCombine = R"(
uniform sampler2D colorTex;
uniform sampler2D aoTex;
uniform float strength;
out vec4 lit;
void main() {
  ivec2 p = ivec2(gl_FragCoord.xy);
  vec4 c = texelFetch(colorTex, p, 0);
  if (empty(p)) { lit = c; return; }
  float z0 = viewPos(p).z, sum = 0.0, wsum = 0.0;
  for (int y = -2; y <= 2; ++y)
    for (int x = -2; x <= 2; ++x) {
      ivec2 q = clamp(p + ivec2(x, y), ivec2(0), isize - 1);
      float w = exp(-abs(viewPos(q).z - z0) / (0.02 * abs(z0)));
      sum += texelFetch(aoTex, q, 0).r * w;
      wsum += w;
    }
  lit = vec4(c.rgb * pow(sum / wsum, strength), c.a);
})";

// Onion skin: one ghost (its items alone, lit, at another frame) laid over the picture, see-through, in its tint;
// its own light and shade kept as brightness so the shape still reads. Premultiplied "over", like Storm's colour.
constexpr const char* kGhost = R"(
uniform sampler2D litTex;
uniform sampler2D ghostTex;
uniform vec3 tint;
uniform float opacity;
out vec4 lit;
void main() {
  ivec2 p = ivec2(gl_FragCoord.xy);
  vec4 c = texelFetch(litTex, p, 0), g = texelFetch(ghostTex, p, 0);
  float a = clamp(g.a, 0.0, 1.0) * opacity;
  float l = dot(max(g.rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
  vec3 col = tint * (0.35 + 0.65 * l / (l + 0.18));
  lit = vec4(c.rgb * (1.0 - a) + col * a, c.a * (1.0 - a) + a);
})";

// The shown picture: depth of field (a gather over a disc as wide as the lens blurs that point), exposure, the
// background where the picture is transparent, OpenColorIO's display transform, the selection ring, then the thin hover outline (1 px, the accent laid over the
// picture at hoverMix: lighter than the ring, which wins where both are). Written top
// row first, so the read-back needs no flip.
constexpr const char* kFinalHead = R"(
uniform sampler2D litTex;
uniform sampler2D maskTex, hoverTex;
uniform int hasMask, hasHover, ring, lens;
uniform float hoverMix;
uniform float gain, cocScale, focus, maxR;  // depth of field: blur diameter in pixels = cocScale * |D - focus| / D
uniform vec3 bg, accent;
out vec4 frag;
)";

constexpr const char* kFinalBody = R"(
float dist(ivec2 p) { return empty(p) ? 1e9 : -viewPos(p).z; }
float blurR(float D) { return min(maxR, 0.5 * cocScale * abs(D - focus) / D); }
vec4 lensed(ivec2 p) {
  vec4 c = texelFetch(litTex, p, 0);
  float Dc = dist(p), rc = blurR(Dc);
  if (rc < 0.5) return c;
  int n = int(clamp(rc * rc * 0.75, 8.0, 96.0));
  vec4 sum = c;
  float w = 1.0;
  for (int i = 0; i < n; ++i) {
    float t = (float(i) + 0.5) / float(n), a = float(i) * 2.3999632;
    vec2 o = vec2(cos(a), sin(a)) * rc * sqrt(t);
    ivec2 q = clamp(p + ivec2(round(o)), ivec2(0), isize - 1);
    float Ds = dist(q);
    // a point behind this one shows through its blur; one in front only where its own blur reaches here
    float ws = (Ds >= Dc * 0.98 || blurR(Ds) >= length(o)) ? 1.0 : 0.0;
    sum += texelFetch(litTex, q, 0) * ws;
    w += ws;
  }
  return sum / w;
}
void main() {
  ivec2 o = ivec2(gl_FragCoord.xy), p = ivec2(o.x, isize.y - 1 - o.y);
  vec4 c = lens == 1 ? lensed(p) : texelFetch(litTex, p, 0);
  float a = clamp(c.a, 0.0, 1.0);
  vec4 shown = OCIODisplay(vec4(c.rgb * gain + bg * gain * (1.0 - a), 1.0));
  shown.a = 1.0;
  bool ringed = false;
  if (hasMask == 1 && texelFetch(maskTex, p, 0).a <= 0.5) {
    bool near = false;
    for (int y = -ring; y <= ring && !near; ++y)
      for (int x = -ring; x <= ring && !near; ++x)
        near = texelFetch(maskTex, clamp(p + ivec2(x, y), ivec2(0), isize - 1), 0).a > 0.5;
    if (near) shown.rgb = accent;
    ringed = near;
  }
  if (hasHover == 1 && !ringed && texelFetch(hoverTex, p, 0).a <= 0.5) {
    bool near = false;
    for (int y = -1; y <= 1 && !near; ++y)
      for (int x = -1; x <= 1 && !near; ++x)
        near = texelFetch(hoverTex, clamp(p + ivec2(x, y), ivec2(0), isize - 1), 0).a > 0.5;
    if (near) shown.rgb = mix(shown.rgb, accent, hoverMix);
  }
  frag = clamp(shown, 0.0, 1.0);
})";

}  // namespace r3d::glsl
