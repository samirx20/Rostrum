// Alembic (.abc, Ogawa) into a converted layer (convert.h), read with Alembic 1.8.3 (BSD-3, the static library of
// Blender's library bundle). Read: the Xform tree with its transforms (animated ones as time samples), PolyMesh
// and SubD shapes with their points (animated as time samples; counts and indices too where the topology changes
// over time), normals (N) and UVs (uv). One time code per source frame: timeCodesPerSecond = 1 / the sampling
// step (24 when the file has no even step), start / end from the file's sample range. Alembic has no unit
// (metersPerUnit 1, unitsKnown false). Cameras, curves, points and visibility animation are not read.
#include <Alembic/AbcCoreFactory/IFactory.h>
#include <Alembic/AbcGeom/All.h>

#include <pxr/usd/usdGeom/tokens.h>

#include <algorithm>
#include <limits>

#include "convert_usd.h"
#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE

namespace r3d {

namespace {

namespace Abc = Alembic::Abc;
namespace AbcG = Alembic::AbcGeom;

AbcG::IN3fGeomParam normals_of(AbcG::IPolyMeshSchema& s) { return s.getNormalsParam(); }
AbcG::IN3fGeomParam normals_of(AbcG::ISubDSchema&) { return AbcG::IN3fGeomParam(); }

// One indexed geometry parameter (N or uv) as values + per-corner or per-point indices, in the flipped corner
// order `corner` (see Reader::geometry). False when it has no data or a scope we don't map.
template <class Param, class Values>
bool read_param(Param& param, const Abc::ISampleSelector& sel, const std::vector<int>& corner,
                const std::vector<int>& face_of, size_t points, Values& values, VtIntArray& indices,
                TfToken& interp) {
  if (!param.valid()) return false;
  typename Param::Sample s;
  param.getIndexed(s, sel);
  if (!s.getVals() || !s.getIndices()) return false;
  const auto& vals = *s.getVals();
  const auto& idx = *s.getIndices();
  values.resize(vals.size());
  for (size_t i = 0; i < vals.size(); ++i)
    for (int c = 0; c < int(values[i].dimension); ++c) values[i][c] = vals[i][c];
  indices.clear();
  switch (s.getScope()) {
    case AbcG::kFacevaryingScope:  // per face corner, reordered with the corners
      if (idx.size() != corner.size()) return false;
      for (int c : corner) indices.push_back(int(idx[size_t(c)]));
      interp = UsdGeomTokens->faceVarying;
      return true;
    case AbcG::kUniformScope:  // per face: every corner of a face takes the face's value
      for (int f : face_of) {
        if (size_t(f) >= idx.size()) return false;
        indices.push_back(int(idx[size_t(f)]));
      }
      interp = UsdGeomTokens->faceVarying;
      return true;
    case AbcG::kVertexScope:
    case AbcG::kVaryingScope:
      if (idx.size() != points) return false;
      for (size_t i = 0; i < idx.size(); ++i) indices.push_back(int(idx[i]));
      interp = UsdGeomTokens->vertex;
      return true;
    default: return false;
  }
}

struct Reader {
  UsdStageRefPtr stage;
  cv::Names names;
  double fps = 24.0;

  UsdTimeCode code(const Abc::TimeSamplingPtr& ts, size_t i) const {
    return UsdTimeCode(ts->getSampleTime(Abc::index_t(i)) * fps);
  }

  void xform(const Abc::IObject& obj, const SdfPath& path) {
    AbcG::IXform x(obj, Abc::kWrapExisting);
    AbcG::IXformSchema& s = x.getSchema();
    UsdGeomXform out = UsdGeomXform::Define(stage, path);
    const size_t n = s.getNumSamples();
    AbcG::XformSample smp;
    for (size_t i = 0; i < n; ++i) {  // none: an Xform with no transform
      s.get(smp, Abc::ISampleSelector(Abc::index_t(i)));
      const GfMatrix4d m(smp.getMatrix().x);  // Imath and USD both use row vectors
      cv::set_transform(out, m, s.isConstant() ? UsdTimeCode::Default() : code(s.getTimeSampling(), i));
      if (s.isConstant()) break;
    }
    if (n > 0 && !s.getInheritsXforms()) out.SetResetXformStack(true);
  }

