#!/bin/bash
# SPDX-License-Identifier: MIT
# Cache only fully verified archives. Leave the package pin unchanged.
fetch_kernel_source() {
  local url=$1 sha=$2 cache=$3 mirror_url=${4:-} mirror_digest=${5:-}
  mkdir -p "$cache"
  local mirror_archive="$cache/${mirror_digest}.tar"
  linux_archive="$cache/$sha.tar"
  linux_strip_components=1

  if [ -f "$linux_archive" ]; then
    printf '%s  %s\n' "$sha" "$linux_archive" | sha256sum --check
    return
  fi
  if [ -n "$mirror_digest" ] && [ -f "$mirror_archive" ]; then
    linux_archive="$mirror_archive"
    linux_strip_components=0
    python3 "$(dirname "${BASH_SOURCE[0]}")/verify-kernel-tree.py" "$linux_archive" "$mirror_digest"
    return
  fi

  if curl --fail --silent --show-error --location --retry 1 --retry-max-time 60 \
      --max-time 240 --output "$linux_archive.part" "$url"; then
    printf '%s  %s\n' "$sha" "$linux_archive.part" | sha256sum --check || return
    mv -- "$linux_archive.part" "$linux_archive"
    return
  fi
  rm -f -- "$linux_archive.part"
  [ -n "$mirror_digest" ] || return 1
  echo "Primary kernel archive unavailable; fetching the verified upstream mirror."
  linux_archive="$mirror_archive"
  linux_strip_components=0
  curl --fail --silent --show-error --location --retry 1 --max-time 240 \
      --output "$linux_archive.part" "$mirror_url" || return
  python3 "$(dirname "${BASH_SOURCE[0]}")/verify-kernel-tree.py" "$linux_archive.part" "$mirror_digest" || return
  mv -- "$linux_archive.part" "$linux_archive"
}
