"""Mode changes must use a live connector and preserve the selected mode catalogue."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE, body


class LiveModeAdmission(unittest.TestCase):
    def test_live_connector_and_exact_timing(self):
        source = (TREE / 'xbmc/windowing/gbm/drm/DRMConnector.cpp').read_text()
        method = body(source, 'bool CDRMConnector::CheckConnector(')
        code = r'''
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <memory>
#include <vector>
using namespace std::chrono_literals;
constexpr int LOGDEBUG = 0, DRM_MODE_CONNECTED = 1, DRM_MODE_DISCONNECTED = 2;
struct CLog { template<class... T> static void LogF(T&&...) {} };
struct drmModeModeInfo {
  uint32_t clock = 594000;
  uint16_t hdisplay = 3840, hsync_start = 4016, hsync_end = 4104, htotal = 4400, hskew = 0;
  uint16_t vdisplay = 2160, vsync_start = 2168, vsync_end = 2178, vtotal = 2250, vscan = 0;
  uint32_t flags = 5, vrefresh = 60, type = 0;
};
struct drmModeConnector {uint32_t connector_id = 517; int connection = DRM_MODE_CONNECTED;
  int count_modes = 0; drmModeModeInfo* modes = nullptr;};
static unsigned now, reads, probes, freed, publishAt, physicalAt, nullAt;
static std::vector<drmModeModeInfo> timings, physicalTimings;
static drmModeModeInfo desktop{}, movie{296703};
static drmModeConnector* snapshot(bool connected) {
  auto* c = new drmModeConnector;
  c->connection = connected ? DRM_MODE_CONNECTED : DRM_MODE_DISCONNECTED;
  c->count_modes = connected ? int(timings.size()) : 0;
  if (c->count_modes) {
    c->modes = new drmModeModeInfo[c->count_modes];
    std::copy(timings.begin(), timings.end(), c->modes);
  }
  return c;
}
static void drmModeFreeConnector(drmModeConnector* c) { ++freed; delete[] c->modes; delete c; }
static drmModeConnector* drmModeGetConnectorCurrent(int, uint32_t id) {
  assert(id == 517); ++reads;
  return now >= nullAt ? nullptr : snapshot(now >= publishAt);
}
static drmModeConnector* drmModeGetConnector(int, uint32_t id) {
  assert(id == 517); ++probes;
  if (now >= physicalAt) { publishAt = now; timings = physicalTimings; }
  return snapshot(now >= publishAt);
}
namespace KODI::TIME { void Sleep(std::chrono::seconds duration) { now += duration.count() * 1000; } }
struct CDRMConnector {
  struct DrmModeConnectorDeleter { void operator()(drmModeConnector* c) { drmModeFreeConnector(c); } };
  int m_fd = 5;
  std::unique_ptr<drmModeConnector, DrmModeConnectorDeleter> m_connector{snapshot(true)};
  bool IsConnected() { return m_connector->connection == DRM_MODE_CONNECTED; }
  bool CheckConnector(const drmModeModeInfo& mode) METHOD
};
static void reset(unsigned publication, unsigned physical, unsigned null = 100000) {
  now = reads = probes = freed = 0;
  publishAt = publication; physicalAt = physical; nullAt = null;
  timings = physicalTimings = {desktop, movie};
}
int main() {
  reset(0,0); CDRMConnector connector;
  auto* catalogue = connector.m_connector.get();
  auto* selected = &catalogue->modes[0];
  assert(connector.CheckConnector(*selected));
  assert(reads == 1 && !probes && !now);
  // The startup cache is connected even when the current kernel status is not.
  reset(750,750);
  assert(connector.CheckConnector(*selected));
  assert(now == 1000 && reads == 2 && !probes);
  // A lost HPD edge: the sink becomes readable, but the published status remains stale.
  reset(100000,750);
  assert(connector.CheckConnector(*selected));
  assert(now == 1000 && reads == 2 && probes == 1);
  reset(100000,100000);
  assert(!connector.CheckConnector(*selected));
  assert(now == 7000 && reads == 8 && probes == 7);
  reset(0,0,0);
  assert(!connector.CheckConnector(*selected) && reads == 1 && !now && !probes);
  reset(100000,100000,1000);
  assert(!connector.CheckConnector(*selected) && now == 1000 && reads == 2 && !probes);
  reset(0,0);
  timings = {movie, desktop};
  assert(connector.CheckConnector(*selected));
  assert(connector.m_connector.get() == catalogue && &catalogue->modes[0] == selected);
  // Status can recover before the kernel repopulates the modes pruned on disconnect.
  timings.clear();
  assert(connector.CheckConnector(*selected) && probes == 1 && !now);
  assert(connector.m_connector.get() == catalogue);
  // A fresh mode list may lack the actual requested timing, even with the same rounded rate.
  reset(0,0); timings = {desktop}; timings[0].clock = 593407; physicalTimings = timings;
  assert(!connector.CheckConnector(*selected) && probes == 1 && !now);
  reset(0,0); timings = {desktop}; timings[0].flags ^= 1; physicalTimings = timings;
  assert(!connector.CheckConnector(*selected) && probes == 1 && !now);
  reset(0,0); timings.clear(); physicalTimings.clear();
  assert(!connector.CheckConnector(*selected) && probes == 1 && !now);
  assert(catalogue->modes[0].clock == 594000);
}
'''.replace('METHOD', method)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / 'test.cpp'
            src.write_text(code)
            binary = root / 'test'
            built = subprocess.run(['c++', '-std=c++20', str(src), '-o', str(binary)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_mode_selection_changes_only_after_admission(self):
        source = (TREE / 'xbmc/windowing/gbm/drm/DRMUtils.cpp').read_text()
        can_set = body(source, 'bool CDRMUtils::CanSetMode(')
        select = body(source, 'void CDRMUtils::SelectMode(')
        set_mode = body(source, 'bool CDRMUtils::SetMode(')
        code = r'''
#include <cassert>
#include <cstdlib>
#include <string>
constexpr int LOGDEBUG = 0, DRM_MODE_FLAG_INTERLACE = 1;
struct CLog { template<class... T> static void LogF(T&&...) {} };
struct Mode { int hdisplay=3840, vdisplay=2160, flags=0, vrefresh=60; };
struct RESOLUTION_INFO { std::string strId; int iWidth=3840, iHeight=2160; };
struct Connector {
  Mode modes[2]{{3840,2160,0,60},{3840,2160,0,24}};
  unsigned queries=0; bool ready=true;
  int GetModesCount() const { return 2; }
  Mode* GetModeForIndex(int index) { assert(index>=0 && index<2); return &modes[index]; }
  bool CheckConnector(const Mode&) { ++queries; return ready; }
};
struct CDRMUtils {
  Connector* m_connector; Mode* m_mode;
  int m_width=0, m_height=0;
  bool CanSetMode(const RESOLUTION_INFO& res) CAN_SET
  void SelectMode(const RESOLUTION_INFO& res) SELECT
  bool SetMode(const RESOLUTION_INFO& res) SET_MODE
};
int main() {
  Connector c; CDRMUtils drm{&c,&c.modes[1]};
  RESOLUTION_INFO next{"0"};
  c.ready=false;
  assert(!drm.SetMode(next) && drm.m_mode==&c.modes[1] && c.queries==1);
  for (auto id : {"-1","2"}) {
    assert(!drm.SetMode(RESOLUTION_INFO{id}) && drm.m_mode==&c.modes[1] && c.queries==1);
  }
  c.ready=true;
  assert(drm.CanSetMode(next) && drm.m_mode==&c.modes[1] && c.queries==2);
  drm.SelectMode(next); assert(drm.m_mode==&c.modes[0] && c.queries==2);
  assert(drm.SetMode(RESOLUTION_INFO{"1"}) && drm.m_mode==&c.modes[1] && c.queries==3);
}
'''.replace('CAN_SET', can_set).replace('SELECT', select).replace('SET_MODE', set_mode)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            src = root / 'test.cpp'
            src.write_text(code)
            binary = root / 'test'
            built = subprocess.run(['c++', '-std=c++20', str(src), '-o', str(binary)],
                                   capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_failed_admission_does_not_tear_down_or_publish_the_mode(self):
        base = (TREE / 'xbmc/windowing/gbm/WinSystemGbm.cpp').read_text()
        egl = (TREE / 'xbmc/windowing/gbm/WinSystemGbmEGLContext.cpp').read_text()
        utils = (TREE / 'xbmc/windowing/gbm/drm/DRMUtils.cpp').read_text()
        create = body(egl, 'bool CWinSystemGbmEGLContext::CreateNewWindow(')
        fullscreen = body(base, 'bool CWinSystemGbm::SetFullScreen(')
        set_mode = body(utils, 'bool CDRMUtils::SetMode(')
        for path in (create, fullscreen):
            self.assertLess(path.index('CanSetMode(res)'), path.index('OnLostDevice()'))
            self.assertLess(path.index('OnLostDevice()'), path.index('SelectMode(res)'))
        self.assertLess(create.index('DestroyWindow()'), create.index('SelectMode(res)'))
        self.assertLess(set_mode.index('CanSetMode(res)'), set_mode.index('SelectMode(res)'))
        for suffix in ('GL', 'GLES'):
            source = (TREE / f'xbmc/windowing/gbm/WinSystemGbm{suffix}Context.cpp').read_text()
            method = body(source, f'bool CWinSystemGbm{suffix}Context::SetFullScreen(')
            switched = method.index('const bool switched =')
            refusal = method.index('if (!switched)', switched)
            self.assertLess(refusal, method.index('ResetRenderSystem(', switched))


if __name__ == '__main__':
    unittest.main()
