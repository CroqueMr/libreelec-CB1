# Versions and source repositories

The **CB1-R1.2.0** integration uses the following component versions. The tested image was built from [225e0f79](https://github.com/CroqueMr/libreelec-CB1/tree/225e0f7951dd41c4616e95f4e744463c4bf58534). Its build sources are pinned in the native LibreELEC package recipes; the retained `CB1/` snapshot is not the linked CB1 1.2 engine.

| Component | Version / source |
| --- | --- |
| Integration | [CB1-R1.2.0](RELEASE-R1.2.0.md) |
| LibreELEC | [13 Beta 1 (12.95.1)](https://github.com/LibreELEC/LibreELEC.tv/tree/3a98afddff5b38120e34487da8851558425b06cf) |
| Kodi | [22.0 RC2](https://github.com/CroqueMr/xbmc/tree/3e2c54f14955b78c7ee83e4d22a2553bc3fbedbf) |
| CB1 engine | [1.2](https://github.com/CroqueMr/CB1/tree/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb) |
| Linux | 7.4-rc4 with CB1 display-driver changes |
| FFmpeg | [9.0.2](https://github.com/CroqueMr/FFmpeg/tree/2f9127b03c4b212bdcc1b052b5b559d06ebbe805) |
| libplacebo | [7.387.0](https://github.com/CroqueMr/libplacebo/tree/f7d8a9b9a0a80c7f21fd1c44849b92e3bcca847f) |
| libbluray | [1.5.1](https://github.com/CroqueMr/libbluray-cb1/tree/7b18d8f440c85fa4f96d4c65daba5c4dffcfd720) |
| Mesa | 26.3.0 |
| Intel Media Driver | 26.3.5 |
| libva | 2.24.1 |
| NVIDIA, Turing and newer | R620 620.73.04 |
| NVIDIA, Pascal | R580 580.196.07; automatically selected in the same image |
| NVIDIA EGL-GBM | 1.1.4 (library ABI 1.1.3) |

CB1 circuit versions are defined in the pinned engine and shown in Player Information. [Current circuit identifiers](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/CIRCUITS.md).

Exact version and revision metadata is in [cb1-versions.json](../../config/cb1-versions.json), with integration/staging receipts in [cb1-source-lock.json](../../config/cb1-source-lock.json). The native package recipes are the authority for the archives and hashes actually selected by the build. [Build instructions](BUILD.md).

The x86-64 release files are named `LibreELEC-x86_64-13.0-CB1-R1.2.0.img.gz` and `LibreELEC-x86_64-13.0-CB1-R1.2.0.tar`. Internal platform identity remains `Generic.x86_64` for updates. Builder: `Community & CroqueMr`.

AMD HDMI 3D changes are part of the matched Linux/Kodi sources, not a separate CB1 circuit. [3D support](3D.md).
