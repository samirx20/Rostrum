#version 450
// Light per pixel, from the lights' real brightness (lights.h: "shown" units, a white matte surface
// facing a light shows its brightness), then the pixel's material (u_mats row, renderPass.cpp):
//   plain:          albedo x the light + emission (physical: as bright as Storm under the same lights)
//   light to colour: "how lit" -> lit / mid / shadow band x albedo + emission
//   halftone:       dots or lines of the halftone colour where the surface is not lit, on top.
// Alpha = how lit (0..1), for the ink pass's light taper.
// Frame-wide controls (renderer settings rostrum:<group>:<name> -> u_<group>_<name>) with defaults:
uniform float u_brush_amount = 0.0;    // how far strokes push "how lit" (light to colour, legacy ramps)
uniform float u_brush_length = 18.0;   // stroke length, output pixels
uniform float u_brush_width = 3.0;     // stroke width, output pixels
uniform float u_brush_angle = 35.0;    // stroke angle on screen (degrees) where the form gives none
uniform float u_brush_follow = 0.7;    // 0 = all strokes at the angle, 1 = strokes follow the form
uniform float u_shadow_soft = 1.5;     // shadow edge softness (shadow-map texels)
uniform float u_shadow_offset = -1.0;  // push the lookup off the surface (scene units); < 0 = auto: 8 texels of
                                       // that light's map where the scene is (u_shadowAuto), so it fits a case or a room
uniform float u_bg_color_x = 0.0, u_bg_color_y = 0.0, u_bg_color_z = 0.0;  // where nothing is drawn

uniform sampler2D u_albedo, u_normal, u_world, u_ramps, u_mats;
uniform isampler2D u_ids;
uniform sampler2DArrayShadow u_shadowMaps;
uniform int u_lightCount;
uniform vec4 u_lightPos[8], u_lightAxis[8], u_lightColor[8], u_lightExtra[8];
uniform mat4 u_shadowMat[4];
uniform float u_shadowTexel, u_ss;
uniform float u_shadowAuto[4];
uniform mat4 u_camView;
// the sky behind the scene (renderPass.cpp SkyUniforms): a dome picture by view direction, else u_bg_color
uniform sampler2D u_sky;
uniform int u_skyOn;
uniform vec3 u_skyGain;
uniform mat4 u_skyUnproj, u_skyLocal;
uniform vec2 u_frame;
out vec4 oColor;

#include <noise.glsl>

const vec3 kLuma = vec3(0.2126, 0.7152, 0.0722);

float shadowAt(int layer, vec3 P, vec3 N, float cosL)
{
    vec4 c = u_shadowMat[layer] * vec4(P + N * (u_shadow_offset < 0.0 ? u_shadowAuto[layer] : u_shadow_offset), 1.0);
    vec3 q = c.xyz / c.w * 0.5 + 0.5;
    if (any(lessThan(q, vec3(0.0))) || any(greaterThan(q, vec3(1.0)))) return 1.0;
    // a surface the light grazes spreads one map texel over many pixels, and a banded look turns the blurred texel
    // stairs into a ragged edge: widen the blur there (up to 4x), and weight the taps as a tent so the edge is round
    float graze = clamp(1.0 / max(cosL, 0.05), 1.0, 4.0);
    float dt = 0.5 * u_shadow_soft * u_shadowTexel * graze;
    float s = 0.0, wsum = 0.0;
    for (int y = -2; y <= 2; ++y)
        for (int x = -2; x <= 2; ++x) {
            float w = (3.0 - abs(float(x))) * (3.0 - abs(float(y)));
            s += w * texture(u_shadowMaps, vec4(q.xy + vec2(x, y) * dt, float(layer), q.z - 1e-4));
            wsum += w;
        }
    return s / wsum;
}

// the sky this pixel looks at (USD's lat-long: top = the dome's +Y, centre column = its +Z)
vec3 sky()
{
    if (u_skyOn == 0) return vec3(u_bg_color_x, u_bg_color_y, u_bg_color_z);
    vec2 ndc = gl_FragCoord.xy / u_frame * 2.0 - 1.0;
    vec4 a = u_skyUnproj * vec4(ndc, -1.0, 1.0), b = u_skyUnproj * vec4(ndc, 0.0, 1.0);
    vec3 d = normalize((u_skyLocal * vec4(b.xyz / b.w - a.xyz / a.w, 0.0)).xyz);
    vec2 uv = vec2((atan(d.z, d.x) + 1.5707963) / 6.2831853, acos(clamp(d.y, -1.0, 1.0)) / 3.1415927);
    return textureLod(u_sky, uv, 0.0).rgb * u_skyGain;
}

vec4 mrow(int row, int k) { return texelFetch(u_mats, ivec2(k, row), 0); }

// a brush-stroke value in -1..1 at this pixel (0 when strokes are off)
float brushStroke(vec3 N)
{
    if (u_brush_amount <= 0.0) return 0.0;
    vec2 px = gl_FragCoord.xy / u_ss;
    float a = radians(u_brush_angle);
    vec2 fixedDir = vec2(cos(a), sin(a));
    vec3 nv = mat3(u_camView) * N;
    vec2 follow = length(nv.xy) > 1e-3 ? normalize(vec2(-nv.y, nv.x)) : fixedDir;
    if (dot(follow, fixedDir) < 0.0) follow = -follow;
    float f = u_brush_follow * smoothstep(0.1, 0.5, length(nv.xy));
    vec2 dir = normalize(mix(fixedDir, follow, f) + 1e-5);
    return strokes(px, dir, u_brush_length, u_brush_width) * 2.0 - 1.0;
}

