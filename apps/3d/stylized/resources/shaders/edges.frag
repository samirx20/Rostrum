#version 450
// Ink line width per pixel (rendered pixels) where the near pixel's material has Lines on:
// silhouettes, folds and creases sharper than its crease angle, thinned in light (its taper), varied
// along the line (its wobble) so lines taper and end. Material row (u_mats): 6 = lines, width,
// taper, wobble; 7 = colour, crease angle.
// Frame-wide controls (renderer settings rostrum:ink:<name> -> u_ink_<name>):
uniform float u_ink_width = 0.0;        // > 0: lines on every material that has none of its own, this wide
uniform float u_ink_creaseAngle = 35.0; //   ... with this crease angle,
uniform float u_ink_lightTaper = 0.6;   //   ... this light taper,
uniform float u_ink_wobble = 0.4;       //   ... and this wobble
uniform float u_ink_crease = 1.0;       // crease line width relative to outlines (every material)
uniform float u_ink_creaseSoft = 15.0;  // degrees over which a crease line fades in
uniform float u_ink_depthJump = 0.05;   // relative depth step that counts as a fold
uniform float u_ink_depthTaper = 0.0;   // lines thin out with distance
uniform float u_ink_wobbleScale = 40.0; // the wobble's scale, output pixels

uniform sampler2D u_normal, u_shaded, u_albedo, u_mats;
uniform isampler2D u_ids;
uniform float u_ss, u_depthNear, u_depthFar;
out float oWidth;

#include <noise.glsl>

void main()
{
    ivec2 p = ivec2(gl_FragCoord.xy);
    ivec2 ids = texelFetch(u_ids, p, 0).rg;
    int id0 = ids.r;
    if (id0 == 0 || texelFetch(u_albedo, p, 0).a > 0.5) { oWidth = 0.0; return; }
    vec4 L0 = texelFetch(u_mats, ivec2(6, ids.g), 0);
    float width = L0.y, taper = L0.z, wobble = L0.w, angle = texelFetch(u_mats, ivec2(7, ids.g), 0).w;
    if (L0.x < 0.5) {
        if (u_ink_width <= 0.0) { oWidth = 0.0; return; }
        width = u_ink_width; taper = u_ink_lightTaper; wobble = u_ink_wobble; angle = u_ink_creaseAngle;
    }
    vec4 n0 = texelFetch(u_normal, p, 0);
    ivec2 size = textureSize(u_ids, 0);
    float sil = 0.0, crease = 0.0;
    int s = max(1, int(u_ss));
    bool creases = angle < 179.5;               // 180 = outline only
    float soft = min(u_ink_creaseSoft, angle * 0.5);
    ivec2 offs[4] = ivec2[](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1));
    for (int k = 0; k < 4; ++k) {
        ivec2 q = clamp(p + offs[k], ivec2(0), size - 1);
        int idq = texelFetch(u_ids, q, 0).r;
        vec4 nq = texelFetch(u_normal, q, 0);
        bool behind = idq == 0 || nq.w > n0.w;   // only the nearer side carries the line
        if (idq != id0 && behind) sil = 1.0;
        else if (idq == id0 && behind && (nq.w - n0.w) / n0.w > u_ink_depthJump) sil = 1.0;
        if (!creases) continue;
        ivec2 qc = clamp(p + offs[k] * s, ivec2(0), size - 1);   // one output pixel away
        if (texelFetch(u_ids, qc, 0).r == id0) {
            float ang = degrees(acos(clamp(dot(n0.xyz, texelFetch(u_normal, qc, 0).xyz), -1.0, 1.0)));
            crease = max(crease, smoothstep(angle - soft, angle, ang));
        }
    }
    float w = max(sil, crease * u_ink_crease) * width;
    if (w <= 0.0) { oWidth = 0.0; return; }
    float lit = texelFetch(u_shaded, p, 0).a;
    w *= 1.0 - taper * smoothstep(0.25, 1.0, lit);
    w *= 1.0 - u_ink_depthTaper * clamp((n0.w - u_depthNear) / max(u_depthFar - u_depthNear, 1e-3), 0.0, 1.0);
    vec2 px = gl_FragCoord.xy / u_ss;
    w *= max(0.0, 1.0 + wobble * (2.0 * vnoise(px / u_ink_wobbleScale) - 1.0) * 1.6);
    oWidth = w * u_ss;
}
