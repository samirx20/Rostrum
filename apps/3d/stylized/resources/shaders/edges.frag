#version 450
// Ink line width per pixel (supersampled pixels): silhouettes, folds and creases, thinned in
// light and with distance, broken by a slow wobble so lines taper and end.
uniform float u_ink_width = 1.6;        // line width, output pixels (0 = no ink)
uniform float u_ink_crease = 0.6;       // crease line width relative to silhouettes
uniform float u_ink_creaseAngle = 35.0; // degrees between normals where a crease is full width
uniform float u_ink_creaseSoft = 15.0;  // degrees over which a crease line fades in
uniform float u_ink_depthJump = 0.05;   // relative depth step that counts as a fold
uniform float u_ink_lightTaper = 0.6;   // lines thin out in light (lost and found edges)
uniform float u_ink_depthTaper = 0.4;   // lines thin out with distance
uniform float u_ink_wobble = 0.4;       // width variation along lines
uniform float u_ink_wobbleScale = 40.0; // its scale, output pixels

uniform sampler2D u_normal, u_shaded, u_albedo;
uniform isampler2D u_ids;
uniform float u_ss, u_depthNear, u_depthFar;
out float oWidth;

#include <noise.glsl>

void main()
{
    ivec2 p = ivec2(gl_FragCoord.xy);
    int id0 = texelFetch(u_ids, p, 0).r;
    if (id0 == 0 || texelFetch(u_albedo, p, 0).a > 0.5 || u_ink_width <= 0.0) { oWidth = 0.0; return; }
    vec4 n0 = texelFetch(u_normal, p, 0);
    ivec2 size = textureSize(u_ids, 0);
    float sil = 0.0, crease = 0.0;
    int s = max(1, int(u_ss));
    ivec2 offs[4] = ivec2[](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1));
    for (int k = 0; k < 4; ++k) {
        ivec2 q = clamp(p + offs[k], ivec2(0), size - 1);
        int idq = texelFetch(u_ids, q, 0).r;
        vec4 nq = texelFetch(u_normal, q, 0);
        bool behind = idq == 0 || nq.w > n0.w;   // only the nearer side carries the line
        if (idq != id0 && behind) sil = 1.0;
        else if (idq == id0 && behind && (nq.w - n0.w) / n0.w > u_ink_depthJump) sil = 1.0;
        ivec2 qc = clamp(p + offs[k] * s, ivec2(0), size - 1);
        if (texelFetch(u_ids, qc, 0).r == id0) {
            float ang = degrees(acos(clamp(dot(n0.xyz, texelFetch(u_normal, qc, 0).xyz), -1.0, 1.0)));
            crease = max(crease, smoothstep(u_ink_creaseAngle - u_ink_creaseSoft, u_ink_creaseAngle, ang));
        }
    }
    float w = max(sil, crease * u_ink_crease) * u_ink_width;
    float lit = texelFetch(u_shaded, p, 0).a;
    w *= 1.0 - u_ink_lightTaper * smoothstep(0.25, 1.0, lit);
    w *= 1.0 - u_ink_depthTaper * clamp((n0.w - u_depthNear) / max(u_depthFar - u_depthNear, 1e-3), 0.0, 1.0);
    vec2 px = gl_FragCoord.xy / u_ss;
    w *= max(0.0, 1.0 + u_ink_wobble * (2.0 * vnoise(px / u_ink_wobbleScale) - 1.0) * 1.6);
    oWidth = w * u_ss;
}
