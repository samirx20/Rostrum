#include "implicit_shapes.h"

#include "primitives.h"

#include <pxr/base/gf/matrix4d.h>
#include <pxr/base/gf/rotation.h>
#include <pxr/base/tf/stringUtils.h>
#include <pxr/imaging/hd/capsuleSchema.h>
#include <pxr/imaging/hd/coneSchema.h>
#include <pxr/imaging/hd/cubeSchema.h>
#include <pxr/imaging/hd/cylinderSchema.h>
#include <pxr/imaging/hd/filteringSceneIndex.h>
#include <pxr/imaging/hd/meshSchema.h>
#include <pxr/imaging/hd/meshTopologySchema.h>
#include <pxr/imaging/hd/overlayContainerDataSource.h>
#include <pxr/imaging/hd/planeSchema.h>
#include <pxr/imaging/hd/primvarSchema.h>
#include <pxr/imaging/hd/primvarsSchema.h>
#include <pxr/imaging/hd/retainedDataSource.h>
#include <pxr/imaging/hd/sceneIndexPluginRegistry.h>
#include <pxr/imaging/hd/sphereSchema.h>
#include <pxr/imaging/hd/tokens.h>
#include <pxr/imaging/hdsi/implicitSurfaceSceneIndex.h>
#include <pxr/imaging/pxOsd/tokens.h>
#include <pxr/usd/usdGeom/tokens.h>

