#!/usr/bin/env python3
"""Builds the release package of the Zed extension.

Usage: package.py [--tag vX.Y.Z[-rc.N]] [--wasm PATH] [--out-dir DIR]

Builds extension.wasm (cargo build --release --target wasm32-wasip2) unless
--wasm names an existing build, then writes into DIR (default: dist/):

  terraphim-zed-<version>/          extension.toml, extension.wasm, LICENSE, README.md
  terraphim-zed-<release>.tar.gz    the same directory, packed deterministically
  SHA256SUMS                        "<sha256>  terraphim-zed-<release>.tar.gz"

The version comes from extension.toml. With --tag, the tag must be
v<version> or v<version>-rc.N, otherwise nothing is written; <release> is
the tag without the "v" (0.2.0-rc.1), so a canary and its final release have
distinct files. Without --tag, <release> is the version. The directory
inside stays terraphim-zed-<version>/: installs strip it, and Zed takes the
version from extension.toml. That directory is what Zed expects in
extensions/installed/terraphim.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tarfile
from typing import NamedTuple, Optional

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = ["LICENSE", "README.md", "extension.toml"]
# Fixed timestamp for every archive entry; SOURCE_DATE_EPOCH overrides it.
FIXED_MTIME = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
TAG_RE = re.compile(r"v(\d+\.\d+\.\d+)(-rc\.\d+)?")


class PackageError(Exception):
    pass


class Result(NamedTuple):
    tarball: pathlib.Path
    sums: pathlib.Path
    prerelease: bool


def read_version(text: str, table: Optional[str] = None) -> str:
    """Return `version = "..."` from the top level of a TOML file, or from
    `[table]` when given. Avoids tomllib so Python 3.8+ is enough."""
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        header = re.fullmatch(r"\[([^\[\]]+)\]", stripped)
        if header:
            current = header.group(1).strip()
            continue
        match = re.fullmatch(r'version\s*=\s*"([^"]+)"', stripped)
        if match and current == table:
            return match.group(1)
    raise PackageError(f"no version in {'top level' if table is None else '[' + table + ']'}")


def check_tag(tag: str, version: str) -> bool:
    """Validate `tag` against the manifest version; return True for -rc tags."""
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise PackageError(f"tag {tag!r} is not of the form vX.Y.Z or vX.Y.Z-rc.N")
    if match.group(1) != version:
        raise PackageError(f"tag {tag} does not match extension.toml version {version}")
    return match.group(2) is not None


def build_wasm(root: pathlib.Path) -> pathlib.Path:
    """Build the release wasm and return its path in cargo's target directory."""
    subprocess.run(
        ["cargo", "build", "--release", "--locked", "--target", "wasm32-wasip2"],
        cwd=root,
        check=True,
    )
    meta = subprocess.run(
        ["cargo", "metadata", "--format-version", "1", "--no-deps", "--offline"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    target = pathlib.Path(json.loads(meta.stdout)["target_directory"])
    return target / "wasm32-wasip2" / "release" / "zed_terraphim.wasm"


def _tarinfo(name: str, size: int = 0, directory: bool = False) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    info.mode = 0o755 if directory else 0o644
    info.size = size
    info.mtime = FIXED_MTIME
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    return info


def write_tarball(staged: pathlib.Path, dest: pathlib.Path) -> None:
    """Pack `staged` (a flat directory) as `<staged.name>/...` into `dest`.

    Entries are sorted and carry fixed metadata, and the gzip header has no
    timestamp or file name, so equal inputs give equal bytes."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        tar.addfile(_tarinfo(staged.name, directory=True))
        for path in sorted(staged.iterdir(), key=lambda p: p.name):
            data = path.read_bytes()
            tar.addfile(_tarinfo(f"{staged.name}/{path.name}", len(data)), io.BytesIO(data))
    with open(dest, "wb") as out, gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0) as gz:
        gz.write(raw.getvalue())


def package(
    root: pathlib.Path,
    wasm: pathlib.Path,
    out_dir: pathlib.Path,
    tag: Optional[str] = None,
) -> Result:
    version = read_version((root / "extension.toml").read_text())
    prerelease = check_tag(tag, version) if tag else False
    data = wasm.read_bytes()
    if not data.startswith(b"\x00asm"):
        raise PackageError(f"{wasm} is not a WebAssembly module")

    name = f"terraphim-zed-{version}"
    staged = out_dir / name
    if staged.exists():
        shutil.rmtree(staged)
    staged.mkdir(parents=True)
    for file in FILES:
        shutil.copyfile(root / file, staged / file)
    (staged / "extension.wasm").write_bytes(data)

    release = tag[1:] if tag else version
    tarball = out_dir / f"terraphim-zed-{release}.tar.gz"
    write_tarball(staged, tarball)
    digest = hashlib.sha256(tarball.read_bytes()).hexdigest()
    sums = out_dir / "SHA256SUMS"
    sums.write_text(f"{digest}  {tarball.name}\n")
    return Result(tarball, sums, prerelease)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tag", help="release tag to validate against extension.toml")
    parser.add_argument("--wasm", type=pathlib.Path, help="use this built wasm instead of building")
    parser.add_argument("--out-dir", type=pathlib.Path, default=ROOT / "dist")
    args = parser.parse_args(argv)
    try:
        version = read_version((ROOT / "extension.toml").read_text())
        if args.tag:
            # Fail on a bad tag before spending minutes on the build.
            check_tag(args.tag, version)
        wasm = args.wasm or build_wasm(ROOT)
        result = package(ROOT, wasm, args.out_dir, args.tag)
    except PackageError as err:
        print(f"package.py: {err}", file=sys.stderr)
        return 1
    print(result.tarball)
    print(result.sums.read_text(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
