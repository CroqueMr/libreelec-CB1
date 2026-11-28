# CB1 builds

## CB1-R1.2.0 x86-64 image

Use the [pinned build source](https://github.com/CroqueMr/libreelec-CB1/tree/225e0f7951dd41c4616e95f4e744463c4bf58534) on a non-root Linux x86-64 build host with LibreELEC dependencies. The Generic recipes fetch the exact CB1 1.2, Kodi, FFmpeg, libplacebo and libbluray revisions and verify their archives. The bundled CB1 snapshot remains a historical staging input, not the current linked engine. See [versions and component sources](VERSIONS.md).

```sh
python3 scripts/cb1-stage.py --check
PROJECT=Generic ARCH=x86_64 OFFICIAL=no make image
```

The default output files are `LibreELEC-x86_64-13.0-CB1-R1.2.0.img.gz` and `LibreELEC-x86_64-13.0-CB1-R1.2.0.tar`. The internal platform remains `Generic.x86_64`. `/etc/os-release` reports `CB1-R1.2.0` and `Community & CroqueMr`. The matched driver stacks are NVIDIA R620 620.73.04 and R580 580.196.07.

## Optional externalhelper release asset

Build the optional `externalhelper` add-on from the same source revision as
the Generic x86_64 image. It includes the private wlroots library that
restores the HDMI `max bpc` setting after an external Wayland session.

```sh
PROJECT=Generic ARCH=x86_64 ADDON_OVERWRITE=yes ./scripts/create_addon externalhelper
```

For the current 12.80.8 add-on ABI, use
`target/addons/12.80.8/Generic/x86_64/tools.externalhelper/tools.externalhelper-12.80.8.14.zip`.
Check the ZIP integrity, the version in `tools.externalhelper/addon.xml` and the
presence of `tools.externalhelper/lib.private/libwlroots-0.20.so`.

Stage the ZIP as a separate release asset next to the Generic image and
update TAR. Regenerate `SHA256SUMS` for the staged assets and verify it before
publishing. Users can install the matching ZIP with **Install from zip file**
in Kodi.

## Historical R1.0.0 Stable image

From the Stable source commit, stage the bundled sources and use LibreELEC's
version overrides for the Generic image.

```sh
python3 CB1/tools/verify.py
python3 scripts/cb1-stage.py
CB1_HDR10_AI=yes PROJECT=Generic ARCH=x86_64 OFFICIAL=no \
  CUSTOM_VERSION=DV-R.1.0.0-Stable BUILDER_VERSION=DV-R.1.0.0-Stable make image
```

Review `/etc/release` and `/etc/os-release` in the assembled SYSTEM. The version
and builder version both identify Stable. Keep qualification media, profiles
and diagnostic service overrides in the test environment.

## Historical R1.0.0 RC3 build

Requires a Linux x86-64 host, LibreELEC build dependencies and the complete source tree.

Published image identity: `DV-R1.0.0-RC3`. Use the synchronized RC3 sources at
`02463f318c083a585fa8b72f5a17a57fd0a477f0` for a pinned build. They retain the
published image's active sources and remove obsolete patches accidentally included
in the original source export. The original release tag and binary assets are
unchanged. The source configuration uses the logical ID `R1.0.0-RC3`.

The published [RC3 release](https://github.com/CroqueMr/libreelec-CB1/releases/tag/R1.0.0-RC3)
provides ready-to-install images and corresponding-source archives. When building
from an older source download, use the synchronized checkout above rather than
reapplying the superseded patches.

```sh
git checkout 02463f318c083a585fa8b72f5a17a57fd0a477f0
python3 CB1/tools/verify.py
python3 scripts/cb1-stage.py
CB1_HDR10_AI=yes PROJECT=Generic ARCH=x86_64 OFFICIAL=no make image
```

Staging verifies and copies the bundled CB1 sources, model and matched dependency
patches into LibreELEC's native package directories. Do not mix headers or libraries
from another version. Native recipes download the pinned upstream archives and apply
the recorded patches; this tree does not use Beta4's frozen pre-patched archives.

Supported Intel/AMD integrated and dedicated GPUs, NVIDIA GeForce GPUs and AMD
HDMI 3D use one Generic image. The image includes matched NVIDIA R615 and R580
modules, firmware and userspace; the appropriate branch is selected at boot.

The AI model under `CB1/models/l1l3/` is required for the AI circuits. Training data,
movies, extracted frames and private oracle fixtures are not release inputs.

For regression checks, use the matched-source preparation in
`.github/scripts/prepare-test-sources.sh` or set the dependency/source paths consumed
by `tests/cb1`. Engine test requirements are listed in [CB1 build](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/BUILD.md).
Hardware-dependent checks require the corresponding GPU and display route.
The CI preparation exports the matching Kodi archive as `KODI_UPSTREAM_ARCHIVE`;
native display tests also require the host libdrm development headers.

Component pins are in [versions](VERSIONS.md), `config/cb1-source-lock.json` and
`CB1/config/dependencies.json`. The model contract is in
`CB1/config/hdr10-ai-dependencies.json`. Runtime assets and applicable notices must
remain in corresponding-source exports. Rebuild hashes can vary with the toolchain,
timestamps and build paths.

## OpenGL device

The `OpenGL` device builds Kodi, libplacebo and the DV bridge against desktop
OpenGL instead of OpenGL ES:

```sh
CB1_HDR10_AI=yes PROJECT=Generic DEVICE=OpenGL ARCH=x86_64 OFFICIAL=no make image
```

Kodi's GL windowing context is generated from the DV GLES context by
`scripts/cb1-gl-winsys.py`. When the GLES context changes, run the script on a
checkout of the pinned Kodi fork and commit the difference there.
