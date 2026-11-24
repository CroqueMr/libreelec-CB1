"""Execute DCN4's actual color-block programming across ordinary/DV transitions."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_hdr10_transport import function


@unittest.skipUnless(os.environ.get('CB1_KERNEL_SOURCE'), 'matched kernel required')
class DCN4Transport(unittest.TestCase):
    def test_native_1to1_scaler_override_is_not_a_neutral_debug_setting(self):
        dc=Path(os.environ['CB1_KERNEL_SOURCE'])/'drivers/gpu/drm/amd/display/dc'
        functions=[]
        for folder,prefix in (('dcn10','dpp1'),('dcn401','dpp401')):
            source=(dc/'dpp'/folder/(folder+'_dpp_dscl.c')).read_text()
            functions.extend(function(source,prefix+name) for name in (
                '_dscl_is_video_format','_dscl_is_420_format','_dscl_get_dscl_mode'))
        code=r'''
#include <assert.h>
#include <stdbool.h>
enum dc_pixel_format {PIXEL_FORMAT_RGB=1,PIXEL_FORMAT_FP16,
 PIXEL_FORMAT_VIDEO_BEGIN=100,PIXEL_FORMAT_420BPP8,PIXEL_FORMAT_420BPP10,PIXEL_FORMAT_VIDEO_END=200};
enum {DSCL_DATA_PRCESSING_FIXED_FORMAT,DSCL_DATA_PRCESSING_FLOAT_FORMAT};
enum dscl_mode_sel {DSCL_MODE_DSCL_BYPASS,DSCL_MODE_SCALING_444_BYPASS,
 DSCL_MODE_SCALING_444_YCBCR_ENABLE,DSCL_MODE_SCALING_444_RGB_ENABLE,
 DSCL_MODE_SCALING_420_LUMA_BYPASS,DSCL_MODE_SCALING_420_CHROMA_BYPASS,
 DSCL_MODE_SCALING_420_YCBCR_ENABLE};
enum dcn401_dscl_mode_sel {DCN401_DSCL_MODE_DSCL_BYPASS,DCN401_DSCL_MODE_SCALING_444_BYPASS,
 DCN401_DSCL_MODE_SCALING_444_YCBCR_ENABLE,DCN401_DSCL_MODE_SCALING_444_RGB_ENABLE,
 DCN401_DSCL_MODE_SCALING_420_LUMA_BYPASS,DCN401_DSCL_MODE_SCALING_420_CHROMA_BYPASS,
 DCN401_DSCL_MODE_SCALING_420_YCBCR_ENABLE};
struct fixed {long long value;};
static const struct fixed dc_fixpt_one={1LL<<32};
struct scaler_data {enum dc_pixel_format format;struct {struct fixed horz,vert,horz_c,vert_c;}ratios;};
struct dpp {struct {int dscl_data_proc_format;} *caps;};
'''+'\n'.join(functions)+r'''
int main(void)
{
 struct {int dscl_data_proc_format;}caps={DSCL_DATA_PRCESSING_FIXED_FORMAT};
 struct dpp dpp={(void *)&caps};
 struct scaler_data data={.format=PIXEL_FORMAT_RGB,
     .ratios={dc_fixpt_one,dc_fixpt_one,dc_fixpt_one,dc_fixpt_one}};
 assert(dpp1_dscl_get_dscl_mode(&dpp,&data,false)==DSCL_MODE_SCALING_444_BYPASS);
 assert(dpp1_dscl_get_dscl_mode(&dpp,&data,true)==DSCL_MODE_SCALING_444_RGB_ENABLE);
 assert(dpp401_dscl_get_dscl_mode(&dpp,&data,false)==DCN401_DSCL_MODE_SCALING_444_BYPASS);
 assert(dpp401_dscl_get_dscl_mode(&dpp,&data,true)==DCN401_DSCL_MODE_SCALING_444_RGB_ENABLE);
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source,binary=Path(directory)/'test.c',Path(directory)/'test'
            source.write_text(code)
            result=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',
                str(source),'-o',str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_real_atomic_neutral_plane_and_exit_contract(self):
        kernel=Path(os.environ['CB1_KERNEL_SOURCE'])
        source=(kernel/'drivers/gpu/drm/amd/display/amdgpu_dm/amdgpu_dm_dv.c').read_text()
        names=('dv_rx550','dv_rx550_mode','dv_stream_edid','dv_sink_supported','lldv_sink_supported','dv_identity_tf',
               'dv_plane_neutral','dv_lldv_native_formats','dv_lldv_native_link','dv_lldv_native_mode','amdgpu_dm_dv_atomic_check')
        surface=(kernel/'drivers/gpu/drm/amd/display/dc/core/dc_surface.c').read_text()
        code=Path(__file__).with_name('amd_dv_atomic.c').read_text().replace(
            '@@FUNCTIONS@@','\n'.join([function(surface,'dc_plane_construct'),
                                      *(function(source,name) for name in names)]))
        with tempfile.TemporaryDirectory() as directory:
            src,binary=Path(directory)/'test.c',Path(directory)/'test'
            src.write_text(code)
            built=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',
                '-Wno-unused-parameter','-Wno-sign-compare','-Wno-unused-but-set-variable',
                '-fsanitize=address,undefined','-fno-pie','-no-pie',
                '-I'+str(kernel/'include/drm'),str(src),'-o',str(binary)],capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            ran=subprocess.run([str(binary)],capture_output=True,text=True)
            self.assertEqual(ran.returncode,0,ran.stderr)

    def test_native_neutral_blocks_and_ordinary_restoration(self):
        dc = Path(os.environ['CB1_KERNEL_SOURCE'])/'drivers/gpu/drm/amd/display/dc'
        sources = {
            '32': (dc/'hwss/dcn32/dcn32_hwseq.c').read_text(),
            '401': (dc/'hwss/dcn401/dcn401_hwseq.c').read_text(),
            '42': (dc/'hwss/dcn42/dcn42_hwseq.c').read_text(),
        }
        names = [('32', 'dcn32_set_mpc_shaper_3dlut'),
                 ('401', 'dcn401_program_gamut_remap'),
                 ('401', 'dcn401_set_mcm_luts'), ('42', 'dcn42_set_mcm_luts'),
                 ('32', 'dcn32_set_input_transfer_func'),
                 ('401', 'dcn401_set_output_transfer_func')]
        rmcm = function(sources['42'], 'dcn42_set_rmcm_luts')
        start = rmcm.index('struct rmcm *rmcm =')
        guard = rmcm.index('/* No RMCM on this plane', start)
        end = rmcm.index('rmcm_inst =', guard)
        rmcm_cleanup = ('dcn42_detach_rmcm', 'dcn42_release_rmcm_from_mpcc',
                        'dcn42_disable_rmcm_luts', 'dcn42_disable_mcm_luts')
        code = Path(__file__).with_name('dcn4_transport.c').read_text()
        code = code.replace('@@FUNCTIONS@@', '\n'.join(function(sources[key], name) for key, name in names))
        code = code.replace('@@RMCM_CLEANUP@@', '\n'.join(
            function(sources['42'], name) for name in rmcm_cleanup))
        code = code.replace('@@RMCM_ADMISSION@@',
                            (rmcm[start:guard].splitlines()[0] + '\n' + rmcm[guard:end]).rstrip())
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory)/'test.c', Path(directory)/'test'
            source.write_text(code)
            built = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                '-Wno-unused-parameter', '-fsanitize=undefined,address','-fno-pie','-no-pie',
                str(source), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            ran = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr)

