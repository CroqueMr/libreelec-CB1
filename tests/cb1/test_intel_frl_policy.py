"""Run Intel FRL admission and clock routing from the packaged driver."""

import os
from pathlib import Path
import unittest

import test_hdr10_transport as transport


@unittest.skipUnless(os.environ.get('CB1_KERNEL_SOURCE'), 'matched kernel required')
class IntelFRLPolicy(unittest.TestCase):
    def setUp(self):
        self.display = (Path(os.environ['CB1_KERNEL_SOURCE']) /
                        'drivers/gpu/drm/i915/display')

    def test_native_frl_requires_opt_in_and_bounded_link_capabilities(self):
        source = (self.display/'intel_hdmi.c').read_text()
        owners = ('intel_hdmi_frl_rate_cap', 'intel_hdmi_frl_enabled',
                  'intel_hdmi_frl_mode_allowed', 'get_next_frl_rate')
        code = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#define HAS_HDMI_FRL(display) ((display)->capable)
#define READ_ONCE(value) (value)
#define min(a,b) ((a) < (b) ? (a) : (b))
#define ARRAY_SIZE(value) ((int)(sizeof(value) / sizeof(*(value))))
#define DRM_MODE_FLAG_DBLCLK (1 << 0)
#define DRM_MODE_FLAG_DBLSCAN (1 << 1)
#define DRM_MODE_FLAG_INTERLACE (1 << 2)
#define DRM_MODE_FLAG_3D_MASK (1 << 3)
#define DRM_DP_DUAL_MODE_NONE 0
struct intel_display { bool capable; struct { bool enable_hdmi_frl; } params; };
struct intel_encoder { struct intel_display *display; bool typec; };
struct intel_hdmi {
    int max_frl_rate;
    bool has_sink_hdmi_21;
    struct { int rate_cap; } frl;
    struct { int type; } dp_dual_mode;
};
struct intel_digital_port { struct intel_encoder base; struct intel_hdmi hdmi; };
struct drm_display_mode { int clock, flags; };
static struct intel_digital_port port;
#define hdmi_to_dig_port(hdmi) (&port)
#define to_intel_display(encoder) ((encoder)->display)
#define intel_encoder_is_tc(encoder) ((encoder)->typec)
@@OWNERS@@
int main(void)
{
    struct intel_display intel = { .capable = true };
    port.base.display = &intel;
    struct intel_hdmi *hdmi = &port.hdmi;
    hdmi->max_frl_rate = 48;
    hdmi->frl.rate_cap = 40;
    hdmi->has_sink_hdmi_21 = true;
    assert(!intel_hdmi_frl_enabled(hdmi));
    intel.params.enable_hdmi_frl = true;
    assert(intel_hdmi_frl_enabled(hdmi));
    assert(intel_hdmi_frl_rate_cap(hdmi) == 40);
    hdmi->max_frl_rate = 32;
    assert(intel_hdmi_frl_rate_cap(hdmi) == 32);
    hdmi->frl.rate_cap = 0;
    assert(intel_hdmi_frl_enabled(hdmi) && !intel_hdmi_frl_rate_cap(hdmi));
    hdmi->frl.rate_cap = 18;
    port.base.typec = true;
    assert(!intel_hdmi_frl_enabled(hdmi));
    port.base.typec = false;
    hdmi->dp_dual_mode.type = 1;
    assert(!intel_hdmi_frl_enabled(hdmi));
    hdmi->dp_dual_mode.type = DRM_DP_DUAL_MODE_NONE;
    hdmi->has_sink_hdmi_21 = false;
    assert(!intel_hdmi_frl_enabled(hdmi));
    assert(get_next_frl_rate(48) == 40 && get_next_frl_rate(18) == 9 &&
           get_next_frl_rate(9) == 0);

    struct drm_display_mode mode = { .clock = 1188000 };
    assert(intel_hdmi_frl_mode_allowed(&mode, true));
    assert(!intel_hdmi_frl_mode_allowed(&mode, false));
    mode.flags = DRM_MODE_FLAG_3D_MASK;
    assert(!intel_hdmi_frl_mode_allowed(&mode, true));
    mode.flags = 0;
    mode.clock = 600000;
    assert(!intel_hdmi_frl_mode_allowed(&mode, true));
}
'''
        transport.HDR10Transport.compile_run(self, code.replace('@@OWNERS@@', '\n'.join(
            transport.function(source, owner) for owner in owners)))
        self.assertIn('param(bool, enable_hdmi_frl, false, 0)',
                      (self.display/'intel_display_params.h').read_text())

    def test_clock_identity_and_retry_keep_tmds_separate(self):
        ddi = (self.display/'intel_ddi.c').read_text()
        selected_clock = transport.function(ddi, 'intel_ddi_link_symbol_clock')
        code = r'''
#include <assert.h>
#include <stdbool.h>
#define DIV_ROUND_CLOSEST(n, d) (((n) + (d)/2) / (d))
struct intel_encoder { bool dp; };
#define intel_encoder_is_dp(encoder) ((encoder)->dp)
static int intel_dp_link_symbol_clock(int clock) { return clock / 10; }
@@CLOCK@@
int main(void)
{
    struct intel_encoder encoder = {0};
    for (int clock = 300000; clock <= 600000; clock += 300000) {
        assert(intel_ddi_link_symbol_clock(&encoder, clock, false) == clock);
        assert(intel_ddi_link_symbol_clock(&encoder, clock, true) ==
               DIV_ROUND_CLOSEST(clock * 10, 18));
    }
    encoder.dp = true;
    assert(intel_ddi_link_symbol_clock(&encoder, 540000, false) == 54000);
}
'''
        transport.HDR10Transport.compile_run(self, code.replace('@@CLOCK@@', selected_clock))
        enable = transport.function(ddi, 'intel_ddi_enable_hdmi')
        self.assertIn('intel_connector_queue_modeset_retry_work(intel_connector)', enable)
        reset = transport.function(ddi, 'intel_hdmi_reset_link')
        self.assertLess(reset.index('if (crtc_state->frl.enable)'),
                        reset.index('drm_scdc_readb'))
        for phy in ('intel_lt_phy.c', 'intel_cx0_phy.c'):
            self.assertIn('crtc_state->frl.enable ?', (self.display/phy).read_text())
