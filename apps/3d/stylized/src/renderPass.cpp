// The stylized render pass (see renderPass.h). Renders at `rostrum:ss` x the output size
// (supersampling, default 2; the core sends 1 for the viewport) and box-filters down; writes the
// colour and depth AOVs. GL objects are made once and kept: render targets are re-made only when
// the size changes, the material table when the materials change; the shadow maps are redrawn
// only when the lights, the meshes or (with a bend) the camera do.
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

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>

PXR_NAMESPACE_OPEN_SCOPE

struct GpuMesh {
    GLuint vao = 0, vbo = 0;
    GLsizei count = 0;
    unsigned version = 0;
};

// what the shadow maps were drawn from (redrawn when any of it changes)
struct ShadowKey {
    unsigned lights = ~0u;
    size_t meshes = 0;
    unsigned long long meshSum = 0;   // each mesh's version and whether it casts (not a glowing card)
    std::string camera;            // with a bend: the camera and where it looks from
    GfMatrix4d view{1.0};
    int size = 0;
    bool operator==(ShadowKey const &o) const
    {
        return lights == o.lights && meshes == o.meshes && meshSum == o.meshSum &&
               camera == o.camera && view == o.view && size == o.size;
    }
};

// The material table (u_mats, RGBA32F, kMatTexels wide, one row per material; row 0 = no material:
// plain). Texels: 0 emission, unlit | 1 lit colour, shadowBelow | 2 mid colour, litFrom |
// 3 shadow colour, lightSoftness | 4 lightToColor, lightSmooth, halftone (1 dots, 2 lines),
// halftoneAngle | 5 halftone colour, halftoneSize | 6 lines, width, taper, wobble |
// 7 lines colour, crease angle
constexpr int kMatTexels = 8;

