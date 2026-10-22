// Lights in UsdLux's units for Cycles. Cycles' Hydra plug-in (hydra/light.cpp) reads two kinds of light wrongly
// (measured H19 on one grey plane, one light at a time, against the hand-computed value; Storm matched all of them):
//  - a dome: colour × intensity × 2^exposure × π goes into the dome's shader AND is set as the light's strength.
//    Cycles multiplies both when it samples the dome as a light (kernel/light/sample.h) but only the shader when a
//    ray sees the dome, so the light a sunny HDR gave was strength² (π² at intensity 1) while the sky looked π: the
//    floor came out ~3× too bright under a sun, about right under a flat dome (which Cycles doesn't sample as a light).
//  - a distant light: × 4 ("unclear why, but approximately matches Karma").
//  - a rect or disk panel with normalize on: exactly 10 000× too bright (measured H23; normalize off is right), so it
//    is handed over as normalize off with intensity ÷ its area, which is what UsdLux's normalize means.
// A Hydra filter in front of Cycles alone hands it numbers that give UsdLux's light: a dome as its picture already
// multiplied (sky.h dome_picture, the same picture Storm gets) with a strength of exactly 1 (intensity 1/π, colour 1,
// exposure 0, no colour temperature), so strength² = strength; a distant light's intensity ÷ 4. The stage keeps the
// UsdLux values, so a saved .usda means the same in any renderer that follows UsdLux.
// The same filter hands over product lighting (light_extras.h: a panel's card and spread, light links, a dome's camera
// visibility) in the tokens our patch on the plug-in reads, and hides the card mesh Storm uses.
#pragma once

namespace r3d {

// register the filter for Hydra's "Cycles" renderer; call once, before any Cycles engine is made
void register_cycles_lights();
// After a scene load: tells every Cycles engine which lights' (and linked items') product lighting may have changed.
// Our own attributes (rostrum:seenByCamera, rostrum:lightsOnly …) don't dirty a light in USD's eyes, so without this a
// dome switched to unseen in a running engine stayed seen (H22).
void announce_light_extras();

}  // namespace r3d
