// The GPU output step (gpu_output.rs). OUT: a frame's halves to output codes; FLAGS: per BLOCK pixels of a row, bit 0
// = a pixel the CPU must redo, bit 1 = differs from the picture the target slot holds (`prev`). LUMA / CHROMA: the
// 8-bit output codes (`cur`) to the encoder's NV12 planes, nv12.rs's integer formula and constants (its `glsl_defines`).
uniform sampler2D src;
uniform usampler2D codes;
uniform usampler2D cur;
uniform usampler2D prev;
uniform uint deep;
uniform uint screen;
uniform uint compare;
uniform int width;
// The half a value read from the F16 frame came from (exact: every half is an f32). Not finite: kept not finite.
uint bits(float v) {
    uint u = floatBitsToUint(v), s = (u >> 16u) & 0x8000u, e = (u >> 23u) & 0xFFu, m = u & 0x7FFFFFu;
    if (e == 255u) return s | 0x7C00u | (m != 0u ? 0x200u : 0u);
    if (e > 112u) return s | ((e - 112u) << 10u) | (m >> 13u);
    if (e < 103u) return s;
    return s | ((m | 0x800000u) >> (126u - e));
}
bool finite(uint h) { return (h & 0x7C00u) != 0x7C00u; }
// 0: transparent, 1: opaque with finite channels (the table answers), 2: the CPU's.
uint kind(uvec4 h) {
    if (!finite(h.a) || (h.a & 0x8000u) != 0u || h.a == 0u) return 0u;
    return h.a >= 0x3C00u && finite(h.r) && finite(h.g) && finite(h.b) ? 1u : 2u;
}
uvec4 halves(ivec2 p) { vec4 c = texelFetch(src, p, 0); return uvec4(bits(c.r), bits(c.g), bits(c.b), bits(c.a)); }
uint dither(uint x, uint y, uint c) {
    uint h = (x * 0x9E3779B1u) ^ (y * 0x85EBCA77u) ^ (c * 0xC2B2AE3Du);
    h ^= h >> 15u; h *= 0x2C1B3C6Du; h ^= h >> 12u; h *= 0x297A2D39u; h ^= h >> 15u;
    return h >> 8u;
}
uint code(uint h, uvec2 p, uint k) {
    uint e = texelFetch(codes, ivec2(int(h & 255u), int(h >> 8u)), 0).r;
    if (deep != 0u) return e;
    uint t = e >> 8u;
    return (e & 255u) + (t != 0u && dither(p.x, p.y, k) >= t ? 1u : 0u);
}
#if defined(LUMA) || defined(CHROMA)
// A pixel over black, each channel rounded to a code (nv12.rs `over_black`). Wrapping uint sums, as nv12.rs.
uvec3 over_black(ivec2 p) { uvec4 c = texelFetch(cur, p, 0); return (c.rgb * c.a + 127u) / 255u; }
#endif
#if defined(LUMA)
layout(location = 0) out uint o;
void main() {
    uvec3 q = over_black(ivec2(gl_FragCoord.xy));
    o = (Y0 + YR * q.r + YG * q.g + YB * q.b) >> FRAC;
}
#elif defined(CHROMA)
layout(location = 0) out uvec2 o;
void main() {
    ivec2 p = ivec2(gl_FragCoord.xy) * 2;
    uvec3 s = over_black(p) + over_black(p + ivec2(1, 0)) + over_black(p + ivec2(0, 1)) + over_black(p + ivec2(1, 1));
    o = uvec2((C0 + CBB * s.b - CBR * s.r - CBG * s.g) >> FRAC, (C0 + CRR * s.r - CRG * s.g - CRB * s.b) >> FRAC);
}
#elif defined(FLAGS)
layout(location = 0) out uint o;
void main() {
    int y = int(gl_FragCoord.y), x0 = int(gl_FragCoord.x) * BLOCK;
    o = 0u;
    for (int x = x0; x < min(x0 + BLOCK, width); x++) {
        uvec4 c = texelFetch(cur, ivec2(x, y), 0);
        if (c.a == 1u) o |= 1u;
        if (compare != 0u && c != texelFetch(prev, ivec2(x, y), 0)) o |= 2u;
    }
}
#else
layout(location = 0) out uvec4 o;
void main() {
    uvec2 p = uvec2(gl_FragCoord.xy);
    uvec4 h = halves(ivec2(p));
    uint k = kind(h);
    // A pixel the CPU redoes is marked by an alpha of 1, which no answered pixel has (0 or the full alpha): a slot's
    // row that held one and now holds none is then seen as changed.
    if (k != 1u) { o = uvec4(0u, 0u, 0u, k == 2u ? 1u : 0u); return; }
    uvec3 c = uvec3(code(h.r, p, 0u), code(h.g, p, 1u), code(h.b, p, 2u));
    o = uvec4(screen != 0u ? c.bgr : c, deep != 0u ? 65535u : 255u);
}
#endif
