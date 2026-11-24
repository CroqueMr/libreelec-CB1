"""Run the AMD primary-flip packet selection and HDR10+ submission contract."""
import os
from pathlib import Path
import unittest

import test_amd_stereo_owner as stereo
from test_hdr10_transport import function


@unittest.skipUnless(os.environ.get('CB1_KERNEL_SOURCE'), 'matched kernel required')
class AMDHDMIPacketOwner(unittest.TestCase):
    source = stereo.AMDNativeStereo.source
    run_c = stereo.AMDNativeStereo.run_c

    def test_hdmi_primary_flip_preserves_owned_vendor_packets(self):
        freesync = self.source('amdgpu_dm/amdgpu_dm_freesync.c')
        helper = (function(freesync, 'amdgpu_dm_hdmi_content_owns_vsif')
                  if 'amdgpu_dm_hdmi_content_owns_vsif(' in freesync else '')
        flip = function(freesync, 'amdgpu_dm_update_freesync_state_on_stream')
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
typedef uint32_t u32;
#define __maybe_unused __attribute__((unused))
#define DRM_MODE_FLAG_3D_MASK (0x1f << 14)
#define HDMI_INFOFRAME_TYPE_VENDOR 0x81
#define HDMI_HDR10PLUS_IEEE_OUI 0x90848b
#define HDMI_FORUM_IEEE_OUI 0xc45dd8
#define HDMI_EOTF_SMPTE_ST2084 2
#define DP_HDR_SDP_EOTF_IDX 2
#define AMDGPU_FAMILY_AI 1
#define FREESYNC_TYPE_PCON_IN_WHITELIST 1
#define VRR_STATE_ACTIVE_VARIABLE 1
#define VRR_STATE_ACTIVE_FIXED 2
enum { SIGNAL_TYPE_HDMI_TYPE_A, SIGNAL_TYPE_HDMI_FRL, SIGNAL_TYPE_DISPLAY_PORT };
enum vrr_packet_type { PACKET_TYPE_VRR, PACKET_TYPE_FS_V1, PACKET_TYPE_FS_V2, PACKET_TYPE_FS_V3 };
enum color_transfer_func { TRANSFER_FUNC_UNKNOWN, TRANSFER_FUNC_PQ2084 };
struct dc_info_packet { bool valid; uint8_t hb0, hb1, hb2, sb[32]; };
struct mod_vrr_params { int state, adjust; };
struct amdgpu_device { int family, event_lock; };
struct amdgpu_crtc { struct { struct mod_vrr_params vrr_params; } dm_irq_params; };
struct dc_plane_state { int unused; };
struct dc_stream_state {
    int signal;
    bool dv_standard, allow_freesync;
    void *dm_stream_context;
    struct { unsigned h_total, v_total, hdmi_vic; } timing;
    struct dc_info_packet hdr_static_metadata, vsp_infopacket, cb1_mode_vsp_infopacket,
        vrr_infopacket, vtem_infopacket, adaptive_sync_infopacket;
};
struct amdgpu_display_manager { struct amdgpu_device *adev; void *dc, *freesync_module; };
struct amdgpu_dm_connector {
    int as_type, max_vfreq;
    bool pack_sdp_v1_3;
    struct { bool freesync_supported, replay_mode; int amd_vsdb_version; } vsdb_info;
    struct { struct { struct { bool allm; struct { bool supported; } vrr_cap; } hdmi; }
             display_info; } base;
};
struct dm_crtc_state {
    struct { struct amdgpu_crtc *crtc; struct { unsigned flags; } mode; } base;
    struct dc_stream_state *stream;
    bool freesync_vrr_info_changed;
    struct dc_info_packet vrr_infopacket, vtem_infopacket;
};
#define to_amdgpu_crtc(crtc) (crtc)
#define spin_lock_irqsave(lock, flags) ((void)(lock), (flags)=0)
#define spin_unlock_irqrestore(lock, flags) ((void)(lock), (void)(flags))
#define adev_to_drm(adev) (adev)
#define drm_dbg_driver(...) ((void)0)
#define drm_dbg_kms(...) ((void)0)
#define dc_is_dp_signal(signal) ((signal) == SIGNAL_TYPE_DISPLAY_PORT)
#define dc_is_hdmi_signal(signal) (!dc_is_dp_signal(signal))
#define mod_freesync_handle_preflip(mod, surface, stream, stamp, params) ((void)(stamp))
#define amdgpu_dm_crtc_vrr_active(state) (true)
#define mod_freesync_handle_v_update(...) ((void)0)
#define dc_stream_adjust_vmin_vmax(...) ((void)0)
#define mod_build_adaptive_sync_infopacket(...) ((void)0)
#define mod_freesync_build_vrr_infopacket(mod, stream, params, type, tf, out, pack) \
    ((out)->valid = (params)->state != 0, (void)(type), (void)(tf), (void)(pack))
