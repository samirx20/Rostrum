// P-3D-3: small OpenGL helpers: shader programs from files, image textures, render targets.
#pragma once

#include <epoxy/gl.h>
#include <pxr/pxr.h>

#include <map>
#include <string>
#include <vector>

PXR_NAMESPACE_OPEN_SCOPE

// Builds a program from <dir>/<vert> + <dir>/<frag>; "#include <file>" lines are expanded.
// Throws std::runtime_error with the compiler log on failure.
GLuint RostrumProgram(std::string const &dir, char const *vert, char const *frag);

// Every look setting "rostrum:a:b" goes to uniform "u_a_b" if the program has one.
void RostrumSetLook(GLuint prog, std::map<std::string, float> const &look);

// An sRGB image as a mip-mapped texture (cached by path); 0 when it cannot be read.
GLuint RostrumTexture(std::string const &path);

// A dome's lat-long picture (float / half, linear) as it is, for the sky behind the scene (cached by path); 0 when
// it cannot be read.
GLuint RostrumSkyTexture(std::string const &path);

// A framebuffer with colour attachments of the given internal formats (+ optional depth).
struct RostrumTarget {
    GLuint fbo = 0, depth = 0;
    std::vector<GLuint> color;
    int w = 0, h = 0;
    void Resize(int w, int h, std::vector<GLenum> const &formats, bool withDepth);
    void Release();
};

PXR_NAMESPACE_CLOSE_SCOPE
