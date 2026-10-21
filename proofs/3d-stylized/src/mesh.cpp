// P-3D-3: mesh -> triangle soup (positions, normals, UVs per corner) + per-camera bend primvars.
#include "prims.h"

#include <pxr/base/gf/range3d.h>
#include <atomic>
#include <pxr/imaging/hd/meshTopology.h>
#include <pxr/imaging/hd/sceneDelegate.h>
#include <pxr/imaging/hd/tokens.h>

PXR_NAMESPACE_OPEN_SCOPE

namespace {

struct Primvar {
    VtValue value;
    HdInterpolation interp = HdInterpolationConstant;
};

// one primvar by name, any interpolation; empty value when the mesh has none
Primvar FindPrimvar(HdSceneDelegate *sd, SdfPath const &id, TfToken const &name, bool texcoord = false)
{
    for (int i = 0; i < HdInterpolationCount; ++i) {
        auto interp = HdInterpolation(i);
        for (HdPrimvarDescriptor const &d : sd->GetPrimvarDescriptors(id, interp)) {
            bool hit = d.name == name || (texcoord && d.role == HdPrimvarRoleTokens->textureCoordinate);
            if (hit) return {sd->Get(id, d.name), interp};
        }
    }
    return {};
}

template <class T> bool Fetch(Primvar const &pv, int face, int vertex, int corner, T *out)
{
    if (!pv.value.IsHolding<VtArray<T>>()) return false;
    VtArray<T> const &a = pv.value.UncheckedGet<VtArray<T>>();
    size_t i = pv.interp == HdInterpolationConstant ? 0
             : pv.interp == HdInterpolationUniform  ? size_t(face)
             : pv.interp == HdInterpolationFaceVarying ? size_t(corner)
                                                     : size_t(vertex);
    if (i >= a.size()) return false;
    *out = a[i];
    return true;
}

template <class T> T Constant(HdSceneDelegate *sd, SdfPath const &id, char const *name, T fallback)
{
    VtValue v = FindPrimvar(sd, id, TfToken(name)).value;
    if (v.IsHolding<T>()) return v.UncheckedGet<T>();
    if (v.IsHolding<VtArray<T>>() && !v.UncheckedGet<VtArray<T>>().empty())
        return v.UncheckedGet<VtArray<T>>()[0];
    return fallback;
}

}  // namespace

HdRostrumMesh::~HdRostrumMesh()
{
    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->meshes.erase(GetId());
}

TfTokenVector const &HdRostrumMesh::GetBuiltinPrimvarNames() const
{
    static TfTokenVector names;
    return names;
}

void HdRostrumMesh::Sync(HdSceneDelegate *sd, HdRenderParam *, HdDirtyBits *bits, TfToken const &)
{
    SdfPath const &id = GetId();
    if (*bits & HdChangeTracker::DirtyMaterialId) SetMaterialId(sd->GetMaterialId(id));
    RostrumMeshData d;
    HdMeshTopology topo = GetMeshTopology(sd);
    VtVec3fArray points = sd->Get(id, HdTokens->points).GetWithDefault<VtVec3fArray>();
    Primvar normals = FindPrimvar(sd, id, HdTokens->normals);
    Primvar st = FindPrimvar(sd, id, TfToken("st"), true);
    VtIntArray const &counts = topo.GetFaceVertexCounts();
    VtIntArray const &idx = topo.GetFaceVertexIndices();
    bool flip = topo.GetOrientation() == HdTokens->leftHanded;

    // smooth vertex normals when none are authored
    std::vector<GfVec3f> smooth;
    if (normals.value.IsEmpty()) {
        smooth.assign(points.size(), GfVec3f(0));
        for (size_t f = 0, k = 0; f < counts.size(); k += counts[f++])
            for (int j = 1; j + 1 < counts[f]; ++j) {
                int a = idx[k], b = idx[k + j], c = idx[k + j + 1];
                GfVec3f n = GfCross(points[b] - points[a], points[c] - points[a]) * (flip ? -1.f : 1.f);
                smooth[a] += n; smooth[b] += n; smooth[c] += n;
            }
        for (GfVec3f &n : smooth) n.Normalize();
    }

    for (size_t f = 0, k = 0; f < counts.size(); k += counts[f++]) {
        for (int j = 1; j + 1 < counts[f]; ++j) {
            int corners[3] = {int(k), int(k + j), int(k + j + 1)};
            if (flip) std::swap(corners[1], corners[2]);
            for (int corner : corners) {
                int v = idx[corner];
                if (v < 0 || size_t(v) >= points.size()) continue;
                GfVec3f n(0, 1, 0);
                GfVec2f uv(0, 0);
                if (!Fetch(normals, int(f), v, corner, &n) && !smooth.empty()) n = smooth[v];
                Fetch(st, int(f), v, corner, &uv);
                d.P.push_back(points[v]); d.N.push_back(n); d.UV.push_back(uv);
            }
        }
    }

    d.xform = sd->GetTransform(id);
    d.visible = sd->GetVisible(id);
    d.material = GetMaterialId();
    d.displayColor = Constant<GfVec3f>(sd, id, "displayColor", d.displayColor);
    GfRange3d box;
    for (GfVec3f const &p : points) box.UnionWith(d.xform.Transform(GfVec3d(p)));
    if (!box.IsEmpty()) {
        GfVec3d c = box.GetMidpoint();
        d.pivot = GfVec3f(float(c[0]), float(box.GetMin()[1]), float(c[2]));
        d.center = GfVec3f(c);
        d.radius = float(box.GetSize().GetLength() * 0.5);
    }
    VtValue cam = FindPrimvar(sd, id, TfToken("rostrum:bend:camera")).value;
    if (cam.IsHolding<std::string>()) d.bend.camera = cam.UncheckedGet<std::string>();
    else if (cam.IsHolding<TfToken>()) d.bend.camera = cam.UncheckedGet<TfToken>().GetString();
    else if (cam.IsHolding<VtStringArray>() && !cam.UncheckedGet<VtStringArray>().empty())
        d.bend.camera = cam.UncheckedGet<VtStringArray>()[0];
    d.bend.squash = Constant<float>(sd, id, "rostrum:bend:squash", 1.0f);
    d.bend.lean = Constant<GfVec2f>(sd, id, "rostrum:bend:lean", GfVec2f(0));
    d.bend.swell = Constant<float>(sd, id, "rostrum:bend:swell", 0.0f);
    static std::atomic<unsigned> counter{0};
    d.version = ++counter;  // unique across meshes, so a re-created prim is re-uploaded

    std::lock_guard<std::mutex> g(_scene->lock);
    _scene->meshes[id] = std::move(d);
    *bits = HdChangeTracker::Clean;
}

PXR_NAMESPACE_CLOSE_SCOPE
