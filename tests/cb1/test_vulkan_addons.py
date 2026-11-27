# SPDX-License-Identifier: MIT
"""Vulkan is an add-on capability, not a new CB1 playback backend."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


def profile(force_off=False, drivers=""):
    script = r'''
set -e
ROOT=$PWD
PROJECT=Generic TARGET_ARCH=x86_64 ARCH=x86_64 DEVICE=Generic
NOONEXIT=yes USE_REUSABLE=no MTADDONBUILD=no TARGET_FEATURES=sse
CB1_HDR10_AI=yes KODI_BLURAY_SUPPORT=yes
. config/functions
. projects/Generic/devices/OpenGLES/options
if [ "$1" = off ]; then VULKAN=no; fi
. config/graphic
if [ -n "$2" ]; then GRAPHIC_DRIVERS="$2"; fi
get_graphicdrivers

# These lookups are unrelated to graphics selection and only supply build paths.
get_build_dir() { printf '/build/%s\n' "$1"; }
get_pkg_directory() { printf '/packages/%s\n' "$1"; }
get_pkg_version() { printf 'test-version\n'; }
get_pkg_variable() { printf 'test-hash\n'; }
get_target_linker() { printf 'bfd\n'; }
emit() { printf '%s\t%s\n' "$1" "$2"; }

emit provider "$VULKAN"
emit video "$OPENGL_SUPPORT $OPENGLES_SUPPORT $DISPLAYSERVER $VAAPI_SUPPORT $GALLIUM_DRIVERS"
(
  . packages/graphics/mesa/package.mk
  emit mesa_options "$PKG_MESON_OPTS_TARGET"
  emit mesa_deps "$PKG_DEPENDS_TARGET"
  PKG_DIR="$ROOT/packages/graphics/mesa" PROJECT_DIR="$ROOT/projects"
  emit mesa_stamp "$(calculate_stamp)"
)
for package in nvidia nvidia-pascal; do (
  . "packages/graphics/$package/package.mk"
  emit "$package-deps" "$PKG_DEPENDS_TARGET"
); done
(
  . packages/mediacenter/kodi/package.mk
  configure_package
  emit kodi "$PKG_CMAKE_OPTS_TARGET"
  emit kodi_deps "$PKG_DEPENDS_TARGET"
)
(
  . packages/addons/addon-depends/multimedia-tools-depends/libplacebo/package.mk
  emit placebo "$PKG_MESON_OPTS_TARGET"
  emit placebo_deps "$PKG_DEPENDS_TARGET"
)
(
  . packages/multimedia/ffmpeg/package.mk
  emit ffmpeg "$PKG_FFMPEG_HWACCEL $PKG_FFMPEG_VAAPI $PKG_FFMPEG_V4L2"
  emit ffmpeg_deps "$PKG_DEPENDS_TARGET"
)
'''
    result = subprocess.run(["bash", "-c", script, "profile", "off" if force_off else "default", drivers],
                            cwd=ROOT, check=True, capture_output=True, text=True)
    return {key: value.split() for key, value in (line.split("\t", 1)
            for line in result.stdout.splitlines())}


class VulkanAddonsTests(unittest.TestCase):
    def test_mesa_stamp_tracks_effective_vulkan_drivers(self):
        disabled = profile(force_off=True)["mesa_stamp"]
        enabled = profile()["mesa_stamp"]
        intel_only = profile(drivers="iris")["mesa_stamp"]
        self.assertNotEqual(disabled, enabled)
        self.assertNotEqual(enabled, intel_only)
        self.assertEqual(enabled, profile()["mesa_stamp"])

    def test_generic_exposes_vulkan_without_changing_playback_backends(self):
        before, after = profile(force_off=True), profile()
        self.assertEqual(after["provider"], ["vulkan-loader"])
        self.assertEqual(after["video"], before["video"])
        self.assertEqual(after["mesa_options"], [
            "-Dvulkan-drivers=amd,intel" if option == "-Dvulkan-drivers=" else option
            for option in before["mesa_options"]])
        self.assertEqual(set(after["mesa_deps"]) - set(before["mesa_deps"]),
                         {"vulkan-loader", "vulkan-tools", "ply:host"})
        for key in ("nvidia-deps", "nvidia-pascal-deps"):
            self.assertEqual(set(after[key]) - set(before[key]), {"vulkan-loader", "vulkan-tools"})
            self.assertFalse(set(before[key]) - set(after[key]))
        for key in ("kodi", "kodi_deps", "placebo", "placebo_deps", "ffmpeg_deps"):
            self.assertEqual(after[key], before[key], key)
        self.assertIn("-DAPP_RENDER_SYSTEM=gles", after["kodi"])
        self.assertIn("-DCORE_PLATFORM_NAME=gbm", after["kodi"])
        self.assertIn("-DENABLE_DVBRIDGE=ON", after["kodi"])
        self.assertIn("-DCB1_ENABLE_HDR10_AI=ON", after["kodi"])
        self.assertIn("-Dvulkan=disabled", after["placebo"])
        self.assertEqual(after["ffmpeg"], [before["ffmpeg"][0], "--disable-vulkan", *before["ffmpeg"][1:]])

    def test_nvidia_vulkan_manifests_resolve_in_each_selected_branch(self):
        for recipe, branch, version in (("nvidia", "r620", "620.73.04"),
                                        ("nvidia-pascal", "r580", "580.196.07")):
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                payload = base / "payload"
                for name in ("firmware", "kernel"):
                    (payload / name).mkdir(parents=True)
                files = ["LICENSE", "10_nvidia.json", "10_nvidia_wayland.json",
                         "libnvidia-egl-wayland.so.1.1.20", "nvidia-smi",
                         "nvidia-application-profiles-" + version + "-rc",
                         "firmware/gsp_test.bin", "firmware/ucodes_test.bin"]
                files += [name + "." + version for name in (
                    "libnvidia-allocator.so", "libEGL_nvidia.so", "libnvidia-eglcore.so",
                    "libnvidia-glsi.so", "libGLESv2_nvidia.so", "libcuda.so", "libnvcuvid.so",
                    "libnvidia-gpucomp.so", "libnvidia-tls.so", "libnvidia-ml.so",
                    "libnvidia-glvkspirv.so", "libnvidia-present.so")]
                files += ["kernel/" + name + ".ko" for name in
                          ("nvidia", "nvidia-modeset", "nvidia-drm", "nvidia-uvm")]
                for name in files:
                    (payload / name).touch()
                (base / "licenses").mkdir()
                (base / "licenses/LicenseRef-NVIDIA-Driver-License-Agreement.txt").touch()
                (payload / "nvidia_icd.json").write_text(json.dumps({
                    "ICD": {"library_path": "libGLX_nvidia.so.0"}}))
                (payload / "nvidia_layers.json").write_text(json.dumps({"layers": [
                    {"library_path": "libGLX_nvidia.so.0"},
                    {"library_path": "libnvidia-present.so." + version,
                     "enable_environment": {"NVPRESENT_ENABLE_SMOOTH_MOTION": "1"}}]}))
                subprocess.run(["bash", "-ec", r'''
ROOT=$PWD VULKAN_SUPPORT=yes VULKAN=vulkan-loader
. "packages/graphics/$1/package.mk"
ROOT=$2 INSTALL=$2/install
get_full_firmware_dir() { echo usr/lib/kernel-overlays/$1/lib/firmware; }
get_full_module_dir() { echo usr/lib/kernel-overlays/$1/lib/modules/test; }
die() { echo "$*" >&2; exit 1; }
cd "$2/payload"
makeinstall_target
''', "install", recipe, str(base)], cwd=ROOT, check=True, capture_output=True)
                installed = base / "install/usr/lib/nvidia-drivers" / branch
                manifest = installed / "usr/share/vulkan"
                icd = json.loads((manifest / "icd.d/nvidia_icd.json").read_text())["ICD"]
                layers = json.loads((manifest / "implicit_layer.d/nvidia_layers.json").read_text())["layers"]
                self.assertEqual(icd["library_path"], "libEGL_nvidia.so.0")
                self.assertEqual(layers[1]["enable_environment"], {"NVPRESENT_ENABLE_SMOOTH_MOTION": "1"})
                required = (installed / "required-userspace").read_text().splitlines()
                for item in [icd, *layers]:
                    relative = "usr/lib/" + item["library_path"]
                    self.assertTrue((installed / relative).is_file(), relative)
                    self.assertIn(relative, required)
                    self.assertEqual((base / "install" / relative).readlink().as_posix(),
                                     "/run/nvidia-driver/" + relative)


if __name__ == "__main__":
    unittest.main()
