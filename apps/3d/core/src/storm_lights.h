// Storm's lights read like Cycles' (brief 10b), by a Hydra filter in front of Storm ("GL") alone; Cycles never sees it.
//  - A sphere light with normalize: UsdLux divides its brightness by its surface area, 4πr² (Cycles does); Storm by
//    πr², 4x too bright. Storm gets normalize off and the intensity ÷ 4πr² (its world size), which it draws as UsdLux.
//  - A spot (a sphere light with UsdLux shaping). Storm cuts only rect and disk lights to their cone (hdSt/light.cpp,
//    _ApproximateAreaLight), so a spot lit all around. Storm gets it as a disk light of the same radius: the same
//    brightness there (both are points of area πr²), cut at the cone, with pow(cos, focus) inside it (glf
//    simpleLighting.glslfx); Storm has no softness. Cycles fades the edge in over the outer `softness` part of the cone
//    (kernel/light/spot.h, a smoothstep): Storm gets a focus at half strength where that fade is, so the pool's size and
//    edge read alike.
#pragma once

namespace r3d {

// register the filter for Storm; call once, before any Storm engine is made
void register_storm_lights();

}  // namespace r3d
