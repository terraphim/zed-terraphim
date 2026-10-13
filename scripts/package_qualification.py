#!/usr/bin/env python3
"""Bind a CI-produced Zed archive to its tested WASM and exact tagged source.

This is package integrity evidence. The calling CI job must finish its build and
checks before issuing it; this receipt does not claim native Zed acceptance.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tomllib

import marketplace
import package

RECEIPT = "package-qualification.json"
MAX_UNPACKED_BYTES = 128 * 1024 * 1024


def record(data):
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def source_state(root, tag):
    """Require a clean tracked checkout at the existing tag and read its files."""
    files = {name: (root / name).read_bytes() for name in package.FILES}
    manifest = tomllib.loads(files["extension.toml"].decode("utf-8"))
    package.check_tag(tag, manifest["version"])

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root)

    source = git("rev-parse", "HEAD").decode().strip()
    tagged = git("rev-parse", f"refs/tags/{tag}^{{commit}}").decode().strip()
    if not marketplace.SHA_RE.fullmatch(source) or source != tagged:
        raise marketplace.GateError("Local tag must match the checked-out source")
    if git("status", "--porcelain", "--untracked-files=no").strip():
        raise marketplace.GateError("Package qualification requires clean tracked source")
    for name, data in files.items():
        if data != git("show", f"{source}:{name}"):
            raise marketplace.GateError(f"Source file differs from tagged bytes: {name}")
    return source, manifest, files


def inspect_archive(data, version):
    """Read the four exact regular files, rejecting aliases, links and extras."""
    prefix = f"terraphim-zed-{version}"
    file_names = package.FILES + ["extension.wasm"]
    expected_names = {prefix} | {f"{prefix}/{name}" for name in file_names}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        members = archive.getmembers()
        if (
            len(members) != len(expected_names)
            or {member.name for member in members} != expected_names
            or any(
                not (member.isdir() if member.name == prefix else member.isfile())
                for member in members
            )
            or any(member.size < 0 for member in members)
            or sum(member.size for member in members) > MAX_UNPACKED_BYTES
        ):
            raise marketplace.GateError("Unexpected extension package layout or size")
        files = {
            name: archive.extractfile(f"{prefix}/{name}").read()
            for name in file_names
        }
    if not files["extension.wasm"].startswith(b"\x00asm"):
        raise marketplace.GateError("Missing packaged WebAssembly module")
    return files


def capture(root, artifacts, tag, expected_source=None):
    """Inspect actual bytes and return the complete deterministic qualification."""
    source, manifest, source_files = source_state(root, tag)
    if expected_source is not None and source != expected_source:
        raise marketplace.GateError("Checked-out source differs from publication source")
    preflight_bytes = (artifacts / "public-preflight/preflight.json").read_bytes()
    preflight = json.loads(preflight_bytes)
    marketplace.validate_receipt(preflight, source, tag)
    if (
        preflight.get("version") != manifest["version"]
        or preflight.get("extensionId") != manifest["id"]
        or not marketplace.REPO_RE.fullmatch(preflight.get("repository", ""))
    ):
        raise marketplace.GateError("Preflight identity differs from tagged manifest")
    folder = artifacts / "release-dist"
    archive = folder / f"terraphim-zed-{tag[1:]}.tar.gz"
    archive_bytes = archive.read_bytes()
    sums = folder / "SHA256SUMS"
    sums_bytes = sums.read_bytes()
    if marketplace.checksums(sums_bytes.decode("utf-8")) != {
        archive.name: record(archive_bytes)["sha256"]
    }:
        raise marketplace.GateError("Release package does not match its checksum manifest")
    members = inspect_archive(archive_bytes, manifest["version"])
    for name, data in source_files.items():
        if members[name] != data:
            raise marketplace.GateError(f"Packaged source differs from tagged bytes: {name}")
    report = {
        "schema": 1,
        "status": "PACKAGE_BYTES_VERIFIED",
        "scope": "Package integrity after CI; native Zed acceptance is separate",
        "source": source,
        "sourceTreeDirty": False,
        "tag": tag,
        "repository": preflight["repository"],
        "version": manifest["version"],
        "extensionId": manifest["id"],
        "publicPreflight": record(preflight_bytes),
        "archive": {"name": archive.name, **record(archive_bytes)},
        "checksums": {"name": sums.name, **record(sums_bytes)},
        "entries": {name: record(data) for name, data in sorted(members.items())},
    }
    return preflight, report, members, [archive, sums, folder / RECEIPT]


def qualify(root, artifacts, tag, wasm):
    """Issue a new receipt only when the archive contains the actual CI module."""
    _, report, members, files = capture(root, artifacts, tag)
    if members["extension.wasm"] != wasm.read_bytes():
        raise marketplace.GateError("Packaged WASM differs from the tested CI module")
    # Never replace prior qualification evidence, including an interrupted run.
    with files[-1].open("x") as output:
        output.write(json.dumps(report, indent=2) + "\n")
    return report


def verify(root, artifacts, tag, source):
    """Require the CI receipt to match all independently re-read source/bytes."""
    preflight, actual, _, files = capture(root, artifacts, tag, source)
    qualified = json.loads(files[-1].read_bytes())
    if qualified != actual:
        raise marketplace.GateError("Package bytes or source differ from CI qualification")
    return preflight, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("."))
    parser.add_argument("--wasm", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = qualify(package.ROOT, args.artifacts, args.tag, args.wasm)
        print(json.dumps(report))
    except (
        marketplace.GateError, package.PackageError, KeyError, ValueError,
        subprocess.CalledProcessError, OSError, tarfile.TarError,
    ) as error:
        print(f"package_qualification: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
