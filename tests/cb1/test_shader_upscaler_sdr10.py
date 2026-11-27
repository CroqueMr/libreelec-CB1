# SPDX-License-Identifier: MIT
"""The native shader upscaler admits 10-bit SDR without changing colour space."""
import unittest
from test_ai_reentry import execute
from test_native_video_source import TREE


class ShaderUpscalerSDR10(unittest.TestCase):
    def test_sdr10_color_admission(self):
        for api in ('GL', 'GLES'):
            with self.subTest(api=api):
                source = (TREE / ('xbmc/cores/VideoPlayer/VideoRenderers/LinuxRenderer' + api + '.cpp')).read_text()
                function = source[source.index('::RenderShaderUpscaler('):]
                policy = function[function.index('  const bool pq'):function.index('  if (m_currentField')]
                execute('''
#include <cassert>
enum { AVCOL_TRC_SMPTE2084, AVCOL_TRC_ARIB_STD_B67, AVCOL_TRC_BT709,
       AVCOL_TRC_UNSPECIFIED, AVCOL_SPC_BT709, AVCOL_SPC_UNSPECIFIED,
       AVCOL_PRI_BT709, AVCOL_PRI_UNSPECIFIED, AVCOL_PRI_BT2020,
       AVCOL_SPC_BT2020_NCL };
struct Buffer { int m_srcColTransfer, m_srcColSpace, m_srcPrimaries, m_srcBits; };
bool supports(bool hdr, Buffer buf) {
''' + policy + '''
  return supportedColor;
}
int main() {
  const Buffer sdr{AVCOL_TRC_BT709, AVCOL_SPC_BT709, AVCOL_PRI_BT709, 8};
  assert(supports(false, sdr));
  auto high = sdr; high.m_srcBits = 10;
  assert(supports(false, high));
  high.m_srcBits = 12; assert(!supports(false, high));
  const Buffer pq{AVCOL_TRC_SMPTE2084, AVCOL_SPC_BT2020_NCL, AVCOL_PRI_BT2020, 10};
  assert(supports(true, pq));
  assert(!supports(false, pq));
}
''')

    def test_sample_layout(self):
        source = (TREE / 'xbmc/cores/VideoPlayer/VideoRenderers/UpscalerSettings.h').read_text()
        policy = source[source.index('struct ShaderSourceLayout'):source.index('constexpr int Label(')]
        execute('''
#include <cassert>
''' + policy + '''
int main() {
  auto p010 = ShaderSource(false, 10, false, true, false, true);
  assert(p010.planes == 2 && p010.sampleDepth == 16 && p010.bitShift == 6);
  auto planar = ShaderSource(false, 10, false, false, true, false);
  assert(planar.planes == 3 && planar.sampleDepth == 16 && planar.bitShift == 0);
  assert(!ShaderSource(false, 10, false, true, false, false).planes);
  assert(!ShaderSource(false, 10, true, false, false, false).planes);
  assert(!ShaderSource(false, 12, false, true, false, true).planes);
  auto nv12 = ShaderSource(false, 8, false, true, false, false);
  assert(nv12.planes == 2 && nv12.sampleDepth == 8 && nv12.bitShift == 0);
  auto old = ShaderSource(true, 10, false, true, false, false);
  assert(old.planes == 2 && old.sampleDepth == 16 && old.bitShift == 6);
  assert(!ShaderSource(true, 10, false, false, true, false).planes);
}
''')
