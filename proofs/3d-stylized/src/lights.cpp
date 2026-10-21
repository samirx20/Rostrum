// P-3D-3: see lights.h. A ramp is a step function (each colour holds from its position to the
// next) box-blurred by `smooth` (0 = hard painted steps, 1 = a blur as wide as the whole ramp).
#include "lights.h"

#include <pxr/base/gf/frustum.h>
#include <pxr/imaging/hd/tokens.h>

#include <algorithm>
#include <cmath>

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

GfMatrix4d ShadowCamera(RostrumLightData const &l, GfVec3d const &c, double r)
{
    GfMatrix4d view;
    GfFrustum f;
    if (l.type == HdPrimTypeTokens->distantLight) {
        GfVec3d L = l.xform.TransformDir(GfVec3d(0, 0, 1)).GetNormalized();
        GfVec3d up = std::abs(L[1]) > 0.99 ? GfVec3d(1, 0, 0) : GfVec3d(0, 1, 0);
        view.SetLookAt(c + L * (2 * r), c, up);
        f.SetOrthographic(-r, r, -r, r, 0.5 * r, 3.5 * r);
    } else {
        GfVec3d eye = l.xform.ExtractTranslation();
        double d = (c - eye).GetLength();
        GfVec3d dir = (c - eye) / std::max(d, 1e-6);
        GfVec3d up = std::abs(dir[1]) > 0.99 ? GfVec3d(1, 0, 0) : GfVec3d(0, 1, 0);
        view.SetLookAt(eye, c, up);
        double fov = d > r ? std::min(160.0, 2.1 * std::asin(r / d) * 180.0 / M_PI) : 160.0;
        f.SetPerspective(fov, 1.0, std::max(d - r, d * 0.02), d + r);
    }
    return view * f.ComputeProjectionMatrix();
}

}  // namespace

RostrumFrameLights RostrumPackLights(std::map<SdfPath, RostrumLightData> const &lights,
                                     GfVec3d const &centre, double radius)
{
    RostrumFrameLights out;
    out.ramps.assign(size_t(kMaxLights) * kRampSize * 4, 0.0f);
    for (auto const &[path, l] : lights) {
        if (!l.enabled) continue;
        if (out.count == kMaxLights) {
            TF_WARN("Rostrum Stylized: more than %d lights; %s and later are ignored", kMaxLights,
                    path.GetText());
            break;
        }
        int i = out.count++;
        GfVec3d emit = l.xform.TransformDir(GfVec3d(0, 0, -1)).GetNormalized();
        GfVec3d at = l.xform.ExtractTranslation();
        if (l.type == HdPrimTypeTokens->distantLight)
            out.pos[i] = GfVec4f(float(-emit[0]), float(-emit[1]), float(-emit[2]), 0.0f);
        else if (l.type == HdPrimTypeTokens->domeLight)
            out.pos[i] = GfVec4f(0, 0, 0, 3.0f);
        else
            out.pos[i] = GfVec4f(GfVec3f(at)[0], GfVec3f(at)[1], GfVec3f(at)[2],
                                 l.type == HdPrimTypeTokens->sphereLight ? 1.0f : 2.0f);
        GfVec3f ax = l.type == HdPrimTypeTokens->domeLight ? l.hemiUp.GetNormalized() : GfVec3f(emit);
        out.axis[i] = GfVec4f(ax[0], ax[1], ax[2], 0.0f);
        GfVec3f c = l.color * l.gain;
        out.color[i] = GfVec4f(c[0], c[1], c[2], l.wrap);
        out.shadowLayer[i] = -1.0f;
        if (l.shadow && l.type != HdPrimTypeTokens->domeLight && out.shadows < kMaxShadows) {
            out.shadowMat[out.shadows] = GfMatrix4f(ShadowCamera(l, centre, radius));
            out.shadowLayer[i] = float(out.shadows++);
        }
        FillRamp(l.ramp, &out.ramps[size_t(i) * kRampSize * 4]);
    }
    return out;
}

PXR_NAMESPACE_CLOSE_SCOPE
