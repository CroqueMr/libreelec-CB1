# SPDX-License-Identifier: GPL-2.0-or-later
"""The packed FEL decoder may stop on ambiguous input, but every returned pair must be exact."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures/fel_identity"


class FELIdentityAfterLoss(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        engine = os.environ.get("CB1_TEST_ENGINE")
        prefix = os.environ.get("FFMPEG_TEST_PREFIX")
        if not engine or not prefix:
            raise unittest.SkipTest("Selected engine and matched FFmpeg required")

        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.binary = Path(temporary.name) / "fel_identity"
        libraries = str(Path(prefix) / "lib")
        subprocess.run(
            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-g",
             "-fsanitize=address,undefined", "-fno-pie", "-no-pie",
             "-I" + str(Path(engine) / "src"), "-I" + str(Path(prefix) / "include"),
             str(HERE / "fel_identity.c"), "-L" + libraries, "-Wl,-rpath," + libraries,
             "-lavformat", "-lavcodec", "-lavutil", "-o", str(cls.binary)],
            check=True,
        )

    def replay(self, *names, expected_statuses=(0,)):
        inputs = [FIXTURES / (name + ".mkv") for name in names]
        replay = subprocess.run(
            [self.binary, *inputs], capture_output=True, text=True, timeout=20
        )
        frames = []
        for line in replay.stdout.splitlines():
            presentation, base, enhancement = map(int, line.split())
            self.assertEqual(base, enhancement, f"BL{base} received EL{enhancement}")
            self.assertEqual(presentation, base, f"Wrong presentation identity for BL{base}")
            frames.append(base)
        self.assertIn(replay.returncode, expected_statuses, replay.stderr)
        self.assertEqual(frames, sorted(set(frames)))
        self.assertTrue(all(0 <= frame < 110 for frame in frames))
        return frames

    def test_healthy_packed_layers_remain_exact(self):
        self.assertEqual(self.replay("healthy"), list(range(110)))

    def test_missing_reference_does_not_change_valid_pairs(self):
        frames = self.replay("lost-reference", expected_statuses=(0, 10))
        self.assertEqual(frames[:44], list(range(44)))
        self.assertNotIn(44, frames)

    def test_shifted_key_cannot_authorize_the_wrong_enhancement(self):
        frames = self.replay("false-anchor", expected_statuses=(0, 10))
        self.assertEqual(frames[:10], list(range(10)))
        self.assertNotIn(91, frames)

    def test_native_layer_timestamps_allow_recovery_after_loss(self):
        frames = self.replay("timed-base", "timed-enhancement")
        self.assertEqual(frames, [frame for frame in range(110) if frame not in (44, 45)])

    def test_unresolved_recovery_reports_failure_after_all_exact_pairs(self):
        frames = self.replay("unresolved-tail", expected_statuses=(10,))
        self.assertEqual(frames, list(range(44)))
