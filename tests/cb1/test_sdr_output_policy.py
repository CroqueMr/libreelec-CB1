"""Check the gamut selection and code range used by the native SDR shaders."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_native_video_source import TREE


class SDROutputPolicyTests(unittest.TestCase):
    def test_saved_gamut_values_and_video_gui_code_range(self):
        probe = r"""
#include "windowing/gbm/SDROutputGamut.h"
#include <cassert>
#include <cmath>
#include <tuple>

using namespace KODI::WINDOWING::GBM;

static_assert(static_cast<int>(SDROutputGamut::Auto) == 0);
static_assert(static_cast<int>(SDROutputGamut::BT2020) == 1);
static_assert(static_cast<int>(SDROutputGamut::BT709) == 2);
static_assert(!WantsSDRBT2020(SDROutputGamut::Auto, false));
static_assert(WantsSDRBT2020(SDROutputGamut::Auto, true));
static_assert(WantsSDRBT2020(SDROutputGamut::BT2020, false));
static_assert(!WantsSDRBT2020(SDROutputGamut::BT709, true));
static_assert(SDROutputRange(false, 10) == std::pair{1.0f, 0.0f});
using Limits = std::pair<uint64_t,uint64_t>;
static_assert(SelectSDRBT2020MaxBpc(8,true,true,Limits{8,16})==10);
static_assert(!SelectSDRBT2020MaxBpc(8,false,true,Limits{8,16}));
static_assert(!SelectSDRBT2020MaxBpc(8,true,false,Limits{8,16}));
static_assert(!SelectSDRBT2020MaxBpc(8,true,true,Limits{8,8}));
static_assert(!SelectSDRBT2020MaxBpc(0,true,true,Limits{8,16}));
static_assert(!SelectSDRBT2020MaxBpc(10,false,true,Limits{12,16}));
static_assert(SelectSDRBT2020MaxBpc(12,false,true,Limits{8,16})==12);
static_assert(SelectSDRBT2020MaxBpc(10,false,false,{})==10);

int main()
{
  for (const auto [bits, black, white] : {std::tuple{8, 16, 235}, {10, 64, 940}, {12, 256, 3760}})
  {
    const auto [scale, offset] = SDROutputRange(true, bits);
    const float maximum = (1u << bits) - 1;
    assert(std::lround(offset * maximum) == black);
    assert(std::lround((scale + offset) * maximum) == white);
  }
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sdr.cpp"
            executable = Path(directory) / "sdr"
            source.write_text(probe, encoding="utf-8")
            compiled = subprocess.run(
                ["c++", "-std=c++20", "-I", str(TREE / "xbmc"), str(source), "-o", str(executable)],
                capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            subprocess.run([str(executable)], check=True)