// the band colour for "how lit" (contract §2): steps, or linear blends of +- softness at each edge
vec3 band(int row, float how)
{
    vec4 lit = mrow(row, 1), mid = mrow(row, 2), shd = mrow(row, 3);
    float below = lit.w, from = mid.w, s = shd.w;
    if (mrow(row, 4).y < 0.5) return how < below ? shd.rgb : how < from ? mid.rgb : lit.rgb;
    vec3 c = mix(shd.rgb, mid.rgb, clamp((how - (below - s)) / (2.0 * s), 0.0, 1.0));
    return mix(c, lit.rgb, clamp((how - (from - s)) / (2.0 * s), 0.0, 1.0));
}

// halftone ink coverage (0..1) at this pixel for `cover` (1 - how lit), cell grid in output pixels
float halftone(int row, float cover)
{
    vec4 h = mrow(row, 4), hc = mrow(row, 5);
    float size = max(hc.w, 1.0), a = radians(h.w);
    vec2 px = gl_FragCoord.xy / u_ss;
    vec2 q = vec2(cos(a) * px.x + sin(a) * px.y, -sin(a) * px.x + cos(a) * px.y) / size;
    vec2 f = fract(q) - 0.5;
    float S = size * u_ss;                       // one cell in rendered pixels, for a 1-pixel soft edge
    float ink = h.z < 1.5 ? clamp((0.7072 * sqrt(cover) - length(f)) * S + 0.5, 0.0, 1.0)  // dots: area ~ cover
                          : clamp((0.5 * cover - abs(f.y)) * S + 0.5, 0.0, 1.0);           // lines: width ~ cover
    return ink * smoothstep(0.0, 0.02, cover);
}

void main()
{
    ivec2 p = ivec2(gl_FragCoord.xy);
    ivec2 ids = texelFetch(u_ids, p, 0).rg;
    if (ids.r == 0) { oColor = vec4(sky(), 0.0); return; }
    int row = ids.g;
    vec4 albedo = texelFetch(u_albedo, p, 0);
    vec3 emission = mrow(row, 0).rgb;
    if (albedo.a > 0.5) { oColor = vec4(albedo.rgb + emission, 1.0); return; }   // glowing card: as is
    vec3 N = normalize(texelFetch(u_normal, p, 0).xyz);
    vec3 P = texelFetch(u_world, p, 0).xyz;
    float stroke = brushStroke(N);

    vec3 light = vec3(0.0);
    float how = 0.0;
    for (int i = 0; i < u_lightCount; ++i) {
        vec4 lp = u_lightPos[i], ax = u_lightAxis[i], lc = u_lightColor[i], ex = u_lightExtra[i];
        int type = int(lp.w + 0.5);
        bool legacy = ax.w > 0.5;
        float facing;                               // the light's share at this point, before brightness
        if (type == 3) {                            // dome: up / down blend over the hemisphere
            facing = 0.5 + 0.5 * dot(N, ax.xyz);
            if (!legacy) {
                light += mix(ex.xyz, lc.rgb, facing);
                how += dot(lc.rgb, kLuma) * facing;
                continue;
            }
        } else {
            vec3 L = normalize(lp.xyz);
            float fall = 1.0;
            if (type != 0) {
                vec3 d = lp.xyz - P;
                float d2 = dot(d, d);
                L = d * inversesqrt(max(d2, 1e-12));
                fall = 1.0 / max(d2, ex.z);
            }
            float wrap = lc.a;
            facing = clamp((dot(N, L) + wrap) / (1.0 + wrap), 0.0, 1.0);
            if (type == 2) facing *= max(dot(ax.xyz, -L), 0.0);                      // a panel's face
            if (type == 1 && ex.x > -1.5) facing *= smoothstep(ex.x, ex.y, dot(ax.xyz, -L));  // spot cone
            int layer = int(ex.w);
            if (layer >= 0 && facing > 0.0) facing *= shadowAt(layer, P, N, abs(dot(N, L)));
            if (!legacy) {
                vec3 e = lc.rgb * (facing * fall);
                light += e;
                how += dot(e, kLuma);
                continue;
            }
        }
        // legacy (primvars:rostrum:ramp:*): this light's ramp of its "how lit", no fall-off
        float lit = clamp(facing + u_brush_amount * stroke, 0.0, 1.0);
        light += texture(u_ramps, vec2(lit, (float(i) + 0.5) / 8.0)).rgb * lc.rgb;
        how += lit * dot(lc.rgb, kLuma);
    }
    how = clamp(how, 0.0, 1.0);

    vec3 col;
    vec4 flags = mrow(row, 4);
    if (flags.x > 0.5) col = band(row, clamp(how + u_brush_amount * stroke, 0.0, 1.0)) * albedo.rgb + emission;
    else col = albedo.rgb * light + emission;
    if (flags.z > 0.5) col = mix(col, mrow(row, 5).rgb, halftone(row, 1.0 - how));
    oColor = vec4(col, how);
}
