# CB1-R1.2.0 documentation

See the [project README](../../README.md) for rendering circuits by source, HDMI compatibility and hardware recommendations. The current image integrates the pinned CB1 1.2 and upstream component forks; [versions and source repositories](VERSIONS.md) identify the exact build sources.

## Playback

| Page | Content |
| --- | --- |
| [Features and downloads](../../README.md) | Profiles, rendering modes, captures and installation |
| [Hardware](HARDWARE.md) | Supported Intel, AMD and NVIDIA GPU families |
| [Image quality and performance](PERFORMANCE-GUIDE.md) | Reference vs Master Reference, video upscalers and recommended hardware |
| [Historical RC3 benchmark](BENCHMARKS.md) | Standalone published RC3 results on Intel N100 and AMD Ryzen 5 7430U |
| [Driver/output matrix](DRIVER-COVERAGE.md) | Dolby Vision V1/V2, HDR10/HLG and HDR10+ by driver |
| [AMD HDMI 3D](3D.md) | MVC, frame packing, SBS/TAB and native Kodi setup |
| [Playback settings](PLAYBACK.md) | Source defaults, SDR/HDR/DV circuits, TV profile, FEL upscaling and O controls |
| [Processing](PROCESSING.md) | Mode behavior, metadata use and output limits |
| [LLDV](LLDV.md) | EDID target, HDMI format selection and HDR10 output |
| [Native playback](NATIVE-PLAYBACK.md) | Native Kodi paths and HDR10+ fallback |
| [Audio information](AUDIO-INFORMATION.md) | Source codec/Atmos details and actual PCM, passthrough or transcoded output |
| [CM2.9 to CM4 controls](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/CM4-APPEND.md) | Optional metadata conversion, Auto/Auto 2 and independent L2 removal |
| [Diagnostics](DIAGNOSTICS.md) | Issue reports and bounded playback logs |
| [CB1-R1.2.0 release notes](RELEASE-R1.2.0.md) | SDR rendering, playback stability, HDMI and compatibility |
| [Historical R1.0.0 RC3 release notes](RELEASE.md) | Earlier Dolby Vision, HDR10+, playback, menus, hardware and audio changes |

## Engine and integration

| Page | Content |
| --- | --- |
| [CB1 1.2](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/README.md) | Pinned engine boundary and source layout |
| [Algorithms](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/ALGORITHMS.md) | Curves, variables, metadata and color processing |
| [Circuit versions](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/CIRCUITS.md) | Current end-to-end identifiers |
| [Master Reference](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/MASTER-REFERENCE.md) | Representation, reconstruction and fidelity contract |
| [HDR10+](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/HDR10PLUS.md) | Native metadata, DV conversion and output transport |
| [FEL upscaling](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/FEL-VAAPI.md) | VAAPI, GPU fallback and source lifetimes |
| [Transport](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/SOURCE-TRANSPORT.md) | Source-domain packing and shared optimizations |
| [Player API](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/API.md) | Preparation, accepted output and resource ownership |
| [Kodi information](KODI-INFORMATION.md) | Native source facts and accepted-output labels |
| [AI model](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/models/l1l3/README.md) | Included LightGBM bundle and runtime contract |
| [Creative mapping](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/CREATIVE-MAPPING.md) | CM2.9/CM4 implementation and attribution |
| [Creative integration](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/CREATIVE-INTEGRATION.md) | Policy and metadata transaction contracts |
| [CM4 qualification](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/CM4-QUALIFICATION.md) | Applied controls and qualification limits |
| [Historical Master / Standard comparison](../reports/master-reference-vs-standard-2026-10-21.md) | Beta5 measurements; Standard is now named Reference |

## Build and licenses

[Image build](BUILD.md) · [Engine build](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/BUILD.md)
· [Versions](VERSIONS.md) · [Licensing and credits](LICENSING.md)
· [Engine licensing](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/LICENSING.md)
· [Original LibreELEC README](UPSTREAM.md).

[Archived numerical contracts](https://github.com/CroqueMr/CB1/blob/10b8a83944be871e8973dbcaf7f8b93a69e3d4bb/docs/REFERENCE-CONTRACTS.md) retain earlier
experiments; they do not define the current playback menu.

Archived release notes: [RC2](RELEASE-RC2.md) · [Beta5](RELEASE-BETA5.md) · [Beta4](RELEASE-BETA4.md).
