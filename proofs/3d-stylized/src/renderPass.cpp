// P-3D-3: the stylized render pass (see renderPass.h). Renders at `rostrum:ss` x the output size
// (supersampling, default 2) and box-filters down; writes the colour and depth AOVs.
#include "renderPass.h"
#include "delegate.h"
#include "lights.h"
#include "renderBuffer.h"

#include <pxr/base/plug/plugin.h>
#include <pxr/base/plug/registry.h>
#include <pxr/base/tf/getenv.h>
#include <pxr/base/gf/range3d.h>
#include <pxr/imaging/hd/camera.h>
#include <pxr/imaging/hd/tokens.h>

#ifdef _WIN32
#include <epoxy/wgl.h>
#endif

#include <chrono>
#include <cstring>
#include <stdexcept>

PXR_NAMESPACE_OPEN_SCOPE

struct GpuMesh {
    GLuint vao = 0, vbo = 0;
    GLsizei count = 0;
    unsigned version = 0;
};

struct RostrumGpu {
    std::string dir;
    GLuint geom = 0, shadow = 0, shade = 0, edges = 0, ink = 0, emptyVao = 0, ramps = 0;
    GLuint shadowTex = 0, shadowFbo = 0;
    int shadowSize = 0;
    std::map<SdfPath, GpuMesh> meshes;
    RostrumTarget gbuf, shaded, edged, inked, out;
};

namespace {

void U(GLuint p, char const *n, GfMatrix4d const &m)
{
    GfMatrix4f f(m);
    glUniformMatrix4fv(glGetUniformLocation(p, n), 1, GL_FALSE, f.data());
}
void U(GLuint p, char const *n, float v) { glUniform1f(glGetUniformLocation(p, n), v); }
void U(GLuint p, char const *n, int v) { glUniform1i(glGetUniformLocation(p, n), v); }
void U(GLuint p, char const *n, GfVec3f const &v) { glUniform3fv(glGetUniformLocation(p, n), 1, v.data()); }
void U(GLuint p, char const *n, GfVec2f const &v) { glUniform2fv(glGetUniformLocation(p, n), 1, v.data()); }

void Units(GLuint p, std::initializer_list<std::pair<char const *, int>> units)
{
    for (auto const &[name, unit] : units) glUniform1i(glGetUniformLocation(p, name), unit);
}

void Bind(int unit, GLenum target, GLuint tex)
{
    glActiveTexture(GL_TEXTURE0 + unit);
    glBindTexture(target, tex);
}

std::string ShaderDir()
{
    std::string env = TfGetenv("ROSTRUM_SHADERS");
    if (!env.empty()) return env;
    PlugPluginPtr plug = PlugRegistry::GetInstance().GetPluginWithName("hdRostrum");
    if (!plug) throw std::runtime_error("Rostrum Stylized: plug-in hdRostrum not registered");
    return plug->GetResourcePath() + "/shaders";
}

void Upload(GpuMesh &g, RostrumMeshData const &m)
{
    std::vector<float> v;
    v.reserve(m.P.size() * 8);
    for (size_t i = 0; i < m.P.size(); ++i) {
        v.insert(v.end(), {m.P[i][0], m.P[i][1], m.P[i][2], m.N[i][0], m.N[i][1], m.N[i][2]});
        v.insert(v.end(), {m.UV[i][0], m.UV[i][1]});
    }
    if (!g.vao) { glGenVertexArrays(1, &g.vao); glGenBuffers(1, &g.vbo); }
    glBindVertexArray(g.vao);
    glBindBuffer(GL_ARRAY_BUFFER, g.vbo);
    glBufferData(GL_ARRAY_BUFFER, v.size() * sizeof(float), v.data(), GL_STATIC_DRAW);
    for (int a = 0; a < 3; ++a) glEnableVertexAttribArray(a);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 32, (void *)0);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 32, (void *)12);
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 32, (void *)24);
    g.count = GLsizei(m.P.size());
    g.version = m.version;
}

