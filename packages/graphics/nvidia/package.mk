# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2021-present Team LibreELEC (https://libreelec.tv)

PKG_NAME="nvidia"
PKG_VERSION="620.73.04"
PKG_SHA256="91f162952fa1d7a4fbdcc7a1a3a0266dfa079007be43d7235e5a6896bf29172a"
PKG_ARCH="x86_64"
PKG_LICENSE="LicenseRef-nonfree"
PKG_SITE="https://www.nvidia.com/en-us/drivers/unix/"
PKG_DEPENDS_TARGET="toolchain util-macros libglvnd nvidia_egl-gbm nvidia-open-kernel-modules nvidia-pascal"
PKG_LONGDESC="NVIDIA R620 and R580 GBM drivers, selected coherently at early boot."
PKG_URL="https://download.nvidia.com/XFree86/Linux-x86_64/${PKG_VERSION}/NVIDIA-Linux-x86_64-${PKG_VERSION}-no-compat32.run"
PKG_TOOLCHAIN="manual"
PKG_BUILD_FLAGS="-strip"
PKG_IS_KERNEL_PKG="yes"
NVIDIA_BRANCH="r620"
if [ "${VULKAN_SUPPORT}" = yes ]; then
  PKG_DEPENDS_TARGET+=" ${VULKAN} vulkan-tools"
fi

source "${ROOT}/packages/graphics/nvidia/common.mk"

post_makeinstall_target() {
  mkdir -p "${INSTALL}/usr/lib/nvidia-drivers/r620"
  cp "${PKG_DIR}/files/select-driver" "${INSTALL}/usr/lib/nvidia-drivers/"
  cp "${PKG_DIR}/files/hdr-depth.conf" "${INSTALL}/usr/lib/nvidia-drivers/r620/"
  python3 "${PKG_DIR}/generate-pci-map.py" \
    "${PKG_BUILD}/supported-gpus/supported-gpus.json" \
    "$(get_build_dir nvidia-pascal)/supported-gpus/supported-gpus.json" \
    "${INSTALL}/usr/lib/nvidia-drivers/pci-branches"
}
