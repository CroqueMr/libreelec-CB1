// SPDX-License-Identifier: GPL-2.0-or-later
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
#include "PascalHDR10Scanout.h"
namespace KODI::WINDOWING::GBM
{
class CDRMPlane;
}

using namespace KODI::WINDOWING::GBM;
constexpr uint32_t DRM_FORMAT_XRGB2101010 = 1, DRM_FORMAT_XBGR2101010 = 2,
    DRM_FORMAT_ABGR2101010 = 3, XR24 = 4;
constexpr uint32_t GBM_BO_USE_SCANOUT = 1, GBM_BO_USE_RENDERING = 2;
struct gbm_device {};
struct gbm_bo { uint32_t format; };
using GLint = int;
using GLuint = unsigned;
constexpr auto GL_TEXTURE_BINDING_2D = 0, GL_TEXTURE_2D = 0, GL_RGB10_A2 = 0;
std::vector<uint32_t> attempts, imports, atomic;
uint32_t failedImport{}, failedAtomic{}, failedProbe{}, failedUpload{};
unsigned liveBuffers{}, boundTexture{};
constexpr int GL_NO_ERROR = 0;
int glError{};
class KODI::WINDOWING::GBM::CDRMPlane
{
public:
  std::vector<uint32_t> formats;
  bool SupportsFormat(uint32_t f) const
  { return std::find(formats.begin(), formats.end(), f) != formats.end(); }
  auto& GetModifiersForFormat(uint32_t f)
  { assert(SupportsFormat(f)); static const std::array<uint64_t,1> modifiers{42}; return modifiers; }
  bool SupportsFormatAndModifier(uint32_t f, uint64_t m)
  { return SupportsFormat(f) && m == 42; }
};
class KODI::WINDOWING::GBM::CDRMAtomic
{
public:
  CDRMPlane plane;
  CDRMPlane* GetGuiPlane() { return &plane; }
  CDRMPlane* GetVideoPlane() { return nullptr; }
  bool TestFramebuffer(gbm_bo* bo)
  { atomic.push_back(bo->format); return bo->format != failedAtomic; }
};
gbm_bo* gbm_bo_create(gbm_device*, int, int, uint32_t f, uint32_t)
{ attempts.push_back(f); ++liveBuffers; return new gbm_bo{f}; }
gbm_bo* gbm_bo_create_with_modifiers2(gbm_device* d, int w, int h, uint32_t f,
                                    const uint64_t* mods, size_t count, uint32_t usage)
{ assert(count == 1 && mods[0] == 42); return gbm_bo_create(d,w,h,f,usage); }
void gbm_bo_destroy(gbm_bo* bo) { --liveBuffers; delete bo; }
uint64_t gbm_bo_get_modifier(gbm_bo*) { return 42; }
int gbm_bo_get_plane_count(gbm_bo*) { return 1; }
int gbm_bo_get_fd(gbm_bo*) { return 10; }
unsigned gbm_bo_get_offset(gbm_bo*, int) { return 0; }
unsigned gbm_bo_get_stride(gbm_bo*) { return 400; }
int close(int) { return 0; }
int eglGetCurrentDisplay() { return 0; }
struct FramebufferBindings {};
struct CEGLImage
{
  explicit CEGLImage(int) {}
  struct EglAttrs {
    int width{}, height{};
    uint32_t format{};
    struct Plane {int fd,offset,stride;uint64_t modifier;};
    std::array<Plane,1> planes{};
  };
  bool CreateImage(const EglAttrs& a)
  {
    assert(a.format == attempts.back() && a.planes[0].modifier == 42);
    imports.push_back(a.format);
    return a.format != failedImport;
  }
  void UploadImage(int) { if (imports.back() == failedUpload) glError = 1; }
  void DestroyImage() {}
};
bool Attach(GLuint&, GLuint) { return glError == GL_NO_ERROR; }
int glGetError() { const int error = glError; glError = GL_NO_ERROR; return error; }
void glGetIntegerv(int,GLint* v) { *v = boundTexture; }
void glGenTextures(int,GLuint* v) { *v = 17; }
void glBindTexture(int,GLuint v) { boundTexture = v; }
void glTexStorage2D(int,int,int,int,int) {}
void glDeleteFramebuffers(int,const GLuint*) {}
void glDeleteTextures(int,const GLuint*) {}
bool CPascalHDR10Scanout::Probe() const { return attempts.back() != failedProbe; }

// PASCAL_SCANOUT_METHODS

int main()
{
  gbm_device dev;
  CDRMAtomic drm;
  const auto XR30 = DRM_FORMAT_XRGB2101010, XB30 = DRM_FORMAT_XBGR2101010,
             AB30 = DRM_FORMAT_ABGR2101010;
  auto exercise = [&](std::vector<uint32_t> formats, bool accepted,
                      std::vector<uint32_t> expected)
  {
    attempts.clear(); imports.clear(); atomic.clear();
    drm.plane.formats = formats;
    boundTexture = 99;
    auto scanout = CPascalHDR10Scanout::Create(&dev, drm, 100, 50);
    if (bool(scanout) != accepted || attempts != expected)
    {
      std::cerr << "Format negotiation failed. Advertised ";
      for (auto f : formats) std::cerr << f << ' ';
      std::cerr << " expected buffer attempts ";
      for (auto f : expected) std::cerr << f << ' ';
      std::cerr << " observed ";
      for (auto f : attempts) std::cerr << f << ' ';
      std::cerr << '\n';
      return false;
    }
    assert(boundTexture == 99 && imports == attempts);
    if (scanout) assert(atomic.size() >= 2 && atomic.back() == attempts.back());
    scanout.reset();
    assert(liveBuffers == 0);
    return true;
  };
  if (!exercise({XB30, AB30, XR24}, true, {XB30, XB30})) return 1;
  failedImport = XB30;
  if (!exercise({XB30, AB30}, true, {XB30, AB30, AB30})) return 1;
  failedImport = 0;
  failedUpload = XB30;
  if (!exercise({XB30, AB30}, true, {XB30, AB30, AB30})) return 1;
  failedUpload = 0;
  failedAtomic = XB30;
  if (!exercise({XB30, AB30}, true, {XB30, AB30, AB30})) return 1;
  failedAtomic = 0;
  failedProbe = XB30;
  if (!exercise({XB30, AB30}, true, {XB30, XB30, AB30, AB30})) return 1;
  failedProbe = 0;
  if (!exercise({XR24}, false, {})) return 1;
  if (!exercise({XR30, XB30}, true, {XR30, XR30})) return 1;
}
