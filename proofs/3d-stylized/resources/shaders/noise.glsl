// value noise and anisotropic "stroke" noise, all in output pixels
float hash12(vec2 p)
{
    vec3 p3 = fract(vec3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p)
{
    vec2 i = floor(p), f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash12(i), hash12(i + vec2(1, 0)), u.x),
               mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), u.x), u.y);
}

// strokes `len` long and `wid` wide along direction `dir`: values 0..1, ~0.5 average
float strokes(vec2 px, vec2 dir, float len, float wid)
{
    vec2 q = vec2(dot(px, dir), dot(px, vec2(-dir.y, dir.x))) / vec2(len, wid);
    return 0.6 * vnoise(q) + 0.4 * vnoise(q * 2.13 + vec2(17.1, 3.7));
}
