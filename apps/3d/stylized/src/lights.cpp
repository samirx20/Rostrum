// See lights.h. A legacy ramp is a step function (each colour holds from its position to the
// next) box-blurred by `smooth` (0 = hard painted steps, 1 = a blur as wide as the whole ramp).
#include "lights.h"

#include <pxr/base/gf/frustum.h>
#include <pxr/imaging/hd/tokens.h>

#include <algorithm>
#include <cmath>
#include <cstdio>

PXR_NAMESPACE_OPEN_SCOPE

namespace {

GfVec3f Step(RostrumRamp const &r, float x)
{
    if (r.positions.empty()) return GfVec3f(x);  // no ramp: plain lambert
    size_t i = 0;
    while (i + 1 < r.positions.size() && x >= r.positions[i + 1]) ++i;
    return r.colors[i];
}

void FillRamp(RostrumRamp const &r, float *row)
{
    int const taps = 64;
    for (int t = 0; t < kRampSize; ++t) {
        float x = (t + 0.5f) / kRampSize;
        GfVec3f c(0);
        if (r.smooth <= 0.0f || r.positions.empty()) c = Step(r, x);
        else {
            for (int k = 0; k < taps; ++k)
                c += Step(r, std::clamp(x + r.smooth * ((k + 0.5f) / taps - 0.5f), 0.0f, 1.0f));
            c /= float(taps);
        }
        row[t * 4 + 0] = c[0]; row[t * 4 + 1] = c[1]; row[t * 4 + 2] = c[2]; row[t * 4 + 3] = 1.0f;
    }
}

// A shadow camera that just holds the bounds' eight corners (a 2048 map then spends its texels on the scene, not on
// empty space around a bounding sphere: a light near the scene got a 160 degree map and a stepped band edge).
// `span`: the map's width at the bounds' centre, world units.
GfMatrix4d ShadowCamera(RostrumLightData const &l, GfRange3d const &box, float *span)
{
    GfVec3d c = box.GetMidpoint();
    double r = std::max(box.GetSize().GetLength() * 0.5, 1e-4);
    bool distant = l.type == HdPrimTypeTokens->distantLight;
    GfVec3d eye, dir;
    if (distant) {
        dir = -l.xform.TransformDir(GfVec3d(0, 0, 1)).GetNormalized();
        eye = c - dir * (2 * r);
    } else {
        eye = l.xform.ExtractTranslation();
        dir = (c - eye) / std::max((c - eye).GetLength(), 1e-6);
    }
    GfMatrix4d view;
    view.SetLookAt(eye, eye + dir, std::abs(dir[1]) > 0.99 ? GfVec3d(1, 0, 0) : GfVec3d(0, 1, 0));
    // the corners in the light's view (looking down -z): their extent across, and their depth range
    double x0 = 1e30, x1 = -1e30, y0 = 1e30, y1 = -1e30, n = 1e30, f = 0;
    bool behind = false;
    for (int k = 0; k < 8; ++k) {
        GfVec3d p = view.Transform(box.GetCorner(k));
        double depth = -p[2];
        if (!distant && depth < 1e-6) { behind = true; break; }
        double x = distant ? p[0] : p[0] / depth, y = distant ? p[1] : p[1] / depth;
        x0 = std::min(x0, x); x1 = std::max(x1, x); y0 = std::min(y0, y); y1 = std::max(y1, y);
        n = std::min(n, depth); f = std::max(f, depth);
    }
    double const wide = std::tan(80.0 * M_PI / 180.0);   // a local light's widest map: 160 degrees
    double d = (c - eye).GetLength();
    GfFrustum fr;
    if (distant) {
        double m = 0.01 * r;                             // a hair round the edge
        fr.SetOrthographic(x0 - m, x1 + m, y0 - m, y1 + m, std::max(n - m, 1e-4), f + m);
        *span = float(std::max(x1 - x0, y1 - y0) + 2 * m);
    } else if (behind || std::max({-x0, x1, -y0, y1}) > wide) {  // the light is among the bounds: the widest map
        fr.SetPerspective(160.0, 1.0, std::max(d - r, d * 0.02), d + r);
        *span = float(2 * wide * d);
    } else {
        double m = 0.01 * std::max(x1 - x0, y1 - y0);
        fr.SetProjectionType(GfFrustum::Perspective);
        fr.SetWindow(GfRange2d(GfVec2d(x0 - m, y0 - m), GfVec2d(x1 + m, y1 + m)));  // on the plane 1 unit away
        fr.SetNearFar(GfRange1d(std::max(n * 0.98, d * 0.02), f * 1.02));
        *span = float((std::max(x1 - x0, y1 - y0) + 2 * m) * d);
    }
    return view * fr.ComputeProjectionMatrix();
}

float Luma(GfVec3f const &c) { return 0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2]; }