#include <cmath>
#include <map>
#include <mutex>
#include <optional>
#include <string>

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {
constexpr int kSegments = 64;  // a Rostrum round shape's steps around when made (mesh_fields.py ROUND_SEGMENTS)

double num(const HdDoubleDataSourceHandle& d, double fallback) { return d ? d->GetTypedValue(0.0f) : fallback; }
TfToken axis_of(const HdTokenDataSourceHandle& d) { return d ? d->GetTypedValue(0.0f) : UsdGeomTokens->z; }

// One shape's mesh, as the core makes its own (Y up), then turned so Y lies along the USD shape's axis (Z unless said).
// nullopt: not one ours makes (a tapered cylinder / capsule), USD's own filter behind this one makes it.
std::optional<MeshData> make(const TfToken& type, const HdContainerDataSourceHandle& ds, TfToken* axis) {
  *axis = UsdGeomTokens->y;
  if (type == HdPrimTypeTokens->sphere)
    return make_sphere(float(num(HdSphereSchema::GetFromParent(ds).GetRadius(), 1.0)), kSegments, true);
  if (type == HdPrimTypeTokens->cube) {
    const float s = float(num(HdCubeSchema::GetFromParent(ds).GetSize(), 2.0));
    return make_box(s, s, s, 0.0f, 1, true);
  }
  if (type == HdPrimTypeTokens->cone) {
    const HdConeSchema c = HdConeSchema::GetFromParent(ds);
    *axis = axis_of(c.GetAxis());
    return make_cone(float(num(c.GetRadius(), 1.0)), float(num(c.GetHeight(), 2.0)), kSegments, true);
  }
  if (type == HdPrimTypeTokens->cylinder || type == HdPrimTypeTokens->capsule) {
    const bool cyl = type == HdPrimTypeTokens->cylinder;
    const HdCylinderSchema y = HdCylinderSchema::GetFromParent(ds);
    const HdCapsuleSchema p = HdCapsuleSchema::GetFromParent(ds);
    const double r = num(cyl ? y.GetRadius() : p.GetRadius(), cyl ? 1.0 : 0.5);
    const double top = num(cyl ? y.GetRadiusTop() : p.GetRadiusTop(), r), bottom = num(cyl ? y.GetRadiusBottom() : p.GetRadiusBottom(), r);
    if (std::abs(top - bottom) > 1e-9) return std::nullopt;
    const double h = num(cyl ? y.GetHeight() : p.GetHeight(), 1.0);
    *axis = axis_of(cyl ? y.GetAxis() : p.GetAxis());
    // USD's capsule height is its straight part; ours is end to end
    return cyl ? make_cylinder(float(top), float(h), 0.0f, kSegments, true)
               : make_capsule(float(top), float(h + 2 * top), kSegments, true);
  }
  if (type == HdPrimTypeTokens->plane) {
    const HdPlaneSchema pl = HdPlaneSchema::GetFromParent(ds);
    *axis = axis_of(pl.GetAxis());  // the plane's normal; width runs along X (along Z for an X axis), length the other way
    const float w = float(num(pl.GetWidth(), 2.0)), l = float(num(pl.GetLength(), 2.0));
    return *axis == UsdGeomTokens->x ? make_plane(l, w) : make_plane(w, l);
  }
  return std::nullopt;
}

// Y to the axis: Z by +90° about X, X by −90° about Z (rotations, so faces keep their winding)
void turn(MeshData& m, const TfToken& axis) {
  if (axis == UsdGeomTokens->y) return;
  const GfMatrix4d r(GfRotation(axis == UsdGeomTokens->z ? GfVec3d(1, 0, 0) : GfVec3d(0, 0, 1),
                                axis == UsdGeomTokens->z ? 90.0 : -90.0), GfVec3d(0.0));
  for (GfVec3f& p : m.points) p = GfVec3f(r.Transform(GfVec3d(p)));
  for (GfVec3f& n : m.normals) n = GfVec3f(r.TransformDir(GfVec3d(n)));
}

HdDataSourceBaseHandle primvar(const VtValue& v, const TfToken& interp, const TfToken& role) {
  return HdPrimvarSchema::Builder()
      .SetPrimvarValue(HdRetainedSampledDataSource::New(v))
      .SetInterpolation(HdPrimvarSchema::BuildInterpolationDataSource(interp))
      .SetRole(HdPrimvarSchema::BuildRoleDataSource(role))
      .Build();
}

// The mesh and primvars put over the shape's own data (its primvars, material, transform stay). Shared by every
// shape with the same sizes: a scene of 500 equal imported spheres builds one mesh.
HdContainerDataSourceHandle mesh_source(const TfToken& type, const HdContainerDataSourceHandle& ds) {
  TfToken axis;
  std::optional<MeshData> m = make(type, ds, &axis);
  if (!m) return nullptr;
  turn(*m, axis);
  const bool two_sided = type == HdPrimTypeTokens->plane &&
                         [&] { auto d = HdPlaneSchema::GetFromParent(ds).GetDoubleSided(); return d && d->GetTypedValue(0.0f); }();
  const auto& T = HdPrimvarSchemaTokens;
  const TfToken names[] = {HdTokens->points, HdTokens->normals, TfToken("st")};
  const HdDataSourceBaseHandle values[] = {primvar(VtValue(m->points), T->vertex, T->point),
                                           primvar(VtValue(m->normals), T->vertex, T->normal),  // Cycles reads vertex normals only
                                           primvar(VtValue(m->st), T->faceVarying, T->textureCoordinate)};
  return HdRetainedContainerDataSource::New(
      HdMeshSchema::GetSchemaToken(),
      HdMeshSchema::Builder()
          .SetTopology(HdMeshTopologySchema::Builder()
                           .SetFaceVertexCounts(HdRetainedTypedSampledDataSource<VtIntArray>::New(m->counts))
                           .SetFaceVertexIndices(HdRetainedTypedSampledDataSource<VtIntArray>::New(m->indices))
                           .SetOrientation(HdMeshTopologySchema::BuildOrientationDataSource(HdTokens->rightHanded))
                           .Build())
          .SetSubdivisionScheme(HdRetainedTypedSampledDataSource<TfToken>::New(PxOsdOpenSubdivTokens->none))
          .SetDoubleSided(HdRetainedTypedSampledDataSource<bool>::New(two_sided))
          .Build(),
      HdPrimvarsSchema::GetSchemaToken(), HdRetainedContainerDataSource::New(3, names, values));
}

bool is_shape(const TfToken& t) {
  return t == HdPrimTypeTokens->sphere || t == HdPrimTypeTokens->cube || t == HdPrimTypeTokens->cylinder ||
         t == HdPrimTypeTokens->cone || t == HdPrimTypeTokens->capsule || t == HdPrimTypeTokens->plane;
}

class SmoothShapes final : public HdSingleInputFilteringSceneIndexBase {
 public:
  static HdSceneIndexBaseRefPtr New(const HdSceneIndexBaseRefPtr& in) { return TfCreateRefPtr(new SmoothShapes(in)); }

  HdSceneIndexPrim GetPrim(const SdfPath& path) const override {
    HdSceneIndexPrim prim = _GetInputSceneIndex()->GetPrim(path);
    if (!is_shape(prim.primType) || !prim.dataSource) return prim;
    if (HdContainerDataSourceHandle mesh = cached(prim.primType, prim.dataSource)) {
      prim.primType = HdPrimTypeTokens->mesh;
      prim.dataSource = HdOverlayContainerDataSource::New(mesh, prim.dataSource);
    }
    return prim;
  }
  SdfPathVector GetChildPrimPaths(const SdfPath& path) const override {
    return _GetInputSceneIndex()->GetChildPrimPaths(path);
  }

 protected:
  void _PrimsAdded(const HdSceneIndexBase&, const HdSceneIndexObserver::AddedPrimEntries& e) override {
    HdSceneIndexObserver::AddedPrimEntries out(e);  // a renderer makes its prim by the type it is added with
    for (auto& a : out)
      if (is_shape(a.primType)) a.primType = GetPrim(a.primPath).primType;
    _SendPrimsAdded(out);
  }
  void _PrimsRemoved(const HdSceneIndexBase&, const HdSceneIndexObserver::RemovedPrimEntries& e) override {
    _SendPrimsRemoved(e);
  }
  void _PrimsDirtied(const HdSceneIndexBase&, const HdSceneIndexObserver::DirtiedPrimEntries& e) override {
    static const HdDataSourceLocatorSet sizes{HdSphereSchema::GetDefaultLocator(), HdCubeSchema::GetDefaultLocator(),
                                              HdCylinderSchema::GetDefaultLocator(), HdConeSchema::GetDefaultLocator(),
                                              HdCapsuleSchema::GetDefaultLocator(), HdPlaneSchema::GetDefaultLocator()};
    HdSceneIndexObserver::DirtiedPrimEntries out(e);  // a changed size remakes the mesh: its points, normals, faces
    for (auto& d : out)
      if (d.dirtyLocators.Intersects(sizes)) {
        d.dirtyLocators.insert(HdMeshSchema::GetDefaultLocator());
        d.dirtyLocators.insert(HdPrimvarsSchema::GetPointsLocator());
        d.dirtyLocators.insert(HdPrimvarsSchema::GetNormalsLocator());
        d.dirtyLocators.insert(HdPrimvarsSchema::GetDefaultLocator().Append(TfToken("st")));
      }
    _SendPrimsDirtied(out);
  }

 private:
  explicit SmoothShapes(const HdSceneIndexBaseRefPtr& in) : HdSingleInputFilteringSceneIndexBase(in) {}

  // made once per type and sizes (a renderer asks for a prim many times while it syncs)
  HdContainerDataSourceHandle cached(const TfToken& type, const HdContainerDataSourceHandle& ds) const {
    std::string key = type.GetString();
    for (const TfToken& n : {HdSphereSchema::GetSchemaToken(), HdCubeSchema::GetSchemaToken(), HdCylinderSchema::GetSchemaToken(),
                             HdConeSchema::GetSchemaToken(), HdCapsuleSchema::GetSchemaToken(), HdPlaneSchema::GetSchemaToken()})
      if (auto c = HdContainerDataSource::Cast(ds->Get(n)))
        for (const TfToken& f : c->GetNames())
          if (auto s = HdSampledDataSource::Cast(c->Get(f))) key += "|" + f.GetString() + "=" + TfStringify(s->GetValue(0.0f));
    std::lock_guard<std::mutex> lock(mutex_);
    if (auto it = cache_.find(key); it != cache_.end()) return it->second;
    if (cache_.size() > 512) cache_.clear();  // bounded: sizes keyed over time would otherwise pile up
    return cache_[key] = mesh_source(type, ds);
  }
  mutable std::mutex mutex_;
  mutable std::map<std::string, HdContainerDataSourceHandle> cache_;
};
}  // namespace

