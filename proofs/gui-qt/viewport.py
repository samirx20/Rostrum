"""The live GPU viewport: a QQuickFramebufferObject whose renderer draws raw OpenGL on Qt's own GL context.

This is the slot a Hydra engine would take (README › Hydra plug-in plan): Qt binds the item's FBO, calls
`render()` on the scene-graph render thread, and composites the result with the rest of the QML screen.
The test scene: a soft gradient background and a lit, slowly turning torus knot.
"""
import ctypes
import math

import numpy as np
from OpenGL import GL
from PySide6.QtCore import Property, Signal
from PySide6.QtGui import QColor
from PySide6.QtQuick import QQuickFramebufferObject, QQuickOpenGLUtils

BG_VS = """#version 330 core
out vec2 uv;
void main() { vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2); uv = p; gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0); }"""
BG_FS = """#version 330 core
in vec2 uv; out vec4 col; uniform vec2 aspect;
void main() {
  vec3 top = vec3(0.105, 0.110, 0.125), bottom = vec3(0.045, 0.047, 0.055);
  vec3 c = mix(bottom, top, smoothstep(0.0, 1.0, uv.y));
  vec2 d = (uv - vec2(0.5, 0.45)) * aspect; c += vec3(0.05, 0.06, 0.08) * exp(-dot(d, d) * 3.0);
  c += (fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453) - 0.5) / 255.0;  // dither: no banding
  col = vec4(c, 1.0);
}"""
MESH_VS = """#version 330 core
layout(location = 0) in vec3 pos; layout(location = 1) in vec3 nrm;
uniform mat4 model, viewProj; out vec3 n; out vec3 wp;
void main() { vec4 w = model * vec4(pos, 1.0); wp = w.xyz; n = mat3(model) * nrm; gl_Position = viewProj * w; }"""
MESH_FS = """#version 330 core
in vec3 n; in vec3 wp; out vec4 col; uniform vec3 tint; uniform vec3 eye;
void main() {
  vec3 N = normalize(n), V = normalize(eye - wp);
  vec3 key = normalize(vec3(-0.5, 0.8, 0.6)), fill = normalize(vec3(0.7, -0.2, 0.4));
  float d = max(dot(N, key), 0.0), f = max(dot(N, fill), 0.0) * 0.25;
  float s = pow(max(dot(N, normalize(key + V)), 0.0), 64.0) * 0.6;
  float rim = pow(1.0 - max(dot(N, V), 0.0), 3.0) * 0.35;
  vec3 c = tint * (0.08 + d * 0.85 + f) + vec3(s) + vec3(0.55, 0.65, 0.85) * rim;
  col = vec4(pow(c, vec3(1.0 / 2.2)), 1.0);
}"""


def torus_knot(p=2, q=3, n=720, m=40, r=0.32):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    def curve(t):
        k = 2 + np.cos(q * t)
        return np.stack([k * np.cos(p * t), k * np.sin(p * t), -np.sin(q * t)], 1) * 0.42
    c, dt = curve(t), 1e-3
    tan = curve(t + dt) - curve(t - dt); tan /= np.linalg.norm(tan, axis=1, keepdims=True)
    acc = curve(t + dt) - 2 * c + curve(t - dt)
    nor = acc - (acc * tan).sum(1, keepdims=True) * tan; nor /= np.linalg.norm(nor, axis=1, keepdims=True)
    bin_ = np.cross(tan, nor)
    a = np.linspace(0, 2 * np.pi, m, endpoint=False)
    ring = np.cos(a)[None, :, None] * nor[:, None] + np.sin(a)[None, :, None] * bin_[:, None]
    verts = np.concatenate([(c[:, None] + r * 0.42 * ring).reshape(-1, 3), ring.reshape(-1, 3)], 1)
    i, j = np.meshgrid(np.arange(n), np.arange(m), indexing="ij")
    a0, a1 = i * m + j, ((i + 1) % n) * m + j
    b0, b1 = i * m + (j + 1) % m, ((i + 1) % n) * m + (j + 1) % m
    idx = np.stack([a0, a1, b0, b0, a1, b1], -1).reshape(-1)
    return verts.astype(np.float32), idx.astype(np.uint32)


def perspective(fov, aspect, near, far):
    f = 1 / math.tan(fov / 2)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)], [0, 0, -1, 0]], np.float32)


def rotation(ax, ay):
    cx, sx, cy, sy = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay)
    rx = np.array([[1, 0, 0, 0], [0, cx, -sx, 0], [0, sx, cx, 0], [0, 0, 0, 1]], np.float32)
    ry = np.array([[cy, 0, sy, 0], [0, 1, 0, 0], [-sy, 0, cy, 0], [0, 0, 0, 1]], np.float32)
    return ry @ rx


def program(vs, fs):
    from OpenGL.GL import shaders
    return shaders.compileProgram(shaders.compileShader(vs, GL.GL_VERTEX_SHADER),
                                  shaders.compileShader(fs, GL.GL_FRAGMENT_SHADER), validate=False)