// per-mesh uniforms for the geometry and shadow programs (model matrix, camera-only bend)
void MeshUniforms(GLuint p, RostrumMeshData const &m, std::string const &camera)
{
    U(p, "u_model", m.xform);
    U(p, "u_bendOn", int(!m.bend.camera.empty() && m.bend.camera == camera));
    U(p, "u_bendPivot", m.pivot);
    U(p, "u_bendRadius", std::max(m.radius, 1e-4f));
    U(p, "u_bendSquash", m.bend.squash);
    U(p, "u_bendLean", m.bend.lean);
    U(p, "u_bendSwell", m.bend.swell);
}

struct SavedGl {
    GLint draw, read, prog, vao, viewport[4], active, pack, unpack;
    GLboolean depth, cull, blend, scissor, srgb;
    SavedGl()
    {
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &draw); glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &read);
        glGetIntegerv(GL_CURRENT_PROGRAM, &prog); glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vao);
        glGetIntegerv(GL_VIEWPORT, viewport); glGetIntegerv(GL_ACTIVE_TEXTURE, &active);
        glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &pack); glGetIntegerv(GL_PIXEL_UNPACK_BUFFER_BINDING, &unpack);
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0);    // our uploads and read-backs use client memory
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0);
        depth = glIsEnabled(GL_DEPTH_TEST); cull = glIsEnabled(GL_CULL_FACE); blend = glIsEnabled(GL_BLEND);
        scissor = glIsEnabled(GL_SCISSOR_TEST); srgb = glIsEnabled(GL_FRAMEBUFFER_SRGB);
    }
    ~SavedGl()
    {
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, draw); glBindFramebuffer(GL_READ_FRAMEBUFFER, read);
        glUseProgram(prog); glBindVertexArray(vao);
        glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
        auto set = [](GLenum cap, GLboolean on) { on ? glEnable(cap) : glDisable(cap); };
        set(GL_DEPTH_TEST, depth); set(GL_CULL_FACE, cull); set(GL_BLEND, blend);
        set(GL_SCISSOR_TEST, scissor); set(GL_FRAMEBUFFER_SRGB, srgb);
        glActiveTexture(active);
        glBindBuffer(GL_PIXEL_PACK_BUFFER, pack); glBindBuffer(GL_PIXEL_UNPACK_BUFFER, unpack);
    }
};

}  // namespace

HdRostrumRenderPass::HdRostrumRenderPass(HdRenderIndex *index, HdRprimCollection const &collection,
                                         HdRostrumDelegate *delegate)
    : HdRenderPass(index, collection), _delegate(delegate)
{
}

HdRostrumRenderPass::~HdRostrumRenderPass() = default;  // GL objects die with the host's context

void HdRostrumRenderPass::_Execute(HdRenderPassStateSharedPtr const &state, TfTokenVector const &)
{
    HdRostrumRenderBuffer *color = nullptr, *depth = nullptr;
    for (HdRenderPassAovBinding const &b : state->GetAovBindings()) {
        auto *rb = static_cast<HdRostrumRenderBuffer *>(b.renderBuffer);
        if (!rb) continue;
        if (b.aovName == HdAovTokens->color) color = rb;
        else if (b.aovName == HdAovTokens->depth) depth = rb;
        else {  // ids: "nothing here"
            std::memset(rb->Map(), 0xff, size_t(rb->GetWidth()) * rb->GetHeight() * HdDataSizeOfFormat(rb->GetFormat()));
            rb->Unmap();
            rb->SetConverged(true);
        }
    }
    if (!color) {
        TF_RUNTIME_ERROR("Rostrum Stylized: the host asked for no colour AOV");
        return;
    }
    if (!wglGetCurrentContext())
        TF_FATAL_ERROR("Rostrum Stylized: no current OpenGL context (the host must provide one)");
    int w = int(color->GetWidth()), h = int(color->GetHeight());
    SavedGl saved;
    auto t0 = std::chrono::steady_clock::now();
    try {
        _Draw(state, w, h);
        glFinish();
        auto ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        if (TfGetenvBool("ROSTRUM_DEBUG", false)) printf("[rostrum] frame %dx%d: %.1f ms\n", w, h, ms);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, _gpu->out.fbo);
        glReadBuffer(GL_COLOR_ATTACHMENT0);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        HdFormat f = color->GetFormat();
        GLenum type = f == HdFormatFloat16Vec4 ? GL_HALF_FLOAT : f == HdFormatFloat32Vec4 ? GL_FLOAT
                    : f == HdFormatUNorm8Vec4 ? GL_UNSIGNED_BYTE : 0;
        if (!type) throw std::runtime_error("Rostrum Stylized: unsupported colour AOV format");
        void *px = color->Map();
        glReadPixels(0, 0, w, h, GL_RGBA, type, px);
        if (TfGetenvBool("ROSTRUM_DEBUG", false) && type == GL_FLOAT) {
            float const *c = static_cast<float const *>(px) + (size_t(h / 2) * w + w / 2) * 4;
            printf("[rostrum] centre pixel %.3f %.3f %.3f %.3f\n", c[0], c[1], c[2], c[3]);
        }
        if (TfGetenvBool("ROSTRUM_DEBUG", false)) printf("[rostrum] colour AOV format %d\n", int(f));
        color->Unmap();
        if (depth && depth->GetFormat() == HdFormatFloat32 && int(depth->GetWidth()) == w) {
            glReadPixels(0, 0, w, h, GL_DEPTH_COMPONENT, GL_FLOAT, depth->Map());
            depth->Unmap();
        }
    } catch (std::exception const &e) {
        TF_RUNTIME_ERROR("%s", e.what());  // the host turns any Tf error into a failed render
    }
    color->SetConverged(true);
    if (depth) depth->SetConverged(true);
}

