# CB1-R1.2.0 - SDR Rendering, Playback Stability and HDMI Compatibility

## Changes since R1.1.1 RC1

### New SDR rendering circuits

- SDR to HDR10 Rendering (1,000-nit output target).
- SDR to Dolby Vision Rendering (600-nit TV-led output target).
- Native SDR remains the default. Both new circuits can be selected in Settings and through Quick Switch when available.
- Updated the CB1 engine to 1.2, with revised version identifiers for the updated circuits.

### Dolby Vision and HDR

- Improved Dolby Vision MEL recovery and HEVC decoder continuity when scaling lists change.
- Improved LLDV colour-volume handling, including bright saturated colours.
- Improved LLDV compatibility with inconsistent display EDID primaries. Significant gamut adjustments are reported; minor EDID rounding no longer raises a warning.
- Improved 1080p Adaptive HDR Mapping and support for 10-bit SDR upscaling.
- Consistent Dolby Vision Player-led output naming in Quick Switch and Player Information.

### Playback, Blu-ray and audio

- Improved playback smoothness during SDR conversion with subtitles and the playback controls open.
- Fixed GUI composition when switching back to native SDR during playback, and improved video screensaver and windowed video support.
- Fixed standard screenshots for SDR to Dolby Vision Rendering while preserving native PQ captures.
- Improved Blu-ray demuxer and menu playback continuity.
- Improved audio passthrough resynchronization and playback diagnostics.

### HDMI and graphics drivers

- Restored the previous Intel HDMI path while retaining Linux 7.4-rc4 and the opt-in AMD FRL work, to address reported signal loss.
- Added a targeted HDR10 scanout format correction for NVIDIA Pascal (GTX 10 series).
- Improved HDMI Auto bit-depth selection and restoration after a clean Kodi restart, including AMD wide-gamut SDR output.
- Improved HDMI connector diagnostics and GPU utilization reporting.
- Added Vulkan support for external applications and add-ons on AMD, Intel and NVIDIA. Kodi retains its existing playback renderer. Desktop OpenGL integration is also included.

### Add-ons and diagnostics

- Matching optional externalhelper ZIP included.
- Improved playback and HDMI diagnostic information to help investigate hardware-specific issues.

## Compatibility notes

- Tested on Intel N100 and AMD Ryzen 5 7430U, including live circuit changes, 24 fps SDR conversions, screenshot output and installation of the complete image. 4K60 SDR conversion can exceed the available GPU performance on the N100, especially with on-screen controls; native SDR remains available.
- If an older build or an unclean shutdown leaves an explicit HDMI bit-depth limit behind, a full device restart may still be needed to restore the driver default.
- The Alien Director's Cut seamless join was confirmed on AMD; its exact counterpart on N100 remains to be qualified.

Intel HDMI signal loss, GTX 10 series HDR10 and JVC BT.2020 tint still need confirmation on the affected hardware. The new Intel experimental FRL path is disabled by removal of the experimental patch; AMD FRL remains opt-in. No claim of 4K120 Dolby Vision support.

Thanks to **sunlollyking** for the desktop OpenGL contribution, **Snuffpig** for GPU telemetry and scaling diagnostics, upstream Kodi contributors, and everyone who reports issues, shares logs and tests fixes. Your feedback helps improve CB1, LibreELEC and Kodi for everyone.

CB1 builds on [LibreELEC](https://github.com/LibreELEC/LibreELEC.tv) and [Kodi](https://github.com/xbmc/xbmc). Applicable fixes will be submitted upstream so everyone can benefit. [Source lock](https://github.com/CroqueMr/libreelec-CB1/blob/225e0f7951dd41c4616e95f4e744463c4bf58534/config/cb1-source-lock.json).

### Downloads

Use the `.img.gz` for a fresh install and the `.tar` for an update. Install the optional externalhelper ZIP using Kodi's **Install from zip file**. Verify downloads against `SHA256SUMS`.

[Build source](https://github.com/CroqueMr/libreelec-CB1/tree/225e0f7951dd41c4616e95f4e744463c4bf58534)
