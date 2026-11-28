"""SDR upconversion is opt in, source-aware, and has separate transport admission."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from test_native_video_source import TREE, body

VIDEO = TREE / "xbmc/cores/VideoPlayer/DVDCodecs/Video"

class SDRUpconversionTests(unittest.TestCase):
    def test_native_default_and_output_choices(self):
        settings = ET.parse(TREE / "system/settings/settings.xml").getroot()
        row = settings.find(".//setting[@id='dvbridge.sdrsource']")
        self.assertIsNotNone(row)
        self.assertEqual(row.findtext("default"), "0")
        self.assertEqual([o.text for o in row.findall("constraints/options/option")], ["0", "1", "2"])
        selectors = (VIDEO / "DVOutputSettings.h").read_text()
        self.assertIn("SDRSourceMode::Native", selectors)
        self.assertIn('GetInt("dvbridge.sdrsource")', selectors)
        self.assertIn("preferences.sdrSource=sdrSource", selectors)

    def test_sdr_transfer_and_color_admission(self):
        source = (VIDEO / "SDRSourceType.h").read_text()
        fn = body(source, "inline bool IsSDRExpansionColor(")
        program = r"""
#include <cassert>
extern "C" {
#include <libavutil/pixfmt.h>
}
bool valid(AVColorTransferCharacteristic transfer, AVColorSpace matrix, AVColorPrimaries primaries) BODY
int main() {
  assert(valid(AVCOL_TRC_BT709, AVCOL_SPC_BT709, AVCOL_PRI_BT709));
  assert(valid(AVCOL_TRC_SMPTE170M, AVCOL_SPC_SMPTE170M, AVCOL_PRI_SMPTE170M));
  assert(valid(AVCOL_TRC_BT2020_10, AVCOL_SPC_BT2020_NCL, AVCOL_PRI_BT2020));
  assert(valid(AVCOL_TRC_UNSPECIFIED, AVCOL_SPC_UNSPECIFIED, AVCOL_PRI_BT709));
  assert(!valid(AVCOL_TRC_SMPTE2084, AVCOL_SPC_BT2020_NCL, AVCOL_PRI_BT2020));
  assert(!valid(AVCOL_TRC_ARIB_STD_B67, AVCOL_SPC_BT2020_NCL, AVCOL_PRI_BT2020));
  assert(!valid(AVCOL_TRC_LINEAR, AVCOL_SPC_BT709, AVCOL_PRI_BT709));
  assert(!valid(AVCOL_TRC_BT709, AVCOL_SPC_BT2020_CL, AVCOL_PRI_BT2020));
}
""".replace("BODY", fn)
        import os
        prefix = Path(os.environ["FFMPEG_TEST_PREFIX"])
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "test"
            build = subprocess.run(["c++","-std=c++20","-I"+str(prefix/"include"),"-x","c++","-","-o",str(exe)], input=program,text=True,capture_output=True)
            self.assertEqual(build.returncode,0,build.stderr)
            subprocess.run([str(exe)],check=True)

    def test_transport_and_source_are_independent(self):
        decision = (VIDEO / "DVOutputSelection.h").read_text()
        branch = body(decision, "inline OutputSelection SelectSDRExpansionOutput(")
        self.assertIn("caps.isSDR", branch)
        self.assertIn("caps.HDR10DepthLimited()", branch)
        self.assertIn("caps.nativeDV", branch)
        self.assertIn("caps.hdr10", branch)
        self.assertIn("OutputRoute::HDR10", branch)
        self.assertIn("OutputRoute::NativeDV", branch)
        self.assertIn("OutputRoute::Vanilla", branch)
        for api in ("GL", "GLES"):
            ctx=(TREE / f"xbmc/windowing/gbm/WinSystemGbm{api}Context.cpp").read_text()
            self.assertIn("IsSDRExpansionSource", ctx)
            self.assertIn("ConfigureHDR10Conversion", ctx)
            self.assertIn("sdrInput", ctx)
            self.assertIn("m_dvBridge->PlayerLed() || layer.sdrInput", ctx)
        renderer=(TREE/"xbmc/cores/VideoPlayer/VideoRenderers/DVBridgeGLES.cpp").read_text()
        self.assertIn("dvbridge_prepare_sdr_expansion(", renderer)
        self.assertIn("dvbridge_render_sdr_hdr10(", renderer)
        menu=(TREE/"xbmc/dialogs/DVPlaybackModes.cpp").read_text()
        self.assertIn("dvbridge.sdrplaybackchoice", menu)
        self.assertIn("active.sdrSource", menu)
