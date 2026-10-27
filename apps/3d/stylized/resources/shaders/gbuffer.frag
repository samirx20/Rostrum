#version 450
in vec3 vWorld;
in vec3 vNormal;
in vec2 vUV;
uniform sampler2D u_tex;
uniform int u_hasTex, u_unlit, u_id, u_mat;
uniform vec3 u_baseColor;
uniform mat4 u_camView;
layout(location = 0) out vec4 oAlbedo;   // linear albedo, a = unlit (a glowing card)
layout(location = 1) out vec4 oNormal;   // world normal (towards the camera), a = view depth
layout(location = 2) out vec4 oWorld;
layout(location = 3) out ivec2 oId;      // r = object id (0 = nothing), g = material row

void main()
{
    vec3 albedo = u_hasTex != 0 ? texture(u_tex, vec2(vUV.x, 1.0 - vUV.y)).rgb : u_baseColor;
    vec3 n = normalize(vNormal);
    if (!gl_FrontFacing) n = -n;                 // double-sided
    float depth = -(u_camView * vec4(vWorld, 1.0)).z;
    oAlbedo = vec4(albedo, float(u_unlit));
    oNormal = vec4(n, depth);
    oWorld = vec4(vWorld, 1.0);
    oId = ivec2(u_id, u_mat);
}