class SceneRenderer(QQuickFramebufferObject.Renderer):
    def __init__(self):
        super().__init__()
        self.ready, self.time, self.tint, self.info = False, 0.0, (0.8, 0.8, 0.8), {}

    # Qt's default FBO (colour only) is the target. We draw into our own 4x MSAA colour + depth buffer and resolve
    # into it with a blit. (Overriding createFramebufferObject from Python double-frees the FBO in PySide 6.12.)
    def _offscreen(self, w, h):
        if getattr(self, "size", None) == (w, h):
            return
        if getattr(self, "fb", None):
            GL.glDeleteFramebuffers(1, [self.fb]); GL.glDeleteRenderbuffers(2, self.rbs)
        self.fb, self.rbs, self.size = GL.glGenFramebuffers(1), GL.glGenRenderbuffers(2), (w, h)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fb)
        for rb, fmt, att in zip(self.rbs, (GL.GL_RGBA8, GL.GL_DEPTH24_STENCIL8),
                                (GL.GL_COLOR_ATTACHMENT0, GL.GL_DEPTH_STENCIL_ATTACHMENT)):
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, rb)
            GL.glRenderbufferStorageMultisample(GL.GL_RENDERBUFFER, 4, fmt, w, h)
            GL.glFramebufferRenderbuffer(GL.GL_FRAMEBUFFER, att, GL.GL_RENDERBUFFER, rb)
        if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("viewport offscreen framebuffer incomplete")

    def synchronize(self, item):  # GUI thread is blocked here: copy state across safely
        self.time = item.time
        self.tint = (item.tint.redF(), item.tint.greenF(), item.tint.blueF())
        item.glInfo = self.info

    def _init(self):
        self.bg, self.mesh = program(BG_VS, BG_FS), program(MESH_VS, MESH_FS)
        verts, idx = torus_knot()
        self.count = idx.size
        self.empty_vao, self.vao = GL.glGenVertexArrays(2)
        GL.glBindVertexArray(self.vao)
        vbo, ibo = GL.glGenBuffers(2)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo); GL.glBufferData(GL.GL_ARRAY_BUFFER, verts.nbytes, verts, GL.GL_STATIC_DRAW)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, ibo); GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, idx.nbytes, idx, GL.GL_STATIC_DRAW)
        for loc, off in ((0, 0), (1, 12)):
            GL.glEnableVertexAttribArray(loc)
            GL.glVertexAttribPointer(loc, 3, GL.GL_FLOAT, False, 24, ctypes.c_void_p(off))
        GL.glBindVertexArray(0)
        self.info = {"vendor": GL.glGetString(GL.GL_VENDOR).decode(), "renderer": GL.glGetString(GL.GL_RENDERER).decode(),
                     "version": GL.glGetString(GL.GL_VERSION).decode(), "triangles": int(self.count // 3)}
        self.ready = True

    def render(self):
        if not self.ready:
            self._init()
        fbo = self.framebufferObject()
        w, h = fbo.width(), fbo.height()
        self._offscreen(w, h)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.fb)
        GL.glViewport(0, 0, w, h)
        GL.glDisable(GL.GL_BLEND); GL.glDisable(GL.GL_DEPTH_TEST); GL.glDisable(GL.GL_CULL_FACE)
        GL.glUseProgram(self.bg)
        GL.glUniform2f(GL.glGetUniformLocation(self.bg, "aspect"), w / max(h, 1), 1.0)
        GL.glBindVertexArray(self.empty_vao); GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        GL.glClear(GL.GL_DEPTH_BUFFER_BIT); GL.glEnable(GL.GL_DEPTH_TEST); GL.glDepthFunc(GL.GL_LESS)
        eye = np.array([0, 0, 4.6], np.float32)
        view = np.eye(4, dtype=np.float32); view[2, 3] = -eye[2]
        vp = perspective(math.radians(38), w / max(h, 1), 0.1, 50) @ view
        model = rotation(0.35 + 0.25 * math.sin(self.time * 0.4), self.time * 0.6)
        GL.glUseProgram(self.mesh)
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self.mesh, "model"), 1, True, model)
        GL.glUniformMatrix4fv(GL.glGetUniformLocation(self.mesh, "viewProj"), 1, True, vp)
        GL.glUniform3f(GL.glGetUniformLocation(self.mesh, "tint"), *self.tint)
        GL.glUniform3f(GL.glGetUniformLocation(self.mesh, "eye"), *eye)
        GL.glBindVertexArray(self.vao)
        GL.glDrawElements(GL.GL_TRIANGLES, self.count, GL.GL_UNSIGNED_INT, None)
        GL.glBindVertexArray(0); GL.glUseProgram(0)
        GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, self.fb)
        GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, fbo.handle())
        GL.glBlitFramebuffer(0, 0, w, h, 0, 0, w, h, GL.GL_COLOR_BUFFER_BIT, GL.GL_NEAREST)  # MSAA resolve
        QQuickOpenGLUtils.resetOpenGLState()  # hand Qt back a clean GL state


class GLViewport(QQuickFramebufferObject):
    timeChanged, tintChanged = Signal(), Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._time, self._tint, self.glInfo = 0.0, QColor("#c9ccd4"), {}
        self.setMirrorVertically(True)  # GL's origin is bottom-left

    def createRenderer(self):
        self._renderer = SceneRenderer()  # keep the Python wrapper alive; Qt owns and deletes the C++ side
        return self._renderer

    def _get_time(self): return self._time
    def _set_time(self, v):
        if v != self._time:
            self._time = v; self.timeChanged.emit(); self.update()
    time = Property(float, _get_time, _set_time, notify=timeChanged)

    def _get_tint(self): return self._tint
    def _set_tint(self, v):
        if v != self._tint:
            self._tint = QColor(v); self.tintChanged.emit(); self.update()
    tint = Property(QColor, _get_tint, _set_tint, notify=tintChanged)
