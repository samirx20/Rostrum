// MaterialX 1.39 (Apache-2.0, Contributors to the MaterialX Project), changed for Rostrum3D (libs/PATCHES.md):
// a lamp falls off as 1 / distance^decay, as Storm's own lighting and Cycles do, not 1 / (distance + 1)^decay.
void mx_point_light(LightData light, vec3 position, out lightshader result)
{
    result.direction = light.position - position;
    float distance = length(result.direction) + M_FLOAT_EPS;
    float attenuation = pow(distance, light.decay_rate);
    result.intensity = light.color * light.intensity / attenuation;
    result.direction /= distance;
}
