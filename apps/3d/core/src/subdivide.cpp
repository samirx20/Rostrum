#include "subdivide.h"

#include <memory>

#include <opensubdiv/far/primvarRefiner.h>
#include <opensubdiv/far/topologyDescriptor.h>
#include <opensubdiv/far/topologyRefinerFactory.h>

#include "error.h"

PXR_NAMESPACE_USING_DIRECTIVE
using namespace OpenSubdiv;

namespace r3d {
namespace {

// The point type PrimvarRefiner interpolates.
struct Vert {
  GfVec3f p;
  void Clear() { p = GfVec3f(0); }
  void AddWithWeight(const Vert& o, float w) { p += o.p * w; }
};

}  // namespace

PolyCage subdivide(const PolyCage& cage, const std::vector<int>& creases, int level) {
  using Factory = Far::TopologyRefinerFactory<Far::TopologyDescriptor>;
  Far::TopologyDescriptor desc;
  desc.numVertices = int(cage.points.size());
  desc.numFaces = int(cage.counts.size());
  desc.numVertsPerFace = cage.counts.data();
  desc.vertIndicesPerFace = cage.indices.data();
  const std::vector<float> sharp(creases.size() / 2, Sdc::Crease::SHARPNESS_INFINITE);
  desc.numCreases = int(sharp.size());
  desc.creaseVertexIndexPairs = creases.data();
  desc.creaseWeights = sharp.data();

  Sdc::Options opt;
  opt.SetVtxBoundaryInterpolation(Sdc::Options::VTX_BOUNDARY_EDGE_AND_CORNER);
  std::unique_ptr<Far::TopologyRefiner> r(Factory::Create(desc, Factory::Options(Sdc::SCHEME_CATMARK, opt)));
  if (!r) throw Error("subdivide: OpenSubdiv could not read this mesh (a face that folds over or an edge shared "
                      "by more than two faces); Smooth surface 0 draws it unsmoothed");
  Far::TopologyRefiner::UniformOptions uo(level);
  uo.fullTopologyInLastLevel = true;  // edges of the result, for its sharp edges
  r->RefineUniform(uo);

  std::vector<Vert> now(cage.points.size());
  for (size_t i = 0; i < now.size(); ++i) now[i].p = cage.points[i];
  std::vector<int> parent(cage.counts.size());
  for (size_t f = 0; f < parent.size(); ++f) parent[f] = int(f);
  Far::PrimvarRefiner pr(*r);
  for (int l = 1; l <= level; ++l) {
    const Far::TopologyLevel& lv = r->GetLevel(l);
    std::vector<Vert> next(lv.GetNumVertices());
    Vert* src = now.data();
    Vert* dst = next.data();
    pr.Interpolate(l, src, dst);
    now.swap(next);
    std::vector<int> up(lv.GetNumFaces());
    for (int f = 0; f < lv.GetNumFaces(); ++f) up[f] = parent[lv.GetFaceParentFace(f)];
    parent.swap(up);
  }

  const Far::TopologyLevel& last = r->GetLevel(level);
  PolyCage out;
  out.points.reserve(now.size());
  for (const Vert& v : now) out.points.push_back(v.p);
  for (int f = 0; f < last.GetNumFaces(); ++f) {
    const Far::ConstIndexArray fv = last.GetFaceVertices(f);
    out.counts.push_back(fv.size());
    for (int c = 0; c < fv.size(); ++c) out.indices.push_back(fv[c]);
  }
  out.on_crease.assign(out.points.size(), 0);
  for (int e = 0; e < last.GetNumEdges(); ++e)
    if (last.GetEdgeSharpness(e) > 0) {
      const Far::ConstIndexArray ev = last.GetEdgeVertices(e);
      out.on_crease[ev[0]] = out.on_crease[ev[1]] = 1;
    }
  out.base_face = std::move(parent);
  return out;
}

}  // namespace r3d
