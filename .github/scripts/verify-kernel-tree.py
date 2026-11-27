# SPDX-License-Identifier: MIT
# The archive encoding/mtime differs between upstream mirrors. Verify the
# Git-visible source paths, regular file content and executable bits, and links.
import hashlib
from pathlib import PurePosixPath
import sys
import tarfile


def source_digest(path):
    entries = {}
    directories = set()
    with tarfile.open(path, "r|*") as archive:
        for member in archive:
            name = member.name.removeprefix("./")
            if member.isdir():
                if member.mode & 0o7700 != 0o700:
                    raise ValueError(f"Unusable directory mode: {member.name}")
                if member.name in (".", "./"):
                    continue
                name = name.rstrip("/")
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith("/") or ".." in parts
                    or "\0" in name or "\n" in name or str(PurePosixPath(name)) != name):
                raise ValueError(f"Invalid archive path: {name!r}")
            if name in entries or name in directories or member.mode & 0o7000:
                raise ValueError(f"Duplicate or special archive entry: {name}")
            if member.isdir():
                directories.add(name)
            elif member.isfile():
                if member.mode & 0o600 != 0o600 or (
                        member.mode & 0o111 and not member.mode & 0o100):
                    raise ValueError(f"Unusable file mode: {name}")
                digest = hashlib.sha256()
                with archive.extractfile(member) as file:
                    for block in iter(lambda: file.read(1024 * 1024), b""):
                        digest.update(block)
                entries[name] = ("file", bool(member.mode & 0o111), digest.hexdigest())
            elif member.issym():
                target = member.linkname
                if "\0" in target or "\n" in target:
                    raise ValueError(f"Invalid symlink target: {name}")
                entries[name] = ("symlink", target)
            else:
                raise ValueError(f"Unsupported archive entry: {name}")
    parents = {str(parent) for name in entries
               for parent in PurePosixPath(name).parents if str(parent) != "."}
    if not directories <= parents or parents & entries.keys():
        raise ValueError("Unexpected directory or non-directory ancestor in source archive")
    digest = hashlib.sha256()
    for name, value in sorted(entries.items()):
        digest.update((name + "\0" + "\0".join(map(str, value)) + "\n").encode())
    return digest.hexdigest()


if __name__ == "__main__":
    try:
        actual = source_digest(sys.argv[1])
        if actual != sys.argv[2]:
            raise ValueError(f"Source digest mismatch: {actual}")
    except (OSError, tarfile.TarError, ValueError) as error:
        sys.exit(str(error))
    print(f"Verified Linux source tree SHA-256: {actual}")