// UsdLux brightness in shown units (lights.h): for a distant light the light on a surface facing it;
// for a local light that x d^2 (the light at distance d is this / d^2), with the light's area (its
// size seen face on) and radiance (intensity, / its area with normalize). `minD2` caps the light
// at its own surface's brightness, so a surface touching a panel doesn't blow up.
float Brightness(RostrumLightData const &l, float *minD2)
{
    *minD2 = 1e-6f;
    if (l.type == HdPrimTypeTokens->distantLight) return l.intensity / float(M_PI);  // lux / pi
    if (l.type == HdPrimTypeTokens->domeLight) return l.intensity;
    float shown, area;   // area seen face on
    if (l.type == HdPrimTypeTokens->rectLight) {
        area = l.width * l.height;
        float radiance = l.normalize ? l.intensity / std::max(area, 1e-8f) : l.intensity;
        shown = radiance * area / float(M_PI);
    } else {  // sphere (and a spot), disk: a disc of the radius face on
        area = float(M_PI) * l.radius * l.radius;
        float surface = l.type == HdPrimTypeTokens->sphereLight ? 4.0f * area : area;  // 4 pi r^2 / pi r^2
        float radiance = l.normalize ? l.intensity / std::max(surface, 1e-8f) : l.intensity;
        shown = radiance * area / float(M_PI);
    }
    *minD2 = std::max(area / float(M_PI), 1e-6f);
    return shown;
}

}  // namespace

RostrumFrameLights RostrumPackLights(std::map<SdfPath, RostrumLightData> const &lights, GfRange3d const &lit)
{
    GfVec3d const centre = lit.GetMidpoint();
    // strongest first, judged at the centre of what is lit
    struct Pick { SdfPath const *path; RostrumLightData const *l; float k, minD2, strength; };
    std::vector<Pick> all, picks;
    bool haveDome = false;
    for (auto const &[path, l] : lights) {
        if (!l.enabled) continue;
        Pick p{&path, &l, 0, 0, 0};
        p.k = Brightness(l, &p.minD2);
        bool legacy = !l.ramp.positions.empty();
        float y = legacy ? Luma(l.color) * l.gain : Luma(l.color) * p.k;
        if (l.type == HdPrimTypeTokens->domeLight && !legacy) y = Luma(GfCompMult(l.color, l.domeUp)) * p.k;
        bool local = l.type != HdPrimTypeTokens->distantLight && l.type != HdPrimTypeTokens->domeLight;
        if (local && !legacy) {
            float d2 = float((l.xform.ExtractTranslation() - centre).GetLengthSq());
            y /= std::max(d2, p.minD2);
        }
        p.strength = y;
        all.push_back(p);
    }
    std::stable_sort(all.begin(), all.end(), [](Pick const &a, Pick const &b) { return a.strength > b.strength; });
    for (Pick const &p : all) {
        // one sky: the viewport hands its dome over beside the stage's own, the same light twice
        if (p.l->type == HdPrimTypeTokens->domeLight) {
            if (haveDome) continue;
            haveDome = true;
        }
        if (int(picks.size()) == kMaxLights) {
            TF_WARN("Rostrum Stylized: more than %d lights; %s and the weaker ones are left out", kMaxLights,
                    p.path->GetText());
            break;
        }
        picks.push_back(p);
    }

    RostrumFrameLights out;
    out.ramps.assign(size_t(kMaxLights) * kRampSize * 4, 0.0f);
    for (Pick const &p : picks) {
        RostrumLightData const &l = *p.l;
        int i = out.count++;
        bool legacy = !l.ramp.positions.empty();
        GfVec3d emit = l.xform.TransformDir(GfVec3d(0, 0, -1)).GetNormalized();
        GfVec3f at(l.xform.ExtractTranslation());
        bool dome = l.type == HdPrimTypeTokens->domeLight;
        if (l.type == HdPrimTypeTokens->distantLight)
            out.pos[i] = GfVec4f(float(-emit[0]), float(-emit[1]), float(-emit[2]), 0.0f);
        else if (dome)
            out.pos[i] = GfVec4f(0, 0, 0, 3.0f);
        else
            out.pos[i] = GfVec4f(at[0], at[1], at[2], l.type == HdPrimTypeTokens->sphereLight ? 1.0f : 2.0f);
        GfVec3f ax = dome ? l.hemiUp.GetNormalized() : GfVec3f(emit);
        out.axis[i] = GfVec4f(ax[0], ax[1], ax[2], legacy ? 1.0f : 0.0f);
        GfVec3f c = legacy ? l.color * l.gain : dome ? GfCompMult(l.color, l.domeUp) * p.k : l.color * p.k;
        out.color[i] = GfVec4f(c[0], c[1], c[2], l.wrap);
        if (dome) {
            GfVec3f down = legacy ? GfVec3f(0) : GfCompMult(l.color, l.domeDown) * p.k;
            out.extra[i] = GfVec4f(down[0], down[1], down[2], -1.0f);
        } else {
            float outer = -2.0f, inner = -2.0f;
            if (l.type == HdPrimTypeTokens->sphereLight && l.coneAngle < 179.9f) {
                // Cycles' spot: full inside angle x (1 - softness), fading out to the angle
                float a = float(std::clamp(double(l.coneAngle), 0.1, 179.9) * M_PI / 180.0);
                outer = std::cos(a);
                inner = std::cos(a * (1.0f - std::clamp(l.coneSoftness, 0.0f, 1.0f)));
                if (inner - outer < 1e-4f) inner = outer + 1e-4f;
            }
            out.extra[i] = GfVec4f(outer, inner, p.minD2, -1.0f);
            if (l.shadow && out.shadows < kMaxShadows) {
                out.shadowMat[out.shadows] = GfMatrix4f(ShadowCamera(l, lit, &out.shadowSpan[out.shadows]));
                out.extra[i][3] = float(out.shadows++);
            }
        }
        if (legacy) {
            FillRamp(l.ramp, &out.ramps[size_t(i) * kRampSize * 4]);
            out.legacy = true;
        }
    }
    return out;
}

PXR_NAMESPACE_CLOSE_SCOPE
