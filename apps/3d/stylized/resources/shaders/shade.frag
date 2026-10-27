#version 450
// "How lit" per light -> broken by brush strokes -> that light's colour ramp -> x albedo.
// Look controls (renderer settings rostrum:<group>:<name> -> u_<group>_<name>) with defaults:
uniform float u_brush_amount = 0.0;    // how far strokes push light across a ramp step (0..1)
uniform float u_brush_length = 18.0;   // stroke length, output pixels
uniform float u_brush_width = 3.0;     // stroke width, output pixels
uniform float u_brush_angle = 35.0;    // stroke angle on screen (degrees) where the form gives none
uniform float u_brush_follow = 0.7;    // 0 = all strokes at the angle, 1 = strokes follow the form
uniform float u_shadow_soft = 1.5;     // shadow edge softness (shadow-map texels)
uniform float u_shadow_offset = 0.15;  // push the lookup off the surface (scene units)
uniform float u_bg_color_x = 0.0, u_bg_color_y = 0.0, u_bg_color_z = 0.0;  // where nothing is drawn

uniform sampler2D u_albedo, u_normal, u_world, u_ramps;
uniform isampler2D u_ids;
uniform sampler2DArrayShadow u_shadowMaps;
uniform int u_lightCount;
uniform vec4 u_lightPos[8], u_lightAxis[8], u_lightColor[8];
uniform float u_lightShadow[8];
uniform mat4 u_shadowMat[4];
uniform float u_shadowTexel, u_ss;
uniform mat4 u_camView;
out vec4 oColor;

#include <noise.glsl>

float shadowAt(int layer, vec3 P, vec3 N)
{
    vec4 c = u_shadowMat[layer] * vec4(P + N * u_shadow_offset, 1.0);
    vec3 q = c.xyz / c.w * 0.5 + 0.5;
    if (any(lessThan(q, vec3(0.0))) || any(greaterThan(q, vec3(1.0)))) return 1.0;
    float s = 0.0;
    for (int y = -2; y <= 2; ++y)
        for (int x = -2; x <= 2; ++x)
            s += texture(u_shadowMaps, vec4(q.xy + vec2(x, y) * 0.5 * u_shadow_soft * u_shadowTexel,
                                            float(layer), q.z - 1e-4));
    return s / 25.0;
}

void main()
{
    ivec2 p = ivec2(gl_FragCoord.xy);
    if (texelFetch(u_ids, p, 0).r == 0) { oColor = vec4(u_bg_color_x, u_bg_color_y, u_bg_color_z, 0.0); return; }
    vec4 albedo = texelFetch(u_albedo, p, 0);
    if (albedo.a > 0.5) { oColor = vec4(albedo.rgb, 1.0); return; }   // unlit card: as painted
    vec3 N = normalize(texelFetch(u_normal, p, 0).xyz);
    vec3 P = texelFetch(u_world, p, 0).xyz;

    // stroke direction: along the form's contour on screen, blended with a fixed angle
    vec2 px = gl_FragCoord.xy / u_ss;
    float a = radians(u_brush_angle);
    vec2 fixedDir = vec2(cos(a), sin(a));
    vec3 nv = mat3(u_camView) * N;
    vec2 follow = length(nv.xy) > 1e-3 ? normalize(vec2(-nv.y, nv.x)) : fixedDir;
    if (dot(follow, fixedDir) < 0.0) follow = -follow;
    float f = u_brush_follow * smoothstep(0.1, 0.5, length(nv.xy));
    vec2 dir = normalize(mix(fixedDir, follow, f) + 1e-5);
    float stroke = strokes(px, dir, u_brush_length, u_brush_width) * 2.0 - 1.0;

    vec3 light = vec3(0.0);
    float litAll = 0.0, weight = 0.0;
    for (int i = 0; i < u_lightCount; ++i) {
        vec4 lp = u_lightPos[i];
        int type = int(lp.w + 0.5);
        float lit;
        if (type == 3) lit = 0.5 + 0.5 * dot(N, u_lightAxis[i].xyz);   // dome: hemisphere
        else {
            vec3 L = type == 0 ? normalize(lp.xyz) : normalize(lp.xyz - P);
            float wrap = u_lightColor[i].a;
            lit = clamp((dot(N, L) + wrap) / (1.0 + wrap), 0.0, 1.0);
            if (type == 2) lit *= clamp(dot(u_lightAxis[i].xyz, -L) * 3.0, 0.0, 1.0);  // one-sided
            int layer = int(u_lightShadow[i]);
            if (layer >= 0) lit *= shadowAt(layer, P, N);
        }
        lit = clamp(lit + u_brush_amount * stroke, 0.0, 1.0);
        light += texture(u_ramps, vec2(lit, (float(i) + 0.5) / 8.0)).rgb * u_lightColor[i].rgb;
        float w = dot(u_lightColor[i].rgb, vec3(0.2126, 0.7152, 0.0722));
        litAll += lit * w;
        weight += w;
    }
    oColor = vec4(albedo.rgb * light, weight > 0.0 ? litAll / weight : 1.0);
}
