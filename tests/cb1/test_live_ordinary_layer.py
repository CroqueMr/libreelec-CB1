"""A live return from CB1 composition must move to the ordinary GUI pass."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE, body


class LiveOrdinaryLayerTests(unittest.TestCase):
    def test_real_render_layer_can_demote_as_well_as_promote(self):
        for suffix in ('GL', 'GLES'):
            with self.subTest(renderer=suffix):
                name = 'CLinuxRenderer' + suffix
                source = (TREE / f'xbmc/cores/VideoPlayer/VideoRenderers/LinuxRenderer{suffix}.cpp').read_text()
                methods = '\n'.join(body(source, f'{kind} {name}::{method}()')
                                    for kind, method in (('bool', 'IsGuiLayer'), ('void', 'UpdateVideoRenderLayer')))
                program = r'''
#include <cassert>
#include <optional>
struct State {
  bool wide = false, composite = false;
  unsigned dirty = 0;
  bool UsesNativeSDRBT2020() { return wide; }
  bool IsHdrComposite() { return composite; }
  void InvalidateGuiComposite() { ++dirty; }
  State& GetWindowManager() { return *this; }
  void MarkDirty() { ++dirty; }
};
namespace KODI::WINDOWING::GBM {
  using CWinSystemGbmDVContext = State;
  using CWinSystemGbmGLESContext = State;
}
struct CServiceBroker {
  static State* GetWinSystem() { static State s; return &s; }
  static State* GetGUI() { return GetWinSystem(); }
  static auto& GetDataCacheCore() { static CServiceBroker c; return c; }
  unsigned GetVideoProcessingGeneration() { return 7; }
};
struct Source { struct { unsigned informationGeneration = 7; } doviSourceInfo; };
struct Renderer {
  std::optional<bool> m_pendingHdrFbo;
  bool m_hdrFboActive = false, m_dvRequested = false;
  int m_iYUVRenderBuffer = 0;
  struct Slot { std::optional<Source> doviSourcePicture{Source{}}; } m_buffers[1];
  bool IsGuiLayer() @GUI@
  void UpdateVideoRenderLayer() @UPDATE@
};
int main() {
  Renderer renderer;
  auto& window = *CServiceBroker::GetWinSystem();
  renderer.m_dvRequested = true;
  renderer.m_pendingHdrFbo = true;
  window.composite = true;
  renderer.UpdateVideoRenderLayer();
  assert(!renderer.IsGuiLayer());
  renderer.m_dvRequested = false;
  renderer.m_pendingHdrFbo = false;
  window.composite = false;
  renderer.UpdateVideoRenderLayer();
  assert(renderer.IsGuiLayer());
  assert(renderer.m_pendingHdrFbo.has_value()); // still owns the selected frame
  renderer.m_pendingHdrFbo.reset();
  window.wide = true;
  assert(!renderer.IsGuiLayer()); // native wide SDR has a separate late pass
  window.wide = false;
  assert(renderer.IsGuiLayer());
  renderer.m_pendingHdrFbo = true;
  renderer.m_buffers[0].doviSourcePicture->doviSourceInfo.informationGeneration = 6;
  renderer.UpdateVideoRenderLayer();
  assert(!renderer.m_pendingHdrFbo && renderer.IsGuiLayer());
}
'''.replace('@GUI@', body(source, f'bool {name}::IsGuiLayer()')).replace('@UPDATE@', body(source, f'void {name}::UpdateVideoRenderLayer()'))
                with tempfile.TemporaryDirectory() as temp:
                    path = Path(temp) / 'test.cpp'
                    path.write_text(program)
                    exe = path.with_suffix('')
                    subprocess.run(['c++', '-std=c++20', str(path), '-o', str(exe)], check=True)
                    subprocess.run([str(exe)], check=True)