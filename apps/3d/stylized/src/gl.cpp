// OpenGL helpers (see gl.h).
#include "gl.h"

#include <pxr/imaging/hio/image.h>

#include <fstream>
#include <sstream>
#include <stdexcept>

PXR_NAMESPACE_OPEN_SCOPE

namespace {

std::string ReadSource(std::string const &dir, std::string const &name, int depth = 0)
{
    std::ifstream f(dir + "/" + name);
    if (!f) throw std::runtime_error("Rostrum Stylized: missing shader file " + dir + "/" + name);
    std::stringstream out;
    std::string line;
    while (std::getline(f, line)) {
        if (line.rfind("#include <", 0) == 0 && depth < 4)
            out << ReadSource(dir, line.substr(10, line.find('>') - 10), depth + 1) << "\n";
        else
            out << line << "\n";
    }
    return out.str();
}

GLuint Compile(GLenum kind, std::string const &src, std::string const &name)
{
    GLuint s = glCreateShader(kind);
    char const *p = src.c_str();
    glShaderSource(s, 1, &p, nullptr);
    glCompileShader(s);
    GLint ok = 0;
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char log[4096];
        glGetShaderInfoLog(s, sizeof(log), nullptr, log);
        glDeleteShader(s);
        throw std::runtime_error("Rostrum Stylized: " + name + " does not compile:\n" + log);
    }
    return s;
}

}  // namespace

GLuint RostrumProgram(std::string const &dir, char const *vert, char const *frag)
{
    GLuint vs = Compile(GL_VERTEX_SHADER, ReadSource(dir, vert), vert);
    GLuint fs = Compile(GL_FRAGMENT_SHADER, ReadSource(dir, frag), frag);
    GLuint p = glCreateProgram();
    glAttachShader(p, vs);
    glAttachShader(p, fs);
    glLinkProgram(p);
    glDeleteShader(vs);
    glDeleteShader(fs);
    GLint ok = 0;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) {
        char log[4096];
        glGetProgramInfoLog(p, sizeof(log), nullptr, log);
        glDeleteProgram(p);
        throw std::runtime_error(std::string("Rostrum Stylized: ") + frag + " does not link:\n" + log);
    }
    return p;
}

void RostrumSetLook(GLuint prog, std::map<std::string, float> const &look)
{
    for (auto const &[key, value] : look) {
        std::string name = "u_" + key.substr(8);  // drop "rostrum:"
        for (char &c : name)
            if (c == ':') c = '_';
        GLint loc = glGetUniformLocation(prog, name.c_str());
        if (loc >= 0) glUniform1f(loc, value);
    }
}

GLuint RostrumTexture(std::string const &path)
{
    static std::map<std::string, GLuint> cache;
    auto it = cache.find(path);
    if (it != cache.end()) return it->second;
    GLuint tex = 0;
    HioImageSharedPtr img = HioImage::OpenForReading(path);
    if (img) {
        HioImage::StorageSpec spec;
        spec.width = img->GetWidth();
        spec.height = img->GetHeight();
        spec.format = img->GetFormat();
        spec.flipped = false;
        std::vector<unsigned char> px(size_t(spec.width) * spec.height * HioGetDataSizeOfFormat(spec.format));
        spec.data = px.data();
        int n = HioGetComponentCount(spec.format);
        bool bytes = HioGetHioType(spec.format) == HioTypeUnsignedByte ||
                     HioGetHioType(spec.format) == HioTypeUnsignedByteSRGB;
        if (bytes && n >= 1 && n <= 4 && img->Read(spec)) {
            static GLenum const fmt[] = {GL_RED, GL_RG, GL_RGB, GL_RGBA};
            glGenTextures(1, &tex);
            glBindTexture(GL_TEXTURE_2D, tex);
            glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
            glTexImage2D(GL_TEXTURE_2D, 0, n >= 3 ? GL_SRGB8_ALPHA8 : GL_R8, spec.width, spec.height, 0,
                         fmt[n - 1], GL_UNSIGNED_BYTE, px.data());
            glGenerateMipmap(GL_TEXTURE_2D);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR_MIPMAP_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAX_ANISOTROPY, 8.0f);
        }
    }
    if (!tex) fprintf(stderr, "Rostrum Stylized: cannot read texture %s (8-bit images only)\n", path.c_str());
    cache[path] = tex;
    return tex;
}

void RostrumTarget::Resize(int width, int height, std::vector<GLenum> const &formats, bool withDepth)
{
    if (fbo && w == width && h == height) return;
    Release();
    w = width; h = height;
    glGenFramebuffers(1, &fbo);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    std::vector<GLenum> bufs;
    for (size_t i = 0; i < formats.size(); ++i) {
        GLuint t;
        glGenTextures(1, &t);
        glBindTexture(GL_TEXTURE_2D, t);
        glTexStorage2D(GL_TEXTURE_2D, 1, formats[i], w, h);
        bool integer = formats[i] == GL_R32I || formats[i] == GL_RG32I;
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, integer ? GL_NEAREST : GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, integer ? GL_NEAREST : GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GLenum(GL_COLOR_ATTACHMENT0 + i), GL_TEXTURE_2D, t, 0);
        color.push_back(t);
        bufs.push_back(GLenum(GL_COLOR_ATTACHMENT0 + i));
    }
    if (withDepth) {
        glGenTextures(1, &depth);
        glBindTexture(GL_TEXTURE_2D, depth);
        glTexStorage2D(GL_TEXTURE_2D, 1, GL_DEPTH_COMPONENT32F, w, h);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, depth, 0);
    }
    glDrawBuffers(GLsizei(bufs.size()), bufs.data());
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
        throw std::runtime_error("Rostrum Stylized: render target incomplete");
}

void RostrumTarget::Release()
{
    if (!color.empty()) glDeleteTextures(GLsizei(color.size()), color.data());
    if (depth) glDeleteTextures(1, &depth);
    if (fbo) glDeleteFramebuffers(1, &fbo);
    color.clear();
    fbo = depth = 0;
}

PXR_NAMESPACE_CLOSE_SCOPE