void register_implicit_shapes() {
  static const bool once = [] {
    HdSceneIndexPluginRegistry& reg = HdSceneIndexPluginRegistry::GetInstance();
    for (const char* renderer : {"GL", "Cycles", "Rostrum Stylized"})  // display names (their plugInfo.json)
      reg.RegisterSceneIndexForRenderer(
          renderer, [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle&) {
            return SmoothShapes::New(in);
          },
          nullptr, -1, HdSceneIndexPluginRegistry::InsertionOrderAtStart);  // phase −1: before Storm's own (phase 0)
    // what ours leaves (tapered cylinders and capsules) still becomes a mesh for the mesh-only renderers
    const HdDataSourceBaseHandle to_mesh =
        HdRetainedTypedSampledDataSource<TfToken>::New(HdsiImplicitSurfaceSceneIndexTokens->toMesh);
    const HdContainerDataSourceHandle args = HdRetainedContainerDataSource::New(
        HdPrimTypeTokens->sphere, to_mesh, HdPrimTypeTokens->cube, to_mesh, HdPrimTypeTokens->cylinder, to_mesh,
        HdPrimTypeTokens->cone, to_mesh, HdPrimTypeTokens->capsule, to_mesh, HdPrimTypeTokens->plane, to_mesh);
    for (const char* renderer : {"Cycles", "Rostrum Stylized"})
      reg.RegisterSceneIndexForRenderer(
          renderer,
          [](const std::string&, const HdSceneIndexBaseRefPtr& in, const HdContainerDataSourceHandle& a) {
            return HdsiImplicitSurfaceSceneIndex::New(in, a);
          },
          args, 0, HdSceneIndexPluginRegistry::InsertionOrderAtStart);
    return true;
  }();
  (void)once;
}

}  // namespace r3d
