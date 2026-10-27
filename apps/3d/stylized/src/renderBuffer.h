// P-3D-3: a CPU-memory render buffer (AOV) the render pass fills after reading the GPU frame back.
#pragma once

#include <pxr/imaging/hd/renderBuffer.h>

#include <vector>

PXR_NAMESPACE_OPEN_SCOPE

class HdRostrumRenderBuffer final : public HdRenderBuffer {
public:
    explicit HdRostrumRenderBuffer(SdfPath const &id) : HdRenderBuffer(id) {}

    bool Allocate(GfVec3i const &dims, HdFormat format, bool multiSampled) override
    {
        _w = dims[0]; _h = dims[1]; _format = format;
        _data.assign(size_t(_w) * _h * HdDataSizeOfFormat(format), 0);
        return true;
    }
    unsigned int GetWidth() const override { return _w; }
    unsigned int GetHeight() const override { return _h; }
    unsigned int GetDepth() const override { return 1; }
    HdFormat GetFormat() const override { return _format; }
    bool IsMultiSampled() const override { return false; }
    void *Map() override { ++_mappers; return _data.data(); }
    void Unmap() override { --_mappers; }
    bool IsMapped() const override { return _mappers > 0; }
    void Resolve() override {}
    bool IsConverged() const override { return _converged; }
    void SetConverged(bool c) { _converged = c; }

private:
    void _Deallocate() override { _data.clear(); _w = _h = 0; }
    unsigned _w = 0, _h = 0;
    HdFormat _format = HdFormatInvalid;
    std::vector<unsigned char> _data;
    int _mappers = 0;
    bool _converged = false;
};

PXR_NAMESPACE_CLOSE_SCOPE
