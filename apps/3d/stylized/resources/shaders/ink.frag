#version 450
// Lines from the edge widths (a disc of each edge pixel's width), in the colour of the line's
// material (row 7 of u_mats; the frame-wide ink colour for lines the frame asked for), over the
// shaded frame; then paper grain.
uniform float u_ink_opacity = 1.0;
uniform float u_ink_color_x = 0.0103, u_ink_color_y = 0.0103, u_ink_color_z = 0.0103;
uniform float u_ink_albedoMix = 0.0;    // 0 = the line colour, 1 = a darker shade of the surface
uniform float u_ink_albedoDark = 0.3;
uniform float u_paper_amount = 0.0;     // paper / canvas grain strength
uniform float u_paper_scale = 1.5;      // grain size, output pixels

uniform sampler2D u_shaded, u_edges, u_albedo, u_mats;
uniform isampler2D u_ids;
uniform int u_inkRadius;                // search radius in rendered pixels (0 = no lines this frame)
uniform float u_ss;
out vec4 oColor;

#include <noise.glsl>

void main()
{
    ivec2 p = ivec2(gl_FragCoord.xy);
    ivec2 size = textureSize(u_edges, 0);
    vec4 shaded = texelFetch(u_shaded, p, 0);
    vec3 col = shaded.rgb;
    int R = u_inkRadius;
    if (R > 0) {
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
        if (cov > 0.0) {
            int row = texelFetch(u_ids, best, 0).g;
            vec4 lineRow = texelFetch(u_mats, ivec2(6, row), 0);
            vec3 ink = lineRow.x > 0.5 ? texelFetch(u_mats, ivec2(7, row), 0).rgb
                                     : vec3(u_ink_color_x, u_ink_color_y, u_ink_color_z);
            ink = mix(ink, texelFetch(u_albedo, best, 0).rgb * u_ink_albedoDark, u_ink_albedoMix);
            col = mix(col, ink, cov * u_ink_opacity);
        }
    }
    if (u_paper_amount != 0.0) {
        vec2 px = gl_FragCoord.xy / u_ss;
        float grain = vnoise(px / u_paper_scale) + vnoise(px / (u_paper_scale * 7.0)) - 1.0;
        col *= 1.0 + u_paper_amount * grain;
    }
    oColor = vec4(col, 1.0);
}
