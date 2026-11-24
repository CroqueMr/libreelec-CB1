# SPDX-License-Identifier: GPL-2.0-or-later
"""Regenerate the synthetic FEL identity inputs with FFmpeg/libx265 and mkvmerge."""

from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent
FRAME_COUNT = 110
WIDTH, HEIGHT = 128, 72
START_CODE = b"\x00\x00\x00\x01"


def nal_type(nal):
    return (nal[0] >> 1) & 63


def encode(key_interval, bframes, forced_keys=()):
    plane = WIDTH * HEIGHT
    pixels = b"".join(
        bytes([16 + frame]) * plane + bytes([128]) * (plane // 2)
        for frame in range(FRAME_COUNT)
    )
    command = [
        "ffmpeg", "-v", "error", "-f", "rawvideo", "-pixel_format", "yuv420p",
        "-video_size", f"{WIDTH}x{HEIGHT}", "-framerate", "24", "-i", "pipe:0",
        "-frames:v", str(FRAME_COUNT), "-c:v", "libx265",
    ]
    if forced_keys:
        expression = "+".join(f"eq(n,{key})" for key in forced_keys)
        command.extend(["-forced-idr", "1", "-force_key_frames", "expr:" + expression])
    minimum = 1 if forced_keys else key_interval
    options = (f"keyint={key_interval}:min-keyint={minimum}:bframes={bframes}:"
               "scenecut=0:open-gop=0:aud=1:repeat-headers=1:pools=1:frame-threads=1:"
               "log-level=error:lossless=1")
    data = subprocess.check_output(
        command + ["-x265-params", options, "-f", "hevc", "pipe:1"], input=pixels
    )
    units = []
    for nal in re.split(rb"\x00\x00\x00?\x01", data):
        if len(nal) < 2:
            continue
        kind = nal_type(nal)
        if kind == 35:
            units.append([])
        if kind not in (39, 40):
            units[-1].append(nal)
    assert len(units) == FRAME_COUNT
    return units


def mux(name, units):
    with tempfile.TemporaryDirectory() as scratch:
        elementary = Path(scratch) / (name + ".hevc")
        elementary.write_bytes(b"".join(START_CODE + nal for unit in units for nal in unit))
        subprocess.run(
            ["mkvmerge", "--quiet", "--deterministic", name, "-o", str(ROOT / (name + ".mkv")),
             "--default-duration", "0:24fps", str(elementary)],
            check=True,
        )


def packed(base, enhancement):
    return [bl + [b"\x7e\x01" + nal for nal in el] for bl, el in zip(base, enhancement, strict=True)]


def main():
    enhancement = encode(46, 0)
    mux("healthy", packed(encode(46, 3), enhancement))

    # Delete EL10 and EL91. The second loss moves EL's IDR92 into BL's IDR91 block.
    shifted = enhancement[:10] + enhancement[11:47] + [[]] + enhancement[47:]
    mux("false-anchor", packed(encode(91, 3), shifted[:91] + shifted[92:] + [[]]))

    base = encode(150, 3, (34, 92))
    enhancement = encode(150, 0, (34, 46, 92))
    # Delete EL44, which has POC 10 in its GOP. Its next IDR occurs on a non-key BL.
    mux("lost-reference", packed(base, enhancement[:44] + enhancement[45:47] + [[]] + enhancement[47:]))
    mux("timed-base", base)
    mux("timed-enhancement", enhancement)


if __name__ == "__main__":
    main()
