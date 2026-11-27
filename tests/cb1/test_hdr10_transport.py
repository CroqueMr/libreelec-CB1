"""Compile the real replayed kernel selectors, not a parallel policy model.

CB1_KERNEL_SOURCE must name the pinned Generic Linux source with the shipped kernel patches applied.
No kernel build or GPU access is needed. The native DC global validation and
physical wire precision still require hardware qualification.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


def function(source, name):
    match = re.search(r'^(?:static )?(?:inline )?(?:[\w]+\s+)+\*?' + name +
                      r'\([^;{]+\)\s*\{', source, re.M)
    if not match:
        raise AssertionError('Missing native function: ' + name)
    start, position, depth = match.start(), match.end(), 1
    while depth:
        depth += (source[position] == '{') - (source[position] == '}')
        position += 1
    return source[start:position]


@unittest.skipUnless(os.environ.get('CB1_KERNEL_SOURCE'),
                     'set CB1_KERNEL_SOURCE to the privately replayed pinned kernel')
class HDR10Transport(unittest.TestCase):
    def compile_run(self, code):
        with tempfile.TemporaryDirectory() as directory:
            source, binary = Path(directory)/'check.c', Path(directory)/'check'
            source.write_text(code)
            built = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                                    str(source), '-o', str(binary)], capture_output=True, text=True)
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_amd_hdmi_preserves_deep_color_through_format_selection_and_atomic_check(self):
        root = Path(os.environ['CB1_KERNEL_SOURCE'])/'drivers/gpu/drm/amd/display/amdgpu_dm'
        source = (root/'amdgpu_dm_connector.c').read_text()
        source = source.replace('struct dc_stream_state *\namdgpu_dm_create_validate_stream_for_sink',
                                'struct dc_stream_state *amdgpu_dm_create_validate_stream_for_sink')
        dv = (root/'amdgpu_dm_dv.c').read_text()
        format_stream = function(source, 'fill_stream_properties_from_drm_display_mode')
        admission = format_stream.split('const bool deep_tmds =', 1)[1].split(';', 1)[0]
        depth = format_stream.split('stream->out_transfer_func.tf = TRANSFER_FUNCTION_SRGB;', 1)[1]
        depth = depth.split('stream->output_color_space =', 1)[0]
        helpers = [function(dv,name) for name in ('amdgpu_dm_hdr10_validate',
                   'amdgpu_dm_hdr10_depth','amdgpu_dm_hdr10_atomic_check')]
        helpers.extend(function(source,name) for name in ('amdgpu_dm_hdr10_tmds',
                       'amdgpu_dm_hdr10_encoding_depth','adjust_colour_depth_from_display_info',
                       'amdgpu_dm_convert_color_depth_from_display_info','dm_validate_stream_color_format'))
        selector = function(source, 'amdgpu_dm_create_validate_stream_for_sink')
        self.compile_run(r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define EINVAL 22
#define BIT(n) (1U << (n))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof(*(a)))
#define min_t(t,a,b) ((t)((a)<(b)?(a):(b)))
#define STATIC_IFN_KUNIT static
#define drm_dbg_kms(...) ((void)0)
#define drm_err(...) ((void)0)
typedef uint8_t u8;
typedef uint32_t u32;
enum dc_pixel_encoding { PIXEL_ENCODING_RGB, PIXEL_ENCODING_YCBCR444, PIXEL_ENCODING_YCBCR422,
 PIXEL_ENCODING_YCBCR420, PIXEL_ENCODING_UNDEFINED };
enum dc_color_depth { COLOR_DEPTH_UNDEFINED, COLOR_DEPTH_666, COLOR_DEPTH_888, COLOR_DEPTH_101010,
 COLOR_DEPTH_121212, COLOR_DEPTH_141414, COLOR_DEPTH_161616, COLOR_DEPTH_999, COLOR_DEPTH_111111 };
enum signal_type { SIGNAL_TYPE_NONE, SIGNAL_TYPE_HDMI_TYPE_A, SIGNAL_TYPE_HDMI_FRL,
 SIGNAL_TYPE_DISPLAY_PORT, SIGNAL_TYPE_DISPLAY_PORT_MST };
enum dc_status { DC_OK, DC_ERROR_UNEXPECTED, DC_UNSUPPORTED_VALUE, DC_FAIL_BANDWIDTH_VALIDATE };
enum { DRM_MODE_CONNECTOR_HDMIA=1, DRM_MODE_CONNECTOR_WRITEBACK, DRM_MODE_CONNECTOR_DisplayPort,
 DRM_OUTPUT_COLOR_FORMAT_YCBCR444=1, DRM_OUTPUT_COLOR_FORMAT_YCBCR422,
 DRM_CONNECTOR_COLOR_FORMAT_AUTO=0, DRM_CONNECTOR_COLOR_FORMAT_RGB444,
 DRM_CONNECTOR_COLOR_FORMAT_YCBCR444, DRM_CONNECTOR_COLOR_FORMAT_YCBCR422,
 DRM_CONNECTOR_COLOR_FORMAT_YCBCR420, DISPLAY_DONGLE_DP_HDMI_CONVERTER,
 DRM_EDID_HDMI_DC_30=1, DRM_EDID_HDMI_DC_36=2, DRM_EDID_HDMI_DC_48=4,
 DRM_EDID_YCBCR420_DC_30=1, DRM_EDID_YCBCR420_DC_36=2, DRM_EDID_YCBCR420_DC_48=4,
 DRM_MODE_COLORIMETRY_BT2020_RGB=1, DRM_MODE_COLORIMETRY_BT2020_YCC, HDMI_EOTF_SMPTE_ST2084=2 };
struct drm_display_info { unsigned color_formats; int bpc,max_tmds_clock;
 unsigned edid_hdmi_rgb444_dc_modes,edid_hdmi_ycbcr444_dc_modes; struct {unsigned y420_dc_modes;} hdmi; };
struct drm_connector { void *dev; int connector_type; struct drm_display_info display_info; };
struct hdr_output_metadata { int metadata_type; struct {int metadata_type,eotf;} hdmi_metadata_type1; };
struct drm_property_blob { size_t length; void *data; };
struct drm_connector_state { struct drm_connector *connector; void *crtc; int max_requested_bpc;
 int colorspace,color_format; struct drm_property_blob *hdr_output_metadata; void *hdr10plus_metadata; };
struct dm_connector_state { struct drm_connector_state base; bool hdr10_deep_color,dv_standard; unsigned lldv_format; };
struct dc_link { enum signal_type connector_signal; struct {int dongle_type;} dpcd_caps; };
struct amdgpu_dm_connector { struct drm_connector base; struct dc_link *dc_link;
 enum dc_pixel_encoding force_yuv_pixel_format; void *hdr10_deep_color_property; };
struct drm_display_mode { unsigned clock; bool only420,also420; };
struct dc_crtc_timing { enum dc_pixel_encoding pixel_encoding; enum dc_color_depth display_color_depth;
 unsigned pix_clk_100hz; };
struct dc_stream_state { enum signal_type signal; struct dc_link *link; struct dc_crtc_timing timing;
 bool dv_standard,dv_native_lldv; };
struct amdgpu_device { struct {void *dc;} dm; };
struct drm_crtc_state { bool active; struct dc_stream_state *stream; };
struct drm_atomic_commit { struct drm_connector_state *con; struct drm_crtc_state *cs; };
#define to_dm_crtc_state(p) (p)
#define to_amdgpu_dm_connector(p) ((struct amdgpu_dm_connector *)(p))
#define to_dm_connector_state(p) ((const struct dm_connector_state *)(p))
#define for_each_new_connector_in_state(s,c,con,i) \
 for((i)=0;(i)<1 && (((con)=(s)->con),((c)=(con)->connector),true);++(i))
static struct drm_crtc_state *drm_atomic_get_new_crtc_state(struct drm_atomic_commit *s,void *crtc)
{ (void)crtc; return s->cs; }
static bool amdgpu_dm_dv_transport(const struct dm_connector_state *s)
{ return s->dv_standard || s->lldv_format; }
static bool drm_mode_is_420_only(const struct drm_display_info *i,const struct drm_display_mode *m)
{ (void)i; return m->only420; }
static bool drm_mode_is_420_also(const struct drm_display_info *i,const struct drm_display_mode *m)
{ (void)i; return m->also420; }
static bool dc_is_hdmi_signal(enum signal_type s)
{ return s==SIGNAL_TYPE_HDMI_TYPE_A || s==SIGNAL_TYPE_HDMI_FRL; }
static bool dc_is_dp_signal(enum signal_type s)
{ return s==SIGNAL_TYPE_DISPLAY_PORT || s==SIGNAL_TYPE_DISPLAY_PORT_MST; }
static struct amdgpu_device device;
static struct amdgpu_device *drm_to_adev(void *p){ (void)p; return &device; }
@@HELPERS@@
static bool reject_422,reject_420;
static unsigned tested_formats,live;
static struct dc_stream_state stream_value;
static struct dc_stream_state *create_stream_for_sink(struct drm_connector *connector,
 const struct drm_display_mode *mode,const struct dm_connector_state *state,
 const struct dc_stream_state *old,int requested_bpc,enum dc_pixel_encoding requested_encoding,bool is_hdmi_ep)
{
 (void)old;
 assert(live++==0);
 struct dc_stream_state *stream=&stream_value;
 struct dc_crtc_timing *timing_out=&stream->timing;
 const struct drm_display_info *info=&connector->display_info;
 const struct drm_connector_state *connector_state=&state->base;
 stream->link=to_amdgpu_dm_connector(connector)->dc_link;
 stream->signal=stream->link->connector_signal;
 stream->dv_native_lldv=false;
 stream->dv_standard=state->dv_standard;
 *timing_out=(struct dc_crtc_timing){requested_encoding,
  amdgpu_dm_convert_color_depth_from_display_info(connector,requested_encoding==PIXEL_ENCODING_YCBCR420,requested_bpc),
  mode->clock*10};
 const bool deep_tmds = @@ADMISSION@@;
 @@DEPTH@@
 if (state->lldv_format==3 || state->lldv_format==4) {
  assert(requested_encoding==PIXEL_ENCODING_RGB);
  stream->dv_native_lldv=true;
  timing_out->pixel_encoding=state->lldv_format==3?PIXEL_ENCODING_YCBCR422:PIXEL_ENCODING_YCBCR444;
  timing_out->display_color_depth=COLOR_DEPTH_101010;
 }
 return stream;
}
static enum dc_status dc_validate_stream(void *dc,struct dc_stream_state *s)
{ (void)dc; tested_formats|=BIT(s->timing.pixel_encoding); return DC_OK; }
static enum dc_status dm_dp_mst_is_port_support_mode(void *a,void *s)
{ (void)a; (void)s; return DC_OK; }
static enum dc_status dm_validate_stream_and_context(void *dc,struct dc_stream_state *s)
{
 (void)dc;
 return (reject_422 && s->timing.pixel_encoding==PIXEL_ENCODING_YCBCR422) ||
        (reject_420 && s->timing.pixel_encoding==PIXEL_ENCODING_YCBCR420) ? DC_FAIL_BANDWIDTH_VALIDATE : DC_OK;
}
static void dc_stream_release(void *s){ (void)s; assert(live--==1); }
@@SELECTOR@@
int main(void)
{
 struct dc_link link={.connector_signal=SIGNAL_TYPE_HDMI_TYPE_A};
 struct amdgpu_dm_connector c={.base={.connector_type=DRM_MODE_CONNECTOR_HDMIA,
  .display_info={.color_formats=BIT(DRM_OUTPUT_COLOR_FORMAT_YCBCR422),.bpc=10,.max_tmds_clock=600000,
    .edid_hdmi_rgb444_dc_modes=DRM_EDID_HDMI_DC_30,.hdmi={DRM_EDID_YCBCR420_DC_30}}},
  .dc_link=&link,.force_yuv_pixel_format=PIXEL_ENCODING_UNDEFINED,.hdr10_deep_color_property=&c};
 struct hdr_output_metadata hdr={.hdmi_metadata_type1={0,HDMI_EOTF_SMPTE_ST2084}};
 struct drm_property_blob blob={sizeof(hdr),&hdr};
 struct dm_connector_state state={.base={.connector=&c.base,.crtc=&state,.max_requested_bpc=10,
  .colorspace=DRM_MODE_COLORIMETRY_BT2020_RGB,.hdr_output_metadata=&blob},.hdr10_deep_color=true};
 const struct drm_display_info defaults=c.base.display_info;
 const struct dm_connector_state preferences=state;
 for(int i=0;i<16;++i) {
  struct drm_display_mode mode={.clock=594000,.also420=true};
  enum dc_pixel_encoding expected=PIXEL_ENCODING_YCBCR422;
  enum dc_color_depth depth=COLOR_DEPTH_101010;
  bool valid=true;
  c.base.display_info=defaults; state=preferences; tested_formats=0; reject_422=false; reject_420=false;
  if(i==1){ mode.clock=297000; expected=PIXEL_ENCODING_RGB; }
  if(i==2){ reject_422=true; expected=PIXEL_ENCODING_YCBCR420; }
  if(i==3){ reject_422=true; reject_420=true; valid=false; }
  if(i==4){ mode.only420=true; mode.also420=false; expected=PIXEL_ENCODING_YCBCR420; }
  if(i==5){ mode.only420=true; state.base.color_format=DRM_CONNECTOR_COLOR_FORMAT_RGB444; valid=false; }
  if(i==6){ c.base.display_info.hdmi.y420_dc_modes=0; reject_422=true; valid=false; }
  if(i==7){ mode.clock=297000; c.base.display_info.edid_hdmi_rgb444_dc_modes=0; }
  if(i==8){ c.base.display_info.bpc=8; }
  if(i==9){ state.hdr10_deep_color=false; state.base.hdr10plus_metadata=&state; }
  if(i==10){ state.hdr10_deep_color=false; state.base.max_requested_bpc=8;
   expected=PIXEL_ENCODING_RGB; depth=COLOR_DEPTH_888; }
  if(i==11 || i==12){ state.hdr10_deep_color=false; state.lldv_format=i==11?3:4;
   state.base.color_format=DRM_CONNECTOR_COLOR_FORMAT_RGB444;
   expected=i==11?PIXEL_ENCODING_YCBCR422:PIXEL_ENCODING_YCBCR444; }
  if(i==13){ state.hdr10_deep_color=false; state.dv_standard=true; state.base.max_requested_bpc=8;
   expected=PIXEL_ENCODING_RGB; depth=COLOR_DEPTH_888; }
  if(i==14){ mode.clock=297000; state.base.color_format=DRM_CONNECTOR_COLOR_FORMAT_YCBCR444;
   c.base.display_info.bpc=8; c.base.display_info.color_formats|=BIT(DRM_OUTPUT_COLOR_FORMAT_YCBCR444);
   c.base.display_info.edid_hdmi_ycbcr444_dc_modes=DRM_EDID_HDMI_DC_30; expected=PIXEL_ENCODING_YCBCR444; }
  if(i==15){ reject_422=true; c.base.display_info.bpc=8; expected=PIXEL_ENCODING_YCBCR420; }
  struct dc_stream_state *s=amdgpu_dm_create_validate_stream_for_sink(&c.base,&mode,&state,NULL);
  assert(c.force_yuv_pixel_format==PIXEL_ENCODING_UNDEFINED);
  assert((s!=NULL)==valid);
  if(i==2)assert(tested_formats==(BIT(PIXEL_ENCODING_YCBCR422)|BIT(PIXEL_ENCODING_YCBCR420)));
  if(valid){
   assert(s->timing.pixel_encoding==expected && s->timing.display_color_depth==depth);
   assert(s->timing.pix_clk_100hz==mode.clock*10);
   dc_stream_release(s);
  }
  assert(live==0);
 }
 state=preferences;
 struct dc_stream_state wire={.signal=SIGNAL_TYPE_HDMI_TYPE_A,.link=&link,
  .timing={PIXEL_ENCODING_YCBCR422,COLOR_DEPTH_101010,5940000}};
 struct drm_crtc_state cs={true,&wire};
 struct drm_atomic_commit commit={&state.base,&cs};
 assert(amdgpu_dm_hdr10_atomic_check(&commit)==0);
 wire.signal=SIGNAL_TYPE_HDMI_FRL;
 wire.timing.pixel_encoding=PIXEL_ENCODING_RGB;
 wire.timing.display_color_depth=COLOR_DEPTH_121212;
 assert(amdgpu_dm_hdr10_atomic_check(&commit)==0);
 wire.timing.display_color_depth=COLOR_DEPTH_999;
 assert(amdgpu_dm_hdr10_atomic_check(&commit)==-EINVAL);
 wire.timing.display_color_depth=COLOR_DEPTH_101010;
 wire.dv_standard=true;
 assert(amdgpu_dm_hdr10_atomic_check(&commit)==-EINVAL);
 wire.dv_standard=false; cs.active=false;
 assert(amdgpu_dm_hdr10_atomic_check(&commit)==-EINVAL);
 cs.active=true; wire.link=NULL;
 assert(amdgpu_dm_hdr10_atomic_check(&commit)==-EINVAL);
}
'''.replace('@@HELPERS@@','\n'.join(helpers)).replace('@@SELECTOR@@',selector)
        .replace('@@ADMISSION@@',admission).replace('@@DEPTH@@',depth))


    def test_intel_native_rgb_then_420_obeys_edid_depth_and_link_limits(self):
        root = Path(os.environ['CB1_KERNEL_SOURCE'])/'drivers/gpu/drm/i915/display'
        source = (root/'intel_hdmi.c').read_text()
        policy = (root/'intel_dvbridge_hdr_policy.h').read_text()
        names = ('intel_hdmi_has_gmp_hdr', 'intel_hdmi_tmds_clock', 'intel_hdmi_source_bpc_possible',
                 'intel_hdmi_sink_bpc_possible', 'intel_hdmi_sink_format_valid',
                 'intel_hdmi_compute_bpc', 'intel_hdmi_compute_clock',
                 'intel_hdmi_output_format', 'intel_hdmi_compute_output_format',
                 'intel_dvbridge_hdr_deep_requested', 'intel_hdmi_compute_formats')
        config = function(source, 'intel_hdmi_compute_config')
        transport = next(line for line in config.splitlines() if 'lldv =' in line)
        admission = config.split('/* This opt-in', 1)[1].split('pipe_config->has_audio', 1)[0]
        admission = '/* This opt-in' + admission
        final_guard = config.split('\tret = intel_hdmi_compute_formats(', 1)[1]
        final_guard = '\tret = intel_hdmi_compute_formats(' + final_guard.split('\n\tif (ret) {', 1)[0]
        code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#define EINVAL 22
#define min(a,b) ((a)<(b)?(a):(b))
#define max(a,b) ((a)>(b)?(a):(b))
#define DIV_ROUND_CLOSEST(a,b) (((a)+(b)/2)/(b))
typedef unsigned char u8;
#define DISPLAY_VER(d) ((d)->version)
#define HAS_GMCH(d) (false)
#define MISSING_CASE(x) ((void)(x))
#define drm_dbg_kms(d,...) ((void)(d))
#define drm_info(...) ((void)0)
#define __ratelimit(p) ((void)(p),false)
enum intel_output_format { INTEL_OUTPUT_FORMAT_RGB, INTEL_OUTPUT_FORMAT_YCBCR420 };
enum drm_mode_status { MODE_OK, MODE_NO_420, MODE_BAD };
enum { DRM_MODE_FLAG_DBLCLK=1, DRM_MODE_COLORIMETRY_BT2020_RGB=1, DRM_MODE_COLORIMETRY_BT2020_YCC=2,
 HDMI_EOTF_SMPTE_ST2084=2, DRM_EDID_YCBCR420_DC_30=1, DRM_EDID_YCBCR420_DC_36=2,
 DRM_EDID_HDMI_DC_30=1, DRM_EDID_HDMI_DC_36=2 };
struct hdr_output_metadata { int metadata_type; struct {int metadata_type,eotf;} hdmi_metadata_type1; };
struct drm_property_blob { size_t length; void *data; };
struct drm_hdmi_info {unsigned y420_dc_modes;};
struct drm_display_info {struct drm_hdmi_info hdmi;unsigned edid_hdmi_rgb444_dc_modes;
 int max_tmds_clock;bool also420,only420;};
struct drm_connector {struct drm_display_info display_info;bool ycbcr_420_allowed;};
struct intel_connector {struct drm_connector base;int dv_log_limit;};
struct drm_connector_state {struct drm_connector *connector;unsigned max_requested_bpc;int colorspace;
 struct drm_property_blob *hdr_output_metadata;void *hdr10plus_metadata;};
struct intel_digital_connector_state {struct drm_connector_state base;bool dv_hdr10_deep_color,dv_lab_standard;unsigned lldv_format;};
struct drm_display_mode {int crtc_clock,flags;};
#define drm_err(...) ((void)0)
struct intel_display {int version;void *drm;struct{bool skylake,kabylake;}platform;};
struct intel_encoder {int limit;struct intel_connector *connector;};
struct intel_crtc_state {struct {struct drm_display_mode adjusted_mode;} hw;
 int pipe_bpp,port_clock;enum intel_output_format sink_format,output_format;bool has_hdmi_sink;
 struct intel_connector *connector;};
static struct intel_display display_state={.version=12};
#define to_intel_display(p) ((void)(p),&display_state)
#define to_intel_connector(p) ((struct intel_connector *)(p))
#define to_intel_digital_connector_state(p) ((struct intel_digital_connector_state *)(p))
#define enc_to_intel_hdmi(p) (p)
static bool drm_mode_is_420_also(const struct drm_display_info *i,const struct drm_display_mode *m)
{(void)m;return i->also420;}
static bool drm_mode_is_420_only(const struct drm_display_info *i,const struct drm_display_mode *m)
{(void)m;return i->only420;}
static bool drm_mode_is_420(const struct drm_display_info *i,const struct drm_display_mode *m)
{return drm_mode_is_420_also(i,m)||drm_mode_is_420_only(i,m);}
static enum drm_mode_status hdmi_port_clock_valid(struct intel_encoder *e,int clock,bool strict,bool hdmi)
{(void)hdmi;return clock<=e->limit && (!strict || clock<=e->connector->base.display_info.max_tmds_clock)?MODE_OK:MODE_BAD;}
static bool hdmi_bpc_possible(const struct intel_crtc_state *s,int bpc);
@@FUNCTIONS@@
static bool hdmi_bpc_possible(const struct intel_crtc_state *s,int bpc)
{return intel_hdmi_source_bpc_possible(&display_state,bpc) &&
 intel_hdmi_sink_bpc_possible(&s->connector->base,bpc,s->has_hdmi_sink,s->sink_format);}
static int native_config(struct intel_encoder *encoder,struct intel_crtc_state *pipe_config,
 const struct drm_connector_state *conn_state) {
 struct intel_display *display=&display_state;
 struct intel_connector *connector=encoder->connector;
 int ret;
 @@TRANSPORT@@
 @@ADMISSION@@
 @@FINAL_GUARD@@
 return ret;
}
int main(void) {
 struct intel_connector connector={.base={.display_info={.hdmi={1},.edid_hdmi_rgb444_dc_modes=1,
   .max_tmds_clock=600000,.also420=true},.ycbcr_420_allowed=true}};
 struct hdr_output_metadata hdr={0,{0,HDMI_EOTF_SMPTE_ST2084}};
 struct drm_property_blob blob={sizeof(hdr),&hdr};
 struct intel_digital_connector_state state={.base={&connector.base,10,DRM_MODE_COLORIMETRY_BT2020_RGB,&blob},
   .dv_hdr10_deep_color=true};
 struct intel_encoder encoder={600000,&connector};
 for(int scenario=0;scenario<31;++scenario) {
  struct intel_connector saved_connector=connector;
  struct intel_digital_connector_state saved_state=state;
  struct intel_crtc_state stream={.hw={.adjusted_mode={594000,0}},.pipe_bpp=30,
    .has_hdmi_sink=true,.connector=&connector};
  int want_result=0;enum intel_output_format want_format=INTEL_OUTPUT_FORMAT_YCBCR420;
  int want_bpp=30;
  if(scenario==1) {stream.hw.adjusted_mode.crtc_clock=297000;want_format=INTEL_OUTPUT_FORMAT_RGB;}
  if(scenario==2) {state.dv_hdr10_deep_color=false;want_format=INTEL_OUTPUT_FORMAT_RGB;want_bpp=24;}
  if(scenario==3) {state.dv_lab_standard=true;want_result=-EINVAL;}
  if(scenario==4) {connector.base.display_info.hdmi.y420_dc_modes=0;want_result=-EINVAL;}
  if(scenario==5) {connector.base.display_info.also420=false;want_result=-EINVAL;}
  if(scenario==6) {connector.base.ycbcr_420_allowed=false;want_result=-EINVAL;}
  if(scenario==7) {connector.base.display_info.max_tmds_clock=340000;want_result=-EINVAL;}
  if(scenario==8) {encoder.limit=340000;want_result=-EINVAL;}
  if(scenario==9) {connector.base.display_info.only420=true;connector.base.display_info.also420=false;}
  if(scenario==10) {connector.base.display_info.only420=true;connector.base.display_info.hdmi.y420_dc_modes=0;want_result=-EINVAL;}
  if(scenario==11) {state.base.hdr_output_metadata=NULL;want_result=-EINVAL;}
  if(scenario==12) {state.base.max_requested_bpc=8;want_result=-EINVAL;}
  if(scenario==13) {stream.pipe_bpp=24;want_result=-EINVAL;}
  if(scenario==14) {display_state.version=11;}
  if(scenario==15) {state.dv_hdr10_deep_color=false;state.dv_lab_standard=true;want_format=INTEL_OUTPUT_FORMAT_RGB;want_bpp=24;}
  if(scenario==16) {hdr.hdmi_metadata_type1.eotf=1;want_result=-EINVAL;}
  if(scenario==17) {display_state.version=10;want_result=-EINVAL;}
  if(scenario==18) {display_state.version=9;want_result=-EINVAL;}
  if(scenario>=19 && scenario<=23) {
   display_state.version=10;state.base.max_requested_bpc=12;stream.pipe_bpp=36;
   connector.base.display_info.edid_hdmi_rgb444_dc_modes=DRM_EDID_HDMI_DC_36;
   connector.base.display_info.hdmi.y420_dc_modes=DRM_EDID_YCBCR420_DC_36;
   want_bpp=36;
  }
  if(scenario==20) {stream.hw.adjusted_mode.crtc_clock=297000;want_format=INTEL_OUTPUT_FORMAT_RGB;}
  if(scenario==21) {connector.base.display_info.hdmi.y420_dc_modes=0;want_result=-EINVAL;}
  if(scenario==22) {connector.base.display_info.max_tmds_clock=400000;want_result=-EINVAL;}
  if(scenario==23) {display_state.version=9;want_result=-EINVAL;}
  if(scenario>=24 && scenario<=25) {state.dv_hdr10_deep_color=false;state.base.hdr10plus_metadata=&state;}
  if(scenario==25) {display_state.version=10;state.base.max_requested_bpc=12;stream.pipe_bpp=36;
   connector.base.display_info.hdmi.y420_dc_modes=DRM_EDID_YCBCR420_DC_36;want_bpp=36;}
  if(scenario>=26 && scenario<=29){
   display_state.version=9;display_state.platform.kabylake=true;state.base.max_requested_bpc=12;
   stream.pipe_bpp=36;stream.hw.adjusted_mode.crtc_clock=148500;encoder.limit=300000;
   connector.base.display_info.max_tmds_clock=300000;
   connector.base.display_info.edid_hdmi_rgb444_dc_modes=DRM_EDID_HDMI_DC_36;
   want_format=INTEL_OUTPUT_FORMAT_RGB;want_bpp=36;
  }
  if(scenario==27){state.base.max_requested_bpc=10;want_result=-EINVAL;}
  if(scenario==28){connector.base.display_info.edid_hdmi_rgb444_dc_modes=0;want_result=-EINVAL;}
  if(scenario==29){stream.hw.adjusted_mode.crtc_clock=297000;
   connector.base.display_info.also420=false;want_result=-EINVAL;}
  if(scenario==30){
   state.lldv_format=1;state.dv_hdr10_deep_color=false;state.base.hdr_output_metadata=NULL;
   state.base.max_requested_bpc=8;connector.base.display_info.also420=false;
   connector.base.display_info.max_tmds_clock=340000;want_result=-EINVAL;
  }
  int clock=stream.hw.adjusted_mode.crtc_clock;
  int result=native_config(&encoder,&stream,&state.base);
  if(result!=want_result) return 20+scenario;
  if(!result && (stream.sink_format!=want_format || stream.pipe_bpp!=want_bpp)) return 50+scenario;
  assert(stream.hw.adjusted_mode.crtc_clock==clock);
  connector=saved_connector;state=saved_state;encoder.limit=600000;display_state.version=12;
  display_state.platform.kabylake=false;
  hdr.hdmi_metadata_type1.eotf=HDMI_EOTF_SMPTE_ST2084;
 }
}
'''
        functions = [function(policy, 'intel_dvbridge_hdr_retry_420')]
        functions.extend(function(source, name) for name in names)
        code = code.replace('struct intel_hdmi *intel_hdmi =', 'struct intel_encoder *intel_hdmi =')
        functions = [f.replace('struct intel_hdmi *intel_hdmi =',
                               'struct intel_encoder *intel_hdmi =') for f in functions]
        self.compile_run(code.replace('@@FUNCTIONS@@', '\n'.join(functions))
                         .replace('@@TRANSPORT@@', transport)
                         .replace('@@ADMISSION@@', admission)
                         .replace('@@FINAL_GUARD@@', final_guard))


if __name__ == '__main__':
    unittest.main()
