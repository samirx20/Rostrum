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

// One layer of brush dabs: rows of strokes `len` long and `wid` wide along `dir`, each with one
// flat value (0..1), staggered ends, soft ends and sides, and faint bristle streaks.
float dabs(vec2 px, vec2 dir, float len, float wid, float seed)
{
    vec2 q = vec2(dot(px, dir), dot(px, vec2(-dir.y, dir.x))) / vec2(len, wid);
    float row = floor(q.y);
    q.x += hash12(vec2(row, seed)) * 7.0;                         // stagger each row
    vec2 cell = vec2(floor(q.x), row);
    vec2 f = fract(q);
    float v = hash12(cell + seed * 13.1);
    v += 0.25 * (vnoise(vec2(q.x * 0.7, q.y * 9.0) + seed) - 0.5); // bristles along the stroke
    float soft = smoothstep(0.0, 0.2, f.x) * smoothstep(1.0, 0.8, f.x) * smoothstep(0.0, 0.25, f.y) * smoothstep(1.0, 0.75, f.y);
    return mix(0.5, v, soft);
}

// two overlapping dab layers at slightly different angles: values 0..1, ~0.5 average
float strokes(vec2 px, vec2 dir, float len, float wid)
{
    vec2 d2 = normalize(dir + 0.35 * vec2(-dir.y, dir.x));
    return 0.6 * dabs(px, dir, len, wid, 1.0) + 0.4 * dabs(px + 11.0, d2, len * 0.8, wid * 1.2, 2.0);
}
