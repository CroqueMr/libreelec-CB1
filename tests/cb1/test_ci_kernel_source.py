# SPDX-License-Identifier: MIT
"""Exercise CI kernel selection without downloading archives."""
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
FETCH = ROOT / ".github/scripts/fetch-kernel-source.sh"


class CIKernelSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.primary = self.root / "primary"
        self.mirror = self.root / "mirror"
        self.cache = self.root / "cache"
        self.calls = self.root / "calls"
        self.primary.write_bytes(b"primary archive")
        self.primary_sha = hashlib.sha256(self.primary.read_bytes()).hexdigest()
        payload = b"kernel file"
        payload_sha = hashlib.sha256(payload).hexdigest()
        self.mirror_sha = hashlib.sha256(
            f"source.c\0file\0False\0{payload_sha}\n".encode()
        ).hexdigest()
        with tarfile.open(self.mirror, "w:gz") as archive:
            member = tarfile.TarInfo("source.c")
            member.size = len(payload)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(payload))
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        curl = bin_dir / "curl"
        curl.write_text(
            '#!/bin/bash\n'
            'set -eu\n'
            'while [ "$#" -gt 1 ]; do\n'
            '  if [ "$1" = "--output" ]; then output=$2; shift; fi\n'
            '  shift\n'
            'done\n'
            'printf "%s\\n" "$1" >> "$CALLS"\n'
            'case "$1" in\n'
            '  https://primary) [ "$PRIMARY_FAIL" != yes ] || exit 22; '
            'cp "$PRIMARY" "$output" ;;\n'
            '  https://mirror) cp "$MIRROR" "$output" ;;\n'
            '  *) exit 1 ;;\n'
            'esac\n'
        )
        curl.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ["PATH"],
                        CALLS=str(self.calls), PRIMARY=str(self.primary),
                        MIRROR=str(self.mirror), PRIMARY_FAIL="no")

    def run_fetch(self, allow_mirror=True, primary_fail=False):
        env = dict(self.env, PRIMARY_FAIL="yes" if primary_fail else "no")
        args = ["https://primary", self.primary_sha, str(self.cache)]
        if allow_mirror:
            args += ["https://mirror", self.mirror_sha]
        return subprocess.run(
            ["bash", "-eu", "-c",
             'source "$1"; shift; fetch_kernel_source "$@"; '
             'printf "SELECTED=%s:%s\\n" "$linux_archive" "$linux_strip_components"',
             "test", str(FETCH), *args],
            env=env, text=True, capture_output=True
        )

    def test_primary_cached_and_verified(self):
        first = self.run_fetch()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(f"SELECTED={self.cache / (self.primary_sha + '.tar')}:1", first.stdout)
        second = self.run_fetch(primary_fail=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.calls.read_text().splitlines(), ["https://primary"])

    def test_network_failure_uses_verified_mirror_and_reuses_cache(self):
        first = self.run_fetch(primary_fail=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(f"SELECTED={self.cache / (self.mirror_sha + '.tar')}:0", first.stdout)
        self.assertEqual(self.run_fetch(primary_fail=True).returncode, 0)
        self.assertEqual(self.calls.read_text().splitlines(), ["https://primary", "https://mirror"])

    def test_primary_checksum_mismatch_does_not_use_mirror(self):
        self.primary.write_bytes(b"wrong bytes")
        result = self.run_fetch()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls.read_text().splitlines(), ["https://primary"])
        self.assertFalse((self.cache / (self.primary_sha + ".tar")).exists())

    def test_mirror_tar_metadata_does_not_change_source_identity(self):
        payload = b"kernel file"
        with tarfile.open(self.mirror, "w:gz") as archive:
            member = tarfile.TarInfo("source.c")
            member.size = len(payload)
            member.mode = 0o664
            member.mtime = 123456789
            archive.addfile(member, io.BytesIO(payload))
        self.assertEqual(self.run_fetch(primary_fail=True).returncode, 0)

    def test_unexpected_directory_is_rejected(self):
        payload = b"kernel file"
        with tarfile.open(self.mirror, "w:gz") as archive:
            member = tarfile.TarInfo("source.c")
            member.size = len(payload)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(payload))
            extra = tarfile.TarInfo("unexpected")
            extra.type = tarfile.DIRTYPE
            archive.addfile(extra)
        self.assertNotEqual(self.run_fetch(primary_fail=True).returncode, 0)

    def test_unreadable_mirror_file_is_rejected(self):
        payload = b"kernel file"
        with tarfile.open(self.mirror, "w:gz") as archive:
            member = tarfile.TarInfo("source.c")
            member.size = len(payload)
            member.mode = 0o004
            archive.addfile(member, io.BytesIO(payload))
        self.assertNotEqual(self.run_fetch(primary_fail=True).returncode, 0)

    def test_absolute_root_directory_is_rejected(self):
        payload = b"kernel file"
        with tarfile.open(self.mirror, "w:gz") as archive:
            member = tarfile.TarInfo("source.c")
            member.size = len(payload)
            member.mode = 0o644
            archive.addfile(member, io.BytesIO(payload))
            extra = tarfile.TarInfo("/")
            extra.type = tarfile.DIRTYPE
            extra.mode = 0o755
            archive.addfile(extra)
        self.assertNotEqual(self.run_fetch(primary_fail=True).returncode, 0)

    def test_corrupted_mirror_is_rejected(self):
        self.mirror.write_bytes(b"wrong bytes")
        result = self.run_fetch(primary_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.cache / (self.mirror_sha + ".tar")).exists())

    def test_corrupted_cache_is_rejected(self):
        self.cache.mkdir()
        (self.cache / (self.primary_sha + ".tar")).write_bytes(b"wrong bytes")
        result = self.run_fetch()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())

    def test_no_mirror_for_unmapped_kernel(self):
        result = self.run_fetch(allow_mirror=False, primary_fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls.read_text().splitlines(), ["https://primary"])


if __name__ == "__main__":
    unittest.main()