void HdRostrumRenderPass::_Draw(HdRenderPassStateSharedPtr const &state, int w, int h)
{
    while (glGetError() != GL_NO_ERROR) {}  // errors left by the host are not ours
    if (!_gpu) {
        _gpu = std::make_unique<RostrumGpu>();
        RostrumGpu &g = *_gpu;
        g.dir = ShaderDir();
        g.geom = RostrumProgram(g.dir, "geom.vert", "gbuffer.frag");
        g.shadow = RostrumProgram(g.dir, "geom.vert", "shadow.frag");
        g.shade = RostrumProgram(g.dir, "screen.vert", "shade.frag");
        g.edges = RostrumProgram(g.dir, "screen.vert", "edges.frag");
        g.ink = RostrumProgram(g.dir, "screen.vert", "ink.frag");
        glGenVertexArrays(1, &g.emptyVao);
        glGenTextures(1, &g.ramps);
        glGenFramebuffers(1, &g.shadowFbo);
    }
    RostrumGpu &g = *_gpu;
    std::map<std::string, float> look = _delegate->LookSettings();
    auto setting = [&](char const *k, float d) { auto it = look.find(k); return it == look.end() ? d : it->second; };
    int ss = std::clamp(int(setting("rostrum:ss", 2)), 1, 4);
    int W = w * ss, H = h * ss;

    GfMatrix4d view = state->GetWorldToViewMatrix(), proj = state->GetProjectionMatrix();
    std::string camera = state->GetCamera() ? state->GetCamera()->GetId().GetString() : "";

    RostrumScene &scene = _delegate->Scene();
    std::lock_guard<std::mutex> lock(scene.lock);
    // bounds of everything lit (cards are not), for the shadow cameras and the ink depth range
    GfRange3d lit;
    for (auto const &[path, m] : scene.meshes) {
        auto mat = scene.materials.find(m.material);
        if (!m.visible || (mat != scene.materials.end() && mat->second.unlit)) continue;
        lit.UnionWith(GfVec3d(m.center) - GfVec3d(m.radius));
        lit.UnionWith(GfVec3d(m.center) + GfVec3d(m.radius));
    }
    GfVec3d centre = lit.IsEmpty() ? GfVec3d(0) : lit.GetMidpoint();
    double radius = lit.IsEmpty() ? 1.0 : lit.GetSize().GetLength() * 0.5;
    double camDist = view.Transform(centre).GetLength();
    float depthNear = float(std::max(camDist - radius, 1e-3)), depthFar = float(camDist + radius);
    RostrumFrameLights L = RostrumPackLights(scene.lights, centre, radius);

    for (auto const &[path, m] : scene.meshes)
        if (g.meshes[path].version != m.version) Upload(g.meshes[path], m);
    auto drawMeshes = [&](GLuint p, bool shadowPass) {
        int index = 0;
        for (auto const &[path, m] : scene.meshes) {
            ++index;
            auto mat = scene.materials.find(m.material);
            bool unlit = mat != scene.materials.end() && mat->second.unlit;
            if (!m.visible || (shadowPass && unlit)) continue;
            MeshUniforms(p, m, camera);
            if (!shadowPass) {
                GfVec3f base = mat != scene.materials.end() ? mat->second.baseColor : m.displayColor;
                GLuint tex = mat != scene.materials.end() && !mat->second.texture.empty()
                           ? RostrumTexture(mat->second.texture) : 0;
                U(p, "u_baseColor", base);
                U(p, "u_hasTex", int(tex != 0));
                U(p, "u_unlit", int(unlit));
                U(p, "u_id", index);
                Bind(0, GL_TEXTURE_2D, tex);
            }
            GpuMesh const &gm = g.meshes[path];
            glBindVertexArray(gm.vao);
            glDrawArrays(GL_TRIANGLES, 0, gm.count);
        }
    };

    glDisable(GL_BLEND); glDisable(GL_SCISSOR_TEST); glDisable(GL_CULL_FACE); glDisable(GL_FRAMEBUFFER_SRGB);

    // 1. shadow maps (one array layer per shadowed light)
    int size = int(setting("rostrum:shadow:size", 4096));
    if (g.shadowSize != size) {
        if (g.shadowTex) glDeleteTextures(1, &g.shadowTex);
        glGenTextures(1, &g.shadowTex);
        glBindTexture(GL_TEXTURE_2D_ARRAY, g.shadowTex);
        glTexStorage3D(GL_TEXTURE_2D_ARRAY, 1, GL_DEPTH_COMPONENT32F, size, size, kMaxShadows);
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_COMPARE_MODE, GL_COMPARE_REF_TO_TEXTURE);
        glTexParameteri(GL_TEXTURE_2D_ARRAY, GL_TEXTURE_COMPARE_FUNC, GL_LEQUAL);
        g.shadowSize = size;
    }
    glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LESS); glDepthMask(GL_TRUE);
    glUseProgram(g.shadow);
    U(g.shadow, "u_camView", view);
    U(g.shadow, "u_camViewInv", view.GetInverse());
    glBindFramebuffer(GL_FRAMEBUFFER, g.shadowFbo);
    glDrawBuffer(GL_NONE);
    glReadBuffer(GL_NONE);
    glViewport(0, 0, size, size);
    for (int s = 0; s < L.shadows; ++s) {
        glFramebufferTextureLayer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, g.shadowTex, 0, s);
        glClear(GL_DEPTH_BUFFER_BIT);
        glUniformMatrix4fv(glGetUniformLocation(g.shadow, "u_viewProj"), 1, GL_FALSE, L.shadowMat[s].data());
        drawMeshes(g.shadow, true);
    }

    // 2. G-buffer: albedo (a = unlit), world normal + view depth, world position, object id
    g.gbuf.Resize(W, H, {GL_RGBA16F, GL_RGBA32F, GL_RGBA32F, GL_R32I}, true);
    glBindFramebuffer(GL_FRAMEBUFFER, g.gbuf.fbo);
    glViewport(0, 0, W, H);
    float zero[4] = {0, 0, 0, 0};
    int none[4] = {0, 0, 0, 0};
    glClearBufferfv(GL_COLOR, 0, zero); glClearBufferfv(GL_COLOR, 1, zero);
    glClearBufferfv(GL_COLOR, 2, zero); glClearBufferiv(GL_COLOR, 3, none);
    glClear(GL_DEPTH_BUFFER_BIT);
    glUseProgram(g.geom);
    U(g.geom, "u_camView", view);
    U(g.geom, "u_camViewInv", view.GetInverse());
    U(g.geom, "u_viewProj", view * proj);
    drawMeshes(g.geom, false);
    glDisable(GL_DEPTH_TEST);

    // shared by the screen passes
    auto screen = [&](GLuint p, RostrumTarget &t) {
        glBindFramebuffer(GL_FRAMEBUFFER, t.fbo);
        glViewport(0, 0, t.w, t.h);
        glUseProgram(p);
        RostrumSetLook(p, look);
        U(p, "u_ss", float(ss));
        U(p, "u_depthNear", depthNear);
        U(p, "u_depthFar", depthFar);
        U(p, "u_camView", view);
    };
    auto draw = [&]() { glBindVertexArray(g.emptyVao); glDrawArrays(GL_TRIANGLES, 0, 3); };

    // 3. shade: per-light "how lit" -> brush strokes -> ramp -> colour (a = how lit overall)
    glBindTexture(GL_TEXTURE_2D, g.ramps);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16F, kRampSize, kMaxLights, 0, GL_RGBA, GL_FLOAT, L.ramps.data());
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    g.shaded.Resize(W, H, {GL_RGBA16F}, false);
    screen(g.shade, g.shaded);
    for (int i = 0; i < 4; ++i) Bind(i, GL_TEXTURE_2D, g.gbuf.color[i]);
    Bind(4, GL_TEXTURE_2D, g.ramps);
    Bind(5, GL_TEXTURE_2D_ARRAY, g.shadowTex);
    Units(g.shade, {{"u_albedo", 0}, {"u_normal", 1}, {"u_world", 2}, {"u_ids", 3},
                        {"u_ramps", 4}, {"u_shadowMaps", 5}});
    U(g.shade, "u_lightCount", L.count);
    glUniform4fv(glGetUniformLocation(g.shade, "u_lightPos"), kMaxLights, L.pos[0].data());
    glUniform4fv(glGetUniformLocation(g.shade, "u_lightAxis"), kMaxLights, L.axis[0].data());
    glUniform4fv(glGetUniformLocation(g.shade, "u_lightColor"), kMaxLights, L.color[0].data());
    glUniform1fv(glGetUniformLocation(g.shade, "u_lightShadow"), kMaxLights, L.shadowLayer);
    glUniformMatrix4fv(glGetUniformLocation(g.shade, "u_shadowMat"), kMaxShadows, GL_FALSE, L.shadowMat[0].data());
    U(g.shade, "u_shadowTexel", 1.0f / float(size));
    draw();

    // 4. ink edges: per-pixel line width where silhouettes and creases are
    g.edged.Resize(W, H, {GL_R16F}, false);
    screen(g.edges, g.edged);
    Bind(0, GL_TEXTURE_2D, g.gbuf.color[1]); Bind(1, GL_TEXTURE_2D, g.gbuf.color[3]);
    Bind(2, GL_TEXTURE_2D, g.shaded.color[0]); Bind(3, GL_TEXTURE_2D, g.gbuf.color[0]);
    Units(g.edges, {{"u_normal", 0}, {"u_ids", 1}, {"u_shaded", 2}, {"u_albedo", 3}});
    draw();

    // 5. ink: lines drawn from the widths, over the shaded frame
    g.inked.Resize(W, H, {GL_RGBA16F}, false);
    screen(g.ink, g.inked);
    Bind(0, GL_TEXTURE_2D, g.shaded.color[0]); Bind(1, GL_TEXTURE_2D, g.edged.color[0]);
    Bind(2, GL_TEXTURE_2D, g.gbuf.color[0]);
    Units(g.ink, {{"u_shaded", 0}, {"u_edges", 1}, {"u_albedo", 2}});
    draw();

    // 6. down to the output size (box filter for 2x) + depth
    g.out.Resize(w, h, {GL_RGBA16F}, true);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, g.inked.fbo);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, g.out.fbo);
    glBlitFramebuffer(0, 0, W, H, 0, 0, w, h, GL_COLOR_BUFFER_BIT, GL_LINEAR);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, g.gbuf.fbo);
    glBlitFramebuffer(0, 0, W, H, 0, 0, w, h, GL_DEPTH_BUFFER_BIT, GL_NEAREST);
    for (int i = 5; i >= 0; --i) Bind(i, i == 5 ? GL_TEXTURE_2D_ARRAY : GL_TEXTURE_2D, 0);
    GLenum err = glGetError();
    if (err != GL_NO_ERROR) throw std::runtime_error("Rostrum Stylized: OpenGL error " + std::to_string(err));
}

PXR_NAMESPACE_CLOSE_SCOPE
