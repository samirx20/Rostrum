#version 450
// Geometry for the G-buffer and the shadow maps, with the per-camera shape bend.
// The bend is defined on the render camera's screen: it applies (and casts shadows) only when
// the mesh's rostrum:bend:camera is the camera rendering.
layout(location = 0) in vec3 aP;
layout(location = 1) in vec3 aN;
layout(location = 2) in vec2 aUV;
uniform mat4 u_model, u_camView, u_camViewInv, u_viewProj;
uniform int u_bendOn;
uniform vec3 u_bendPivot;
uniform float u_bendRadius, u_bendSquash, u_bendSwell;
uniform vec2 u_bendLean;
out vec3 vWorld;
out vec3 vNormal;
out vec2 vUV;

vec3 bend(vec3 wp)
{
    vec3 v = (u_camView * vec4(wp, 1.0)).xyz;
    vec3 c = (u_camView * vec4(u_bendPivot, 1.0)).xyz;
    vec3 d = v - c;
    float h = d.y;                                   // height above the pivot on screen
    d.y *= u_bendSquash;                             // squash / stretch ...
    d.xz /= sqrt(max(u_bendSquash, 1e-3));           // ... keeping the volume
    d.x += u_bendLean.x * h;                         // lean sideways on screen
    d.z += u_bendLean.y * h;                         // lean toward (+) / away from the camera
    d.xy *= 1.0 + u_bendSwell;                       // grow in the picture plane
    return (u_camViewInv * vec4(c + d, 1.0)).xyz;
}

void main()
{
    vec3 wp = (u_model * vec4(aP, 1.0)).xyz;
    if (u_bendOn != 0) wp = bend(wp);
    vWorld = wp;
    vNormal = normalize(transpose(inverse(mat3(u_model))) * aN);
    vUV = aUV;
    gl_Position = u_viewProj * vec4(wp, 1.0);
}
