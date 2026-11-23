"""Check that GBM consumes each EGL KMS sync handle at most once."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE, body


class EglFenceLifetime(unittest.TestCase):
    def test_cpu_wait_consumes_a_fence_and_leaves_the_empty_slot_safe(self):
        method = body((TREE / "xbmc/utils/EGLFence.cpp").read_text(),
                      "void CEGLFence::WaitSyncCPU()")
        code = r'''
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>

#include <cassert>
#include <cstdio>

struct CEGLFence
{
  EGLDisplay m_display;
  EGLSyncKHR m_kmsFence;
  PFNEGLCLIENTWAITSYNCKHRPROC m_eglClientWaitSyncKHR;
  PFNEGLDESTROYSYNCKHRPROC m_eglDestroySyncKHR;
  void WaitSyncCPU() BODY
};

static int destroys = 0;
static PFNEGLDESTROYSYNCKHRPROC destroyReal;

static EGLBoolean EGLAPIENTRY Destroy(EGLDisplay display, EGLSyncKHR sync)
{
  ++destroys;
  return destroyReal(display, sync);
}

static EGLint EGLAPIENTRY FailWait(EGLDisplay, EGLSyncKHR, EGLint, EGLTimeKHR)
{
  return EGL_FALSE;
}

int main()
{
  auto display = eglGetDisplay(EGL_DEFAULT_DISPLAY);
  assert(display != EGL_NO_DISPLAY && eglInitialize(display, nullptr, nullptr));
  assert(eglBindAPI(EGL_OPENGL_ES_API));
  const EGLint attributes[]{EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
                           EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT, EGL_NONE};
  EGLConfig config;
  EGLint count;
  assert(eglChooseConfig(display, attributes, &config, 1, &count) && count == 1);
  const EGLint contextAttrs[]{EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE};
  const EGLint surfaceAttrs[]{EGL_WIDTH, 1, EGL_HEIGHT, 1, EGL_NONE};
  auto context = eglCreateContext(display, config, EGL_NO_CONTEXT, contextAttrs);
  auto surface = eglCreatePbufferSurface(display, config, surfaceAttrs);
  assert(eglMakeCurrent(display, surface, surface, context));

  auto create = reinterpret_cast<PFNEGLCREATESYNCKHRPROC>(eglGetProcAddress("eglCreateSyncKHR"));
  destroyReal = reinterpret_cast<PFNEGLDESTROYSYNCKHRPROC>(eglGetProcAddress("eglDestroySyncKHR"));
  auto wait = reinterpret_cast<PFNEGLCLIENTWAITSYNCKHRPROC>(eglGetProcAddress("eglClientWaitSyncKHR"));
  assert(create && destroyReal && wait);

  CEGLFence fence{display, EGL_NO_SYNC_KHR, wait, Destroy};
  fence.WaitSyncCPU();
  assert(eglGetError() == EGL_SUCCESS && destroys == 0);

  fence.m_kmsFence = create(display, EGL_SYNC_FENCE_KHR, nullptr);
  assert(fence.m_kmsFence != EGL_NO_SYNC_KHR);
  glFlush();
  fence.WaitSyncCPU();
  auto first = eglGetError();

  // A presentation without a new out-fence must leave the slot empty.
  fence.WaitSyncCPU();
  auto empty = eglGetError();
  std::fprintf(stderr, "first wait=%#x, no new fence=%#x\n", first, empty);
  assert(first == EGL_SUCCESS && empty == EGL_SUCCESS && destroys == 1);

  auto fresh = create(display, EGL_SYNC_FENCE_KHR, nullptr);
  assert(fresh != EGL_NO_SYNC_KHR);
  glFlush();
  fence.m_kmsFence = fresh;
  fence.m_eglClientWaitSyncKHR = FailWait;
  fence.WaitSyncCPU();
  assert(fence.m_kmsFence == fresh && destroys == 1);
  fence.m_eglClientWaitSyncKHR = wait;
  fence.WaitSyncCPU();
  assert(eglGetError() == EGL_SUCCESS && fence.m_kmsFence == EGL_NO_SYNC_KHR && destroys == 2);

  eglMakeCurrent(display, EGL_NO_SURFACE, EGL_NO_SURFACE, EGL_NO_CONTEXT);
  eglDestroySurface(display, surface);
  eglDestroyContext(display, context);
  eglTerminate(display);
}
'''.replace("BODY", method)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fence.cpp"
            binary = source.with_suffix("")
            source.write_text(code)
            subprocess.run(["c++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(source), "-o", str(binary), "-lEGL", "-lGLESv2"], check=True)
            result = subprocess.run([binary], capture_output=True, text=True, timeout=15,
                                    env=dict(os.environ, EGL_PLATFORM="surfaceless",
                                             LIBGL_ALWAYS_SOFTWARE="1"))
            self.assertEqual(result.returncode, 0, result.stderr)
