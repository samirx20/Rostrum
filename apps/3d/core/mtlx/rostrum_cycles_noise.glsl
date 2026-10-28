// Cycles' Noise texture (3D, fBM, normalized, lacunarity 2), so the Quick view draws the pattern Final draws.
// The Noise block's nodegraph (rostrum_blocks.mtlx, written by apps/3d/tools/make_blocks_mtlx.py) calls it with the
// object-space position x scale. Ported from Cycles: kernel/svm/noise.h (Perlin, BSD-3-Clause, Sony Pictures Imageworks
// et al. / Blender Foundation, adapted from Open Shading Language), kernel/svm/fractal_noise.h and noisetex.h and
// util/hash.h (Jenkins' lookup3 hash) (Apache-2.0, Blender Foundation). Every name starts with rx_ (no clash with
// MaterialX's own library).

uint rx_rot(uint x, int k) { return (x << k) | (x >> (32 - k)); }

// lookup3's final(a, b, c), returning c
uint rx_final(uint a, uint b, uint c)
{
    c ^= b; c -= rx_rot(b, 14);
    a ^= c; a -= rx_rot(c, 11);
    b ^= a; b -= rx_rot(a, 25);
    c ^= b; c -= rx_rot(b, 16);
    a ^= c; a -= rx_rot(c, 4);
    b ^= a; b -= rx_rot(a, 14);
    c ^= b; c -= rx_rot(b, 24);
    return c;
}

uint rx_hash2(uint kx, uint ky)
{
    uint s = 0xdeadbeefu + (2u << 2) + 13u;
    return rx_final(s + kx, s + ky, s);
}

uint rx_hash3(uint kx, uint ky, uint kz)
{
    uint s = 0xdeadbeefu + (3u << 2) + 13u;
    return rx_final(s + kx, s + ky, s + kz);
}

float rx_fade(float t) { return t * t * t * (t * (t * 6.0 - 15.0) + 10.0); }

float rx_grad3(uint hash, float x, float y, float z)
{
    uint h = hash & 15u;
    float u = h < 8u ? x : y;
    float vt = (h == 12u || h == 14u) ? x : z;
    float v = h < 4u ? y : vt;
    return ((h & 1u) != 0u ? -u : u) + ((h & 2u) != 0u ? -v : v);
}

float rx_perlin3(vec3 p)
{
    vec3 f = floor(p);
    ivec3 I = ivec3(f);
    vec3 r = p - f;
    uint X = uint(I.x), Y = uint(I.y), Z = uint(I.z);
    float u = rx_fade(r.x), v = rx_fade(r.y), w = rx_fade(r.z);
    float v0 = rx_grad3(rx_hash3(X, Y, Z), r.x, r.y, r.z);
    float v1 = rx_grad3(rx_hash3(X + 1u, Y, Z), r.x - 1.0, r.y, r.z);
    float v2 = rx_grad3(rx_hash3(X, Y + 1u, Z), r.x, r.y - 1.0, r.z);
    float v3 = rx_grad3(rx_hash3(X + 1u, Y + 1u, Z), r.x - 1.0, r.y - 1.0, r.z);
    float v4 = rx_grad3(rx_hash3(X, Y, Z + 1u), r.x, r.y, r.z - 1.0);
    float v5 = rx_grad3(rx_hash3(X + 1u, Y, Z + 1u), r.x - 1.0, r.y, r.z - 1.0);
    float v6 = rx_grad3(rx_hash3(X, Y + 1u, Z + 1u), r.x, r.y - 1.0, r.z - 1.0);
    float v7 = rx_grad3(rx_hash3(X + 1u, Y + 1u, Z + 1u), r.x - 1.0, r.y - 1.0, r.z - 1.0);
    float x1 = 1.0 - u, y1 = 1.0 - v, z1 = 1.0 - w;
    return z1 * (y1 * (v0 * x1 + v1 * u) + v * (v2 * x1 + v3 * u)) +
           w * (y1 * (v4 * x1 + v5 * u) + v * (v6 * x1 + v7 * u));
}

// signed, about -1..1; repeats every 100000 like Cycles (C's fmod keeps the sign: not GLSL's mod)
float rx_snoise3(vec3 p)
{
    vec3 fix = 0.5 * vec3(greaterThanEqual(abs(p), vec3(1000000.0)));
    p = p - 100000.0 * trunc(p / 100000.0) + fix;
    return 0.9820 * rx_perlin3(p);
}

float rx_fbm3(vec3 p, float detail, float roughness)
{
    float fscale = 1.0, amp = 1.0, maxamp = 0.0, sum = 0.0;
    int n = int(detail);
    for (int i = 0; i <= n; i++) {
        sum += rx_snoise3(fscale * p) * amp;
        maxamp += amp;
        amp *= roughness;
        fscale *= 2.0;
    }
    float rmd = detail - floor(detail);
    if (rmd != 0.0) {
        float sum2 = sum + rx_snoise3(fscale * p) * amp;
        return mix(0.5 * sum / maxamp + 0.5, 0.5 * sum2 / (maxamp + amp) + 0.5, rmd);
    }
    return 0.5 * sum / maxamp + 0.5;
}

// Cycles' random_float3_offset(seed): a fixed offset in 100..200 per axis, for distortion and the colour's channels
vec3 rx_offset3(float seed)
{
    uint s = floatBitsToUint(seed);
    const float k = 1.0 / 4294967296.0;
    return vec3(100.0 + float(rx_hash2(s, floatBitsToUint(0.0))) * k * 100.0,
                100.0 + float(rx_hash2(s, floatBitsToUint(1.0))) * k * 100.0,
                100.0 + float(rx_hash2(s, floatBitsToUint(2.0))) * k * 100.0);
}

// position: object-space position x scale (Cycles' "vector x scale")
void mx_rostrum_cycles_noise(vec3 position, float detail, float roughness, float distortion, out float value,
                             out vec3 colour)
{
    detail = clamp(detail, 0.0, 15.0);
    roughness = max(roughness, 0.0);
    vec3 p = position;
    if (distortion != 0.0)
        p += vec3(rx_snoise3(p + rx_offset3(0.0)), rx_snoise3(p + rx_offset3(1.0)), rx_snoise3(p + rx_offset3(2.0))) *
             distortion;
    value = rx_fbm3(p, detail, roughness);
    colour = vec3(value, rx_fbm3(p + rx_offset3(3.0), detail, roughness), rx_fbm3(p + rx_offset3(4.0), detail, roughness));
}