#define mod_build_infopacket_vtem(stream, params, fva, out) ((out)->valid = true)
#define mod_freesync_get_freesync_enabled(params) ((params)->state != 0)
static struct dc_info_packet packet(u32 oui, unsigned marker)
{
    struct dc_info_packet result = { .valid = true, .hb0 = 0x81, .hb1 = 1, .hb2 = 4 };
    result.sb[1] = oui; result.sb[2] = oui >> 8; result.sb[3] = oui >> 16;
    result.sb[4] = marker;
    return result;
}
static void mod_build_hf_vsif_infopacket(const struct dc_stream_state *stream,
                                        struct dc_info_packet *out, bool enabled, bool value)
{ (void)stream; if (enabled) *out = packet(HDMI_FORUM_IEEE_OUI, value); }
''' + function(freesync, 'dm_dp_in_hdr_mode') + '\n' + helper + '\n' + flip + r'''
int main(void)
{
    struct amdgpu_device adev = {.family=AMDGPU_FAMILY_AI};
    struct amdgpu_display_manager dm = {.adev=&adev};
    struct amdgpu_crtc crtc = {0};
    struct amdgpu_dm_connector connector = {0};
    struct dm_crtc_state crtc_state = {.base.crtc=&crtc};
    struct dc_stream_state stream = {.dm_stream_context=&connector,
        .timing.h_total=4400, .timing.v_total=2250};
    connector.base.display_info.hdmi.allm = true;
    connector.base.display_info.hdmi.vrr_cap.supported = true;
    crtc_state.stream = &stream;
    for (stream.signal=SIGNAL_TYPE_HDMI_TYPE_A; stream.signal<=SIGNAL_TYPE_HDMI_FRL; ++stream.signal) {
        const struct dc_info_packet cases[] = {packet(0xd046, 1),
            packet(0xc03, 2), packet(HDMI_HDR10PLUS_IEEE_OUI, 3),
            packet(0xc03, 4), packet(0xc03, 5)};
        for (unsigned i=0; i<sizeof(cases)/sizeof(*cases); ++i) {
            stream.dv_standard = i < 2;
            crtc_state.base.mode.flags = i == 3 ? 1 << 14 : 0;
            stream.timing.hdmi_vic = i == 4 ? 1 : 0;
            stream.vsp_infopacket = cases[i];
            for (int active=0; active<=1; ++active) {
                crtc.dm_irq_params.vrr_params.state = active;
                amdgpu_dm_update_freesync_state_on_stream(&dm, &crtc_state, &stream, 0, 0);
                assert(!memcmp(&stream.vsp_infopacket, &cases[i], sizeof(cases[i])));
                if (stream.dv_standard)
                    assert(!stream.vtem_infopacket.valid && !stream.vrr_infopacket.valid);
            }
        }
        stream.timing.hdmi_vic = 0;
        stream.cb1_mode_vsp_infopacket = packet(0xc03, 0);
        stream.vsp_infopacket = stream.cb1_mode_vsp_infopacket;
        amdgpu_dm_update_freesync_state_on_stream(&dm, &crtc_state, &stream, 0, 0);
        assert(stream.vsp_infopacket.sb[1] == 0xd8);
        crtc.dm_irq_params.vrr_params.state = 0;
        amdgpu_dm_update_freesync_state_on_stream(&dm, &crtc_state, &stream, 0, 0);
        assert(!memcmp(&stream.vsp_infopacket, &stream.cb1_mode_vsp_infopacket,
                       sizeof(stream.vsp_infopacket)));
    }
}
''')

    def test_hdr10plus_packet_only_flip_reaches_display_core(self):
        source = self.source('amdgpu_dm/amdgpu_dm.c')
        owner = function(source, 'amdgpu_dm_commit_planes')
        start = owner.index('for_each_new_connector_in_state', owner.index('Update the planes if changed'))
        end = owner.index('if (new_pcrtc_state->mode_changed)', start)
        submission = owner[owner.index('update_planes_and_stream_adapter', end):].split(';', 1)[0]
        with self.subTest('packet changes mark the stream update required'):
            self.assertIn('stream_update_needed = true;', owner[start:end])
        with self.subTest('display core receives that conditional update'):
            self.assertIn('stream_update_needed ? &bundle->stream_update : NULL', submission)


    def test_frl_is_opt_in_without_changing_other_display_defaults(self):
        kernel = Path(os.environ['CB1_KERNEL_SOURCE'])
        driver = (kernel / 'drivers/gpu/drm/amd/amdgpu/amdgpu_drv.c').read_text()
        default = driver.split('uint amdgpu_dc_feature_mask = ', 1)[1].split(';', 1)[0]
        self.assertEqual(default, 'DC_MULTI_MON_PP_MCLK_SWITCH_MASK')

    def test_static_hdr_refresh_reaches_reused_hdmi_backends_only(self):
        source = self.source('dc/hwss/dce110/dce110_hwseq.c')
        owner = function(source, 'dce110_apply_ctx_to_hw')
        start = owner.index('if (resource_is_pipe_type', owner.index('A reused HDMI backend'))
        end = owner.index('continue;', start)
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
enum { TMDS, FRL, DP, OTG_MASTER };
struct dc_stream_state {
    struct { bool valid; unsigned content; } hdr_static_metadata;
    bool use_dynamic_meta, dpms_off;
    int signal;
};
struct pipe_ctx { struct dc_stream_state *stream; };
static bool dc_is_hdmi_signal(int signal) { return signal == TMDS || signal == FRL; }
static bool resource_is_pipe_type(struct pipe_ctx *pipe, int type)
{ (void)pipe; return type == OTG_MASTER; }
static unsigned built, sent;
static void resource_build_info_frame(struct pipe_ctx *pipe) { (void)pipe; ++built; }
static void send_info_frame(struct pipe_ctx *pipe) { (void)pipe; ++sent; }
''' + function(source, 'dce110_static_hdr_packet_changed') + r'''
static void update(struct pipe_ctx *pipe_ctx_old, struct pipe_ctx *pipe_ctx)
{
    struct { struct { void (*update_info_frame)(struct pipe_ctx *); } hwss; } core =
        { .hwss.update_info_frame = send_info_frame }, *dc = &core;
''' + owner[start:end] + r'''
}
int main(void)
{
    for (int signal = TMDS; signal <= DP; ++signal) {
        const unsigned expected = signal != DP;
        struct dc_stream_state old = { .signal = signal }, next = old;
        struct pipe_ctx before = { &old }, after = { &next };
        built = sent = 0;
        next.hdr_static_metadata.valid = true;
        next.hdr_static_metadata.content = 1;
        update(&before, &after);
        assert(built == expected && sent == expected);
        old = next;
        update(&before, &after);
        assert(sent == expected);
        next.hdr_static_metadata.content = 2;
        update(&before, &after);
        assert(sent == 2 * expected);
        old = next;
        next.use_dynamic_meta = true;
        update(&before, &after);
        assert(sent == 3 * expected);
    }
}
''')
