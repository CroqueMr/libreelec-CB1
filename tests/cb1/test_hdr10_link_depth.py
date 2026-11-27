"""HDR10 conversion requires an HDMI link that can carry at least 10 bpc."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_native_video_source import TREE, body


class HDR10LinkDepthTests(unittest.TestCase):
    def test_startup_rejects_depth_before_timing_and_audio_setup(self):
        source = (TREE / 'xbmc/cores/VideoPlayer/VideoPlayer.cpp').read_text()
        video = body(source, 'bool CVideoPlayer::OpenVideoStream(')
        guard = body(video, 'if (window && (mode == DVBRIDGE_MODE_HDR10_BASIC')
        self.assertLess(video.index(guard), video.index('SetVideoResolution('))
        self.assertIn('m_errorDetail = CDVPlaybackInfo::ReasonLabel(reason);', guard)
        self.assertIn('m_bAbortRequest = true;', guard)
        defaults = body(source, 'void CVideoPlayer::OpenDefaultStreams(')
        self.assertLess(defaults.index('if (m_bAbortRequest)'), defaults.index('// open audio stream'))
    def test_hdr10_circuits_require_deep_color_when_hdmi_depth_is_known(self):
        headers = TREE / 'xbmc/cores/VideoPlayer/DVDCodecs/Video'
        info = (headers / 'DVPlaybackInfo.h').read_text()
        settings = (headers / 'DVOutputSettings.h').read_text()
        selection = (headers / 'DVOutputSelection.h').read_text()
        repo = Path(__file__).resolve().parents[2]
        program = r'''
#include <array>
#include <atomic>
#include <bit>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#define HAVE_DVBRIDGE
extern "C" {
#include "dvbridge_policy.h"
#include "cb1_cmv40.h"
}
#include "utils/DVBridgePresentation.h"
struct Settings {
  int GetInt(const char*) { return 0; }
  double GetNumber(const char*) { return 0; }
  bool GetBool(const char*) { return false; }
  Settings* GetSettings() { return this; }
};
struct CServiceBroker {
  static Settings* GetSettingsComponent() { static Settings settings; return &settings; }
};
namespace DVBRIDGE { uint64_t NextRevision() { return 1; } }
@INFO@
@SETTINGS@
@SELECTION@
int main()
{
  using namespace DVBRIDGE;
  OutputCapabilities caps{};
  caps.sourceKnown = caps.isDV = caps.hdr10 = caps.nativeDV = caps.processingKnown = true;
  for (auto& mode : caps.processing)
    mode.usable = true;
  OutputPreferences prefs{};
  prefs.output = OutputMode::HDR10;
  prefs.expertPeak = 1000;
  prefs.expertGamut = 2;
  for (int method : {0, 1})
  {
    prefs.method = method;
    for (unsigned depth : {0u, 8u, 10u, 12u})
    {
      caps.hdr10MaxBpc = depth;
      const auto result = SelectOutput(prefs, caps);
      if (depth == 8)
        assert(result.route == OutputRoute::Vanilla && result.reason == OutputReason::HDR10LinkDepthTooLow);
      else
        assert(result.route == OutputRoute::HDR10 && result.reason == OutputReason::None);
    }
  }
  caps.hdr10MaxBpc = 8;
  prefs.output = OutputMode::Standard;
  assert(SelectOutput(prefs, caps).route == OutputRoute::NativeDV);
}
'''
        program = program.replace('@INFO@', info).replace('@SETTINGS@', '\n'.join(
            line for line in settings.splitlines() if not line.startswith('#include')))
        program = program.replace('@SELECTION@', '\n'.join(
            line for line in selection.splitlines() if not line.startswith('#include')))
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / 'test'
            built = subprocess.run(['c++', '-std=c++20', '-I' + str(TREE / 'xbmc'),
                '-I' + str(repo / 'CB1/src'), '-x', 'c++', '-', '-o', str(binary)],
                input=program, capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
    def test_wide_sdr_does_not_change_never_wide_hdr10_depth(self):
        gbm = TREE / "xbmc/windowing/gbm"
        effective = body((gbm / "WinSystemGbm.cpp").read_text(),
                         "uint64_t CWinSystemGbm::GetEffectiveMaxBpc(")
        methods = [body((gbm / f"WinSystemGbm{api}Context.cpp").read_text(),
                        f"void CWinSystemGbm{api}Context::RefreshHDR10LinkDepth()")
                   for api in ("GL", "GLES")]
        self.assertEqual(methods[0], methods[1])
        program = r"""
#include <optional>
#include <algorithm>
#include <array>
#include <string>
#include <cstdint>
#include <utility>
#include <cassert>
using std::uint64_t;
constexpr std::array<uint64_t,4> MAX_BPC_VALUES{0,8,10,12};
constexpr auto MAX_BPC="max bpc";
constexpr auto SDR_BT2020_DEEP_COLOR="CB1_SDR_BT2020_DEEP_COLOR";
struct Connector {
  bool guard=false; uint64_t current=8;
  std::string GetType() const { return "HDMI-A"; }
  bool SupportsProperty(const char*) const { return true; }
  std::optional<uint64_t> GetPropertyValue(std::string s) const
  { return s==SDR_BT2020_DEEP_COLOR ? guard : current; }
  std::optional<std::pair<uint64_t,uint64_t>> GetRangePropertyLimits(const char*) const
  { return std::pair<uint64_t,uint64_t>{8,16}; }
};
struct DRM { Connector c; Connector* GetConnector() { return &c; } };
struct Snapshot {
  std::optional<uint64_t> before; bool wasWide=false;
  bool Captured() const { return before.has_value(); }
  std::optional<uint64_t> Before(std::string s) const {
    if (!Captured()) return {};
    if (s==SDR_BT2020_DEEP_COLOR) return wasWide;
    return before;
  }
};
struct Win {
  DRM drm; DRM* m_DRM=&drm; Snapshot m_cb1ConnectorState,m_dvState;
  int m_maxBpc=0; bool m_maxBpcFallback=false; uint64_t m_hdr10MaxBpc=0;
  bool SDRBT2020DeepColorSupported() const { return true; }
  std::optional<uint64_t> DefaultMaxBpc() const { return 8; }
  uint64_t GetEffectiveMaxBpc(std::optional<uint64_t> restored={}) const @EFFECTIVE@
  void RefreshHDR10LinkDepth() @REFRESH@
};
int main() {
  Win w;
  w.m_cb1ConnectorState.before=8; w.m_maxBpc=2;
  w.RefreshHDR10LinkDepth(); assert(w.m_hdr10MaxBpc==10);
  w.m_cb1ConnectorState.before.reset(); w.m_maxBpc=0;
  w.drm.c.guard=true; w.drm.c.current=10;
  w.RefreshHDR10LinkDepth(); assert(w.m_hdr10MaxBpc==8);
  w.drm.c.guard=false; w.drm.c.current=8;
  w.m_dvState.before=10; w.m_dvState.wasWide=true; w.m_cb1ConnectorState.before=8;
  w.RefreshHDR10LinkDepth(); assert(w.m_hdr10MaxBpc==8);
}
""".replace("@EFFECTIVE@", effective).replace("@REFRESH@", methods[0])
        with tempfile.TemporaryDirectory() as directory:
            binary = Path(directory) / "wide-hdr-depth"
            result = subprocess.run(["c++", "-std=c++20", "-x", "c++", "-", "-o", str(binary)],
                                    input=program, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(binary)], check=True)
