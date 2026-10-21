#include "ocio_gpu.h"

#include <epoxy/gl.h>
#include <OpenColorIO/OpenColorIO.h>

#include <vector>

#include "error.h"

namespace OCIO = OCIO_NAMESPACE;

namespace r3d {

namespace {
struct Texture {
  unsigned id = 0, target = 0;
  std::string sampler;
};

GLint filter(OCIO::Interpolation i) { return i == OCIO::INTERP_NEAREST ? GL_NEAREST : GL_LINEAR; }

void params(unsigned target, GLint f) {
  glTexParameteri(target, GL_TEXTURE_MIN_FILTER, f);
  glTexParameteri(target, GL_TEXTURE_MAG_FILTER, f);
  glTexParameteri(target, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
  glTexParameteri(target, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
  glTexParameteri(target, GL_TEXTURE_WRAP_R, GL_CLAMP_TO_EDGE);
}
}  // namespace

struct OcioGpu::Impl {
  OCIO::GpuShaderDescRcPtr desc;
  std::string glsl;
  std::vector<Texture> textures;
};

OcioGpu::OcioGpu(const std::string& config, const std::string& display, const std::string& view)
    : impl_(std::make_unique<Impl>()) {
  try {
    auto cfg = OCIO::Config::CreateFromFile(config.c_str());
    auto t = OCIO::DisplayViewTransform::Create();
    t->setSrc(OCIO::ROLE_SCENE_LINEAR);
    t->setDisplay(display.c_str());
    t->setView(view.c_str());
    auto gpu = cfg->getProcessor(t)->getDefaultGPUProcessor();
    impl_->desc = OCIO::GpuShaderDesc::CreateShaderDesc();
    impl_->desc->setLanguage(OCIO::GPU_LANGUAGE_GLSL_4_0);
    impl_->desc->setFunctionName("OCIODisplay");
    impl_->desc->setResourcePrefix("ocio_");
    gpu->extractGpuShaderInfo(impl_->desc);
  } catch (const OCIO::Exception& e) {
    throw Error("view: OpenColorIO could not make the graphics-card transform for display \"" + display +
                "\", view \"" + view + "\": " + e.what());
  }
  const auto& d = *impl_->desc;
  impl_->glsl = d.getShaderText();
  for (unsigned i = 0; i < d.getNum3DTextures(); ++i) {
    const char *name, *sampler;
    unsigned edge;
    OCIO::Interpolation interp;
    const float* values;
    d.get3DTexture(i, name, sampler, edge, interp);
    d.get3DTextureValues(i, values);
    Texture t{0, GL_TEXTURE_3D, sampler};
    glGenTextures(1, &t.id);
    glBindTexture(GL_TEXTURE_3D, t.id);
    params(GL_TEXTURE_3D, filter(interp));
    glTexImage3D(GL_TEXTURE_3D, 0, GL_RGB32F, edge, edge, edge, 0, GL_RGB, GL_FLOAT, values);
    impl_->textures.push_back(t);
  }
  for (unsigned i = 0; i < d.getNumTextures(); ++i) {
    const char *name, *sampler;
    unsigned w, h;
    OCIO::GpuShaderDesc::TextureType channel;
    OCIO::GpuShaderDesc::TextureDimensions dims;
    OCIO::Interpolation interp;
    const float* values;
    d.getTexture(i, name, sampler, w, h, channel, dims, interp);
    d.getTextureValues(i, values);
    const bool red = channel == OCIO::GpuShaderDesc::TEXTURE_RED_CHANNEL;
    const GLint inner = red ? GL_R32F : GL_RGB32F;
    const GLenum fmt = red ? GL_RED : GL_RGB;
    Texture t{0, unsigned(dims == OCIO::GpuShaderDesc::TEXTURE_1D ? GL_TEXTURE_1D : GL_TEXTURE_2D), sampler};
    glGenTextures(1, &t.id);
    glBindTexture(t.target, t.id);
    params(t.target, filter(interp));
    if (t.target == GL_TEXTURE_1D) glTexImage1D(GL_TEXTURE_1D, 0, inner, w, 0, fmt, GL_FLOAT, values);
    else glTexImage2D(GL_TEXTURE_2D, 0, inner, w, h, 0, fmt, GL_FLOAT, values);
    impl_->textures.push_back(t);
  }
  glBindTexture(GL_TEXTURE_2D, 0);
}

OcioGpu::~OcioGpu() {
  for (auto& t : impl_->textures) glDeleteTextures(1, &t.id);
}

const std::string& OcioGpu::glsl() const { return impl_->glsl; }

void OcioGpu::bind(unsigned program, int first_unit) const {
  int unit = first_unit;
  for (const auto& t : impl_->textures) {
    glActiveTexture(GL_TEXTURE0 + unit);
    glBindTexture(t.target, t.id);
    glUniform1i(glGetUniformLocation(program, t.sampler.c_str()), unit++);
  }
  const auto& d = *impl_->desc;
  for (unsigned i = 0; i < d.getNumUniforms(); ++i) {  // only views with live values have any
    OCIO::GpuShaderDesc::UniformData u;
    const GLint at = glGetUniformLocation(program, d.getUniform(i, u));
    switch (u.m_type) {
      case OCIO::UNIFORM_DOUBLE: glUniform1f(at, float(u.m_getDouble())); break;
      case OCIO::UNIFORM_BOOL: glUniform1i(at, u.m_getBool() ? 1 : 0); break;
      case OCIO::UNIFORM_FLOAT3: glUniform3f(at, u.m_getFloat3()[0], u.m_getFloat3()[1], u.m_getFloat3()[2]); break;
      case OCIO::UNIFORM_VECTOR_FLOAT: glUniform1fv(at, GLsizei(u.m_vectorFloat.m_getSize()), u.m_vectorFloat.m_getVector()); break;
      case OCIO::UNIFORM_VECTOR_INT: glUniform1iv(at, GLsizei(u.m_vectorInt.m_getSize()), u.m_vectorInt.m_getVector()); break;
      default: throw Error("view: OpenColorIO asked for a shader value of an unknown type");
    }
  }
  glActiveTexture(GL_TEXTURE0);
}

}  // namespace r3d