  // A PolyMesh or SubD. Alembic's polygons wind clockwise; USD's (rightHanded) counter-clockwise: every face's
  // corners are reversed (first corner kept), and per-corner normals and UVs with them.
  template <class Obj>
  void geometry(const Abc::IObject& obj, const SdfPath& path, bool subdivided) {
    Obj o(obj, Abc::kWrapExisting);
    auto& s = o.getSchema();
    const size_t n = s.getNumSamples();
    const bool topology_changes = s.getTopologyVariance() == AbcG::kHeterogeneousTopology;
    auto uv = s.getUVsParam();
    auto nrm = normals_of(s);
    const bool extras_change =
        topology_changes || (uv.valid() && !uv.isConstant()) || (nrm.valid() && !nrm.isConstant());
    UsdGeomMesh mesh = UsdGeomMesh::Define(stage, path);
    for (size_t i = 0; i < n; ++i) {
      const Abc::ISampleSelector sel{Abc::index_t(i)};
      typename Obj::schema_type::Sample smp;
      s.get(smp, sel);
      if (!smp.getPositions() || !smp.getFaceCounts() || !smp.getFaceIndices()) continue;
      const auto& P = *smp.getPositions();
      const auto& counts = *smp.getFaceCounts();
      const auto& indices = *smp.getFaceIndices();
      cv::MeshArrays m;
      m.subdivided = subdivided;
      m.points.resize(P.size());
      for (size_t k = 0; k < P.size(); ++k) m.points[k] = GfVec3f(P[k].x, P[k].y, P[k].z);
      std::vector<int> corner, face_of;  // output corner -> source corner, and its face
      for (size_t f = 0, begin = 0; f < counts.size(); begin += size_t(counts[f]), ++f) {
        const int c = counts[f];
        m.counts.push_back(c);
        for (int k = 0; k < c; ++k) {
          corner.push_back(int(begin) + (k == 0 ? 0 : c - k));
          face_of.push_back(int(f));
        }
      }
      if (corner.size() != indices.size()) throw Error(path.GetName() + "'s faces don't match their corner list");
      for (int c : corner) m.indices.push_back(indices[size_t(c)]);
      if (!read_param(nrm, sel, corner, face_of, P.size(), m.normals, m.normal_indices, m.normal_interp))
        m.normals.clear();
      if (!read_param(uv, sel, corner, face_of, P.size(), m.uvs, m.uv_indices, m.uv_interp)) m.uvs.clear();

      if (n == 1) {
        cv::write_mesh_sample(mesh, m, UsdTimeCode::Default(), true, true, UsdTimeCode::Default());
        break;
      }
      const UsdTimeCode t = code(s.getTimeSampling(), i);
      if (i == 0 && !topology_changes)  // the topology (and still normals / UVs) once
        cv::write_mesh_sample(mesh, m, UsdTimeCode::Default(), true, !extras_change, UsdTimeCode::Default());
      cv::write_mesh_sample(mesh, m, t, topology_changes, extras_change, t);
    }
  }

  void walk(const Abc::IObject& obj, const SdfPath& parent) {
    for (size_t i = 0; i < obj.getNumChildren(); ++i) {
      const Abc::IObject child = obj.getChild(i);
      const Abc::ObjectHeader& h = child.getHeader();
      if (AbcG::IXform::matches(h)) {
        const SdfPath path = names.child(parent, child.getName(), "Xform");
        xform(child, path);
        walk(child, path);
      } else if (AbcG::IPolyMesh::matches(h)) {
        geometry<AbcG::IPolyMesh>(child, names.child(parent, child.getName(), "Mesh"), false);
      } else if (AbcG::ISubD::matches(h)) {
        geometry<AbcG::ISubD>(child, names.child(parent, child.getName(), "Mesh"), true);
      }
    }
  }
};

}  // namespace

void convert_abc(const std::string& file, const UsdStageRefPtr& out) {
  Alembic::AbcCoreFactory::IFactory factory;
  Abc::IArchive archive = factory.getArchive(file);
  if (!archive.valid()) throw Error("it isn't an Alembic file this reads (only Ogawa .abc files are read, not old HDF5 ones)");

  // the frame rate and the range: the first even sampling that has frames, and every sampling's first / last time
  Reader r;
  r.stage = out;
  bool found_rate = false;
  double start = std::numeric_limits<double>::max(), end = std::numeric_limits<double>::lowest();
  for (uint32_t i = 0; i < archive.getNumTimeSamplings(); ++i) {
    const Abc::index_t samples = archive.getMaxNumSamplesForTimeSamplingIndex(i);
    if (samples < 2 || samples == INDEX_UNKNOWN) continue;
    const Abc::TimeSamplingPtr ts = archive.getTimeSampling(i);
    const auto type = ts->getTimeSamplingType();
    if (!found_rate && type.isUniform() && type.getTimePerCycle() > 0) {
      r.fps = 1.0 / type.getTimePerCycle();
      found_rate = true;
    }
    start = std::min(start, ts->getSampleTime(0));
    end = std::max(end, ts->getSampleTime(samples - 1));
  }

  const SdfPath root = cv::start_layer(out, file, "Alembic", 1.0, false).GetPath();
  if (start <= end) cv::set_time_range(out, start * r.fps, end * r.fps, r.fps);
  r.walk(archive.getTop(), root);
}

}  // namespace r3d
