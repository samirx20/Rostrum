#version 450
// Lines from the edge widths (a disc of each edge pixel's width), coloured from the surface,
// over the shaded frame; then paper grain.
uniform float u_ink_opacity = 0.9;
uniform float u_ink_color_x = 0.04, u_ink_color_y = 0.03, u_ink_color_z = 0.05;
uniform float u_ink_albedoMix = 0.5;    // 0 = the ink colour, 1 = a darker shade of the surface
uniform float u_ink_albedoDark = 0.3;
uniform float u_ink_width = 1.6, u_ink_wobble = 0.4;
uniform float u_paper_amount = 0.0;     // paper / canvas grain strength
uniform float u_paper_scale = 1.5;      // grain size, output pixels

uniform sampler2D u_shaded, u_edges, u_albedo;
uniform float u_ss;
out vec4 oColor;

#include <noise.glsl>

void main()
{
    ivec2 p = ivec2(gl_FragCoord.xy);
    ivec2 size = textureSize(u_edges, 0);
    vec4 shaded = texelFetch(u_shaded, p, 0);
    int R = clamp(int(ceil(u_ink_width * u_ss * (1.0 + u_ink_wobble * 1.6) * 0.5 + 1.0)), 1, 12);
    float cov = 0.0;
    ivec2 best = p;
    for (int y = -R; y <= R; ++y)
        for (int x = -R; x <= R; ++x) {
            ivec2 q = clamp(p + ivec2(x, y), ivec2(0), size - 1);
            float w = texelFetch(u_edges, q, 0).r;
            if (w <= 0.0) continue;
            float c = clamp(w * 0.5 - length(vec2(x, y)) + 0.5, 0.0, 1.0);
            if (c > cov) { cov = c; best = q; }
        }
    vec3 ink = mix(vec3(u_ink_color_x, u_ink_color_y, u_ink_color_z),
                   texelFetch(u_albedo, best, 0).rgb * u_ink_albedoDark, u_ink_albedoMix);
    vec3 col = mix(shaded.rgb, ink, cov * u_ink_opacity);
    vec2 px = gl_FragCoord.xy / u_ss;
    float grain = vnoise(px / u_paper_scale) + vnoise(px / (u_paper_scale * 7.0)) - 1.0;
    col *= 1.0 + u_paper_amount * grain;
    oColor = vec4(col, 1.0);
}