struct RostrumGpu {
    std::string dir;
    GLuint geom = 0, shadow = 0, shade = 0, edges = 0, ink = 0, emptyVao = 0, ramps = 0, mats = 0;
    GLuint shadowTex = 0, shadowFbo = 0;
    int shadowSize = 0;
    ShadowKey shadowKey;
    unsigned materialsVersion = ~0u;
    std::map<SdfPath, int> matRow;
    float widestLine = 0;         // the widest material line with its wobble, output pixels
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

void Put(float *t, GfVec3f const &c, float w) { t[0] = c[0]; t[1] = c[1]; t[2] = c[2]; t[3] = w; }

// the material table (see kMatTexels); fills each material's row and the widest line
std::vector<float> MaterialTable(std::map<SdfPath, RostrumMaterialData> const &materials,
                                 std::map<SdfPath, int> *rows, float *widest)
{
    std::vector<float> t(size_t(materials.size() + 1) * kMatTexels * 4, 0.0f);
    rows->clear();
    *widest = 0;
    int r = 0;
    for (auto const &[path, m] : materials) {
        (*rows)[path] = ++r;
        float *row = &t[size_t(r) * kMatTexels * 4];
        float below = std::clamp(m.shadowBelow, 0.0f, 1.0f), from = std::clamp(m.litFrom, 0.0f, 1.0f);
        if (below > from) below = from;  // contract: the engine uses litFrom for both
        Put(row + 0, m.emission, m.unlit ? 1.0f : 0.0f);
        Put(row + 4, m.litColor, below);
        Put(row + 8, m.midColor, from);
        Put(row + 12, m.shadowColor, std::clamp(m.lightSoftness, 0.01f, 0.5f));
        row[16] = m.lightToColor ? 1.0f : 0.0f;
        row[17] = m.lightSmooth ? 1.0f : 0.0f;
        row[18] = m.halftone ? (m.halftoneLines ? 2.0f : 1.0f) : 0.0f;
        row[19] = m.halftoneAngle;
        Put(row + 20, m.halftoneColor, std::clamp(m.halftoneSize, 1.0f, 200.0f));
        bool lines = m.lines && !m.unlit;
        row[24] = lines ? 1.0f : 0.0f;
        row[25] = std::max(m.linesWidth, 0.0f);
        row[26] = std::clamp(m.linesTaper, 0.0f, 1.0f);
        row[27] = std::clamp(m.linesWobble, 0.0f, 1.0f);
        Put(row + 28, m.linesColor, std::clamp(m.linesCreaseAngle, 1.0f, 180.0f));
        if (lines) *widest = std::max(*widest, row[25] * (1.0f + row[27] * 1.6f));
    }
    return t;
}

// ROSTRUM_DEBUG: one line per frame with what each pass cost (it waits for the GPU after each
// pass, so the frame is a little slower with it on)
struct PassClock {
    bool on = TfGetenvBool("ROSTRUM_DEBUG", false);
    std::chrono::steady_clock::time_point last = std::chrono::steady_clock::now();
    std::string line;
    void Mark(char const *pass)
    {
        if (!on) return;
        glFinish();
        auto now = std::chrono::steady_clock::now();
        char buf[64];
        snprintf(buf, sizeof(buf), " %s %.2f", pass, std::chrono::duration<double, std::milli>(now - last).count());
        line += buf;
        last = now;
    }
};

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
    bool debug = TfGetenvBool("ROSTRUM_DEBUG", false);
    auto t0 = std::chrono::steady_clock::now();
    try {
        _Draw(state, w, h);
        // The colour goes back through CPU memory: the host (HdxAovInputTask, the core's AOV
        // reads) uploads it again. Handing it a GPU texture instead (HdRenderBuffer::GetResource
        // -> HgiTextureHandle) can't be checked from the headers alone; see LOOKS.md "Speed".
        glBindFramebuffer(GL_READ_FRAMEBUFFER, _gpu->out.fbo);
        glReadBuffer(GL_COLOR_ATTACHMENT0);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        HdFormat f = color->GetFormat();
        GLenum type = f == HdFormatFloat16Vec4 ? GL_HALF_FLOAT : f == HdFormatFloat32Vec4 ? GL_FLOAT
                    : f == HdFormatUNorm8Vec4 ? GL_UNSIGNED_BYTE : 0;
        if (!type) throw std::runtime_error("Rostrum Stylized: unsupported colour AOV format");
        void *px = color->Map();
        glReadPixels(0, 0, w, h, GL_RGBA, type, px);
        if (debug && type == GL_FLOAT) {
            float const *c = static_cast<float const *>(px) + (size_t(h / 2) * w + w / 2) * 4;
            printf("[rostrum] centre pixel %.3f %.3f %.3f %.3f\n", c[0], c[1], c[2], c[3]);
        }
        color->Unmap();
        if (depth && depth->GetFormat() == HdFormatFloat32 && int(depth->GetWidth()) == w &&
            int(depth->GetHeight()) == h) {
            glReadPixels(0, 0, w, h, GL_DEPTH_COMPONENT, GL_FLOAT, depth->Map());
            depth->Unmap();
        }
        if (debug) {
            auto ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
            printf("[rostrum] frame %dx%d (colour AOV format %d): %.1f ms with the read-back\n", w, h, int(f), ms);
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
        glBindTexture(GL_TEXTURE_2D, g.ramps);
        glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA16F, kRampSize, kMaxLights);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
        glGenTextures(1, &g.mats);
        glBindTexture(GL_TEXTURE_2D, g.mats);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAX_LEVEL, 0);
        glGenFramebuffers(1, &g.shadowFbo);
    }
    RostrumGpu &g = *_gpu;
    PassClock clock;
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
    ShadowKey key;
    key.lights = scene.lightsVersion;
    bool bent = false;
    for (auto const &[path, m] : scene.meshes) {
        auto mat = scene.materials.find(m.material);
        bool card = mat != scene.materials.end() && mat->second.unlit;
        key.meshSum = key.meshSum * 1000003ull + m.version * 2ull + (card ? 1 : 0);
        ++key.meshes;
        bent = bent || (!m.bend.camera.empty() && m.bend.camera == camera);
        if (!m.visible || card) continue;
        lit.UnionWith(GfVec3d(m.center) - GfVec3d(m.radius));
        lit.UnionWith(GfVec3d(m.center) + GfVec3d(m.radius));
    }
    if (bent) { key.camera = camera; key.view = view; }  // a bend follows the camera, and so do its shadows
    GfVec3d centre = lit.IsEmpty() ? GfVec3d(0) : lit.GetMidpoint();
    double radius = lit.IsEmpty() ? 1.0 : lit.GetSize().GetLength() * 0.5;
    double camDist = view.Transform(centre).GetLength();
    float depthNear = float(std::max(camDist - radius, 1e-3)), depthFar = float(camDist + radius);
    RostrumFrameLights L = RostrumPackLights(scene.lights, centre, radius);
    if (L.legacy) {  // legacy ramp lights only (32 KB)
        glBindTexture(GL_TEXTURE_2D, g.ramps);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, kRampSize, kMaxLights, GL_RGBA, GL_FLOAT, L.ramps.data());
    }
    if (g.materialsVersion != scene.materialsVersion) {
        std::vector<float> table = MaterialTable(scene.materials, &g.matRow, &g.widestLine);
        glBindTexture(GL_TEXTURE_2D, g.mats);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA32F, kMatTexels, GLsizei(scene.materials.size() + 1), 0, GL_RGBA,
                     GL_FLOAT, table.data());
        g.materialsVersion = scene.materialsVersion;
    }

    for (auto const &[path, m] : scene.meshes)
        if (g.meshes[path].version != m.version) Upload(g.meshes[path], m);
    auto drawMeshes = [&](GLuint p, bool shadowPass) {
        int index = 0;
        for (auto const &[path, m] : scene.meshes) {
            ++index;
            auto mat = scene.materials.find(m.material);
            bool found = mat != scene.materials.end();
            bool unlit = found && mat->second.unlit;
            if (!m.visible || (shadowPass && unlit)) continue;
            MeshUniforms(p, m, camera);
            if (!shadowPass) {
                GfVec3f base = found ? mat->second.baseColor : m.displayColor;
                GLuint tex = found && !mat->second.texture.empty() ? RostrumTexture(mat->second.texture) : 0;
                auto row = g.matRow.find(m.material);
                U(p, "u_baseColor", base);
                U(p, "u_hasTex", int(tex != 0));
                U(p, "u_unlit", int(unlit));
                U(p, "u_id", index);
                U(p, "u_mat", row == g.matRow.end() ? 0 : row->second);
                Bind(0, GL_TEXTURE_2D, tex);
            }
            GpuMesh const &gm = g.meshes[path];
            glBindVertexArray(gm.vao);
            glDrawArrays(GL_TRIANGLES, 0, gm.count);
        }
    };
    clock.Mark("prep");

    glDisable(GL_BLEND); glDisable(GL_SCISSOR_TEST); glDisable(GL_CULL_FACE); glDisable(GL_FRAMEBUFFER_SRGB);

    // 1. shadow maps (one array layer per shadowed light), redrawn only when what they show changed
    int size = std::clamp(int(setting("rostrum:shadow:size", 2048)), 256, 8192);
    key.size = size;
    if (L.shadows > 0 && g.shadowSize != size) {
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
        g.shadowKey = ShadowKey();  // new maps: draw them
    }
    glEnable(GL_DEPTH_TEST); glDepthFunc(GL_LESS); glDepthMask(GL_TRUE);
    if (L.shadows > 0 && !(g.shadowKey == key)) {
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
        g.shadowKey = key;
    }
    clock.Mark("shadows");

    // 2. G-buffer: albedo (a = unlit), world normal + view depth, world position, object id + material row
    g.gbuf.Resize(W, H, {GL_RGBA16F, GL_RGBA16F, GL_RGBA32F, GL_RG32I}, true);
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
    clock.Mark("gbuffer");

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

    // 3. shade: light per pixel -> the material's plain / light to colour / halftone (a = how lit)
    g.shaded.Resize(W, H, {GL_RGBA16F}, false);
    screen(g.shade, g.shaded);
    for (int i = 0; i < 4; ++i) Bind(i, GL_TEXTURE_2D, g.gbuf.color[i]);
    Bind(4, GL_TEXTURE_2D, g.ramps);
    Bind(5, GL_TEXTURE_2D_ARRAY, g.shadowTex);
    Bind(6, GL_TEXTURE_2D, g.mats);
    Units(g.shade, {{"u_albedo", 0}, {"u_normal", 1}, {"u_world", 2}, {"u_ids", 3},
                    {"u_ramps", 4}, {"u_shadowMaps", 5}, {"u_mats", 6}});
    U(g.shade, "u_lightCount", L.count);
    glUniform4fv(glGetUniformLocation(g.shade, "u_lightPos"), kMaxLights, L.pos[0].data());
    glUniform4fv(glGetUniformLocation(g.shade, "u_lightAxis"), kMaxLights, L.axis[0].data());
    glUniform4fv(glGetUniformLocation(g.shade, "u_lightColor"), kMaxLights, L.color[0].data());
    glUniform4fv(glGetUniformLocation(g.shade, "u_lightExtra"), kMaxLights, L.extra[0].data());
    glUniformMatrix4fv(glGetUniformLocation(g.shade, "u_shadowMat"), kMaxShadows, GL_FALSE, L.shadowMat[0].data());
    U(g.shade, "u_shadowTexel", 1.0f / float(size));
    U(g.shade, "u_shadowAuto", float(8.0 * 2.0 * radius / double(size)));
    // where nothing is drawn: the scene's dome when the camera sees it (as Storm and Cycles show it: its colour x
    // intensity; a dome picture as its average), else rostrum:bg:color
    VtValue seen = _delegate->GetRenderSetting(HdRenderSettingsTokens->domeLightCameraVisibility);
    if (!seen.IsHolding<bool>() || seen.UncheckedGet<bool>()) {
        float best = -1.0f;
        GfVec3f sky(0.0f);
        for (auto const &[path, l] : scene.lights) {
            if (l.type != HdPrimTypeTokens->domeLight || !l.enabled) continue;
            GfVec3f c = GfCompMult(l.color, (l.domeUp + l.domeDown) * 0.5f) * l.intensity;
            float y = 0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2];
            if (y > best) { best = y; sky = c; }
        }
        if (best >= 0.0f) {
            U(g.shade, "u_bg_color_x", sky[0]);
            U(g.shade, "u_bg_color_y", sky[1]);
            U(g.shade, "u_bg_color_z", sky[2]);
        }
    }
    draw();
    clock.Mark("shade");

    // 4. ink edges: per-pixel line width where a material with Lines (or the frame-wide ink) asks;
    // skipped when nothing has lines
    float frameInk = setting("rostrum:ink:width", 0.0f);
    float frameWidest = frameInk > 0 ? frameInk * (1.0f + setting("rostrum:ink:wobble", 0.4f) * 1.6f) : 0.0f;
    float widest = std::max(g.widestLine, frameWidest);
    int inkRadius = widest > 0 ? std::clamp(int(std::ceil(widest * ss * 0.5f + 1.0f)), 1, 32) : 0;
    if (inkRadius > 0) {
        g.edged.Resize(W, H, {GL_R16F}, false);
        screen(g.edges, g.edged);
        Bind(0, GL_TEXTURE_2D, g.gbuf.color[1]); Bind(1, GL_TEXTURE_2D, g.gbuf.color[3]);
        Bind(2, GL_TEXTURE_2D, g.shaded.color[0]); Bind(3, GL_TEXTURE_2D, g.gbuf.color[0]);
        Bind(4, GL_TEXTURE_2D, g.mats);
        Units(g.edges, {{"u_normal", 0}, {"u_ids", 1}, {"u_shaded", 2}, {"u_albedo", 3}, {"u_mats", 4}});
        draw();
    }
    clock.Mark("edges");

    // 5. ink: lines drawn from the widths over the shaded frame (+ paper grain); at 1x straight
    // into the output, else into the big frame that is then filtered down
    g.out.Resize(w, h, {GL_RGBA16F}, true);
    if (ss > 1) g.inked.Resize(W, H, {GL_RGBA16F}, false);
    else g.inked.Release();
    screen(g.ink, ss > 1 ? g.inked : g.out);
    Bind(0, GL_TEXTURE_2D, g.shaded.color[0]);
    Bind(1, GL_TEXTURE_2D, inkRadius > 0 ? g.edged.color[0] : 0);
    Bind(2, GL_TEXTURE_2D, g.gbuf.color[0]); Bind(3, GL_TEXTURE_2D, g.mats);
    Bind(4, GL_TEXTURE_2D, g.gbuf.color[3]);
    Units(g.ink, {{"u_shaded", 0}, {"u_edges", 1}, {"u_albedo", 2}, {"u_mats", 3}, {"u_ids", 4}});
    U(g.ink, "u_inkRadius", inkRadius);
    draw();
    clock.Mark("ink");

    // 6. down to the output size (box filter for 2x) + depth
    if (ss > 1) {
        glBindFramebuffer(GL_READ_FRAMEBUFFER, g.inked.fbo);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, g.out.fbo);
        glBlitFramebuffer(0, 0, W, H, 0, 0, w, h, GL_COLOR_BUFFER_BIT, GL_LINEAR);
    }
    glBindFramebuffer(GL_READ_FRAMEBUFFER, g.gbuf.fbo);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER, g.out.fbo);
    glBlitFramebuffer(0, 0, W, H, 0, 0, w, h, GL_DEPTH_BUFFER_BIT, GL_NEAREST);
    for (int i = 6; i >= 0; --i) Bind(i, i == 5 ? GL_TEXTURE_2D_ARRAY : GL_TEXTURE_2D, 0);
    clock.Mark("down");
    if (clock.on)
        printf("[rostrum] passes ms (%dx%d ss %d, %d lights, %d shadowed):%s\n", w, h, ss, L.count, L.shadows,
               clock.line.c_str());
    GLenum err = glGetError();
    if (err != GL_NO_ERROR) throw std::runtime_error("Rostrum Stylized: OpenGL error " + std::to_string(err));
}

PXR_NAMESPACE_CLOSE_SCOPE
