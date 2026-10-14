#!/usr/bin/env python3
"""Prepare catalog files for a human maintainer; never push or open an upstream PR."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import catalog
import marketplace
import package
import package_qualification
from publish_github import verify_remote_tag

UPSTREAM = "zed-industries/extensions"
POLICY = "https://github.com/zed-industries/extensions/blob/main/AI_POLICY.md"

# Match upstream's Node runtime and a reviewed exact pnpm 11 release.
NODE_VERSION = "24.21.0"
PNPM_VERSION = "11.28.5"
LOCKED_FILES = ("package.json", "pnpm-lock.yaml")


def validate_release_source(root, receipt, tag):
    """Bind release evidence to a clean tagged checkout, separate from tooling."""
    source = catalog.git(root, "rev-parse", "HEAD")
    tagged = catalog.git(root, "rev-parse", f"refs/tags/{tag}^{{commit}}")
    if (source != tagged
            or catalog.git(root, "status", "--porcelain", "--untracked-files=no")):
        raise marketplace.GateError("Release source must be the clean tagged checkout")
    marketplace.validate_receipt(receipt, source, tag, catalog=True)
    return source


def validate_released_package(root, receipt, tag, archive, sums, qualification):
    """Require actual published package bytes to name the exact release source."""
    value = json.loads(qualification)
    name = f"terraphim-lsp-{receipt['version']}.tar.gz"
    archive_record = package_qualification.record(archive)
    expected = {"status": "PACKAGE_BYTES_VERIFIED", "source": receipt["source"],
                "sourceTreeDirty": False, "tag": tag,
                "repository": receipt["repository"], "version": receipt["version"],
                "extensionId": "terraphim-lsp", "extensionPath": package.CATALOG_PATH}
    if (any(value.get(key) != item for key, item in expected.items())
            or value.get("archive") != {"name": name, **archive_record}
            or marketplace.checksums(sums.decode()) != {name: archive_record["sha256"]}
            or value.get("checksums") != {"name": "SHA256SUMS",
                                          **package_qualification.record(sums)}):
        raise marketplace.GateError("Published package identity or checksum differs")
    files = package_qualification.inspect_archive(archive, receipt["version"],
                                                  package.CATALOG_PATH)
    if value.get("entries") != {name: package_qualification.record(data)
                                for name, data in files.items()}:
        raise marketplace.GateError("Published package entries differ")
    for source_file in package.FILES:
        if files[source_file] != (root / package.CATALOG_PATH / source_file).read_bytes():
            raise marketplace.GateError("Published package differs from tagged source")
    return {"archive": {"name": name, **archive_record},
            "qualification": package_qualification.record(qualification)}


def locked_inputs(root):
    """Require upstream's regular manifest/lock files and reviewed runtime."""
    if any(not (root / name).exists() for name in LOCKED_FILES):
        raise marketplace.GateError("Upstream manifest and pnpm lockfile are required")
    if any((root / name).is_symlink() or not (root / name).is_file()
           for name in LOCKED_FILES):
        raise marketplace.GateError("Upstream manifest and lockfile must be regular files")
    saved = {name: (root / name).read_bytes() for name in LOCKED_FILES}
    if json.loads(saved["package.json"]).get("volta", {}).get("node") != NODE_VERSION:
        raise marketplace.GateError("Upstream runtime changed; review catalog tooling")
    return saved


def verify_locked_inputs(root, saved):
    """Refuse a dependency installer or sorter that rewrites upstream inputs."""
    if any((root / name).read_bytes() != data for name, data in saved.items()):
        raise marketplace.GateError("Upstream manifest or lockfile changed")


def install_and_sort(root, env):
    """Run upstream's real sorter using its frozen production dependencies."""
    saved = locked_inputs(root)
    node = subprocess.check_output(["node", "--version"], text=True, env=env).strip()
    pnpm = subprocess.check_output(["pnpm", "--version"], text=True, env=env).strip()
    if node != f"v{NODE_VERSION}" or pnpm != PNPM_VERSION:
        raise marketplace.GateError("Catalog requires the reviewed exact Node/pnpm versions")
    subprocess.run(["pnpm", "install", "--frozen-lockfile", "--ignore-scripts", "--prod"],
                   cwd=root, check=True, env=env)
    verify_locked_inputs(root, saved)
    subprocess.run(["pnpm", "run", "sort-extensions"], cwd=root, check=True, env=env)
    verify_locked_inputs(root, saved)
    return {"node": node, "pnpm": pnpm,
            "upstreamInputs": {name: hashlib.sha256(data).hexdigest()
                               for name, data in saved.items()},
            "frozenLockfile": True, "inputBytesUnchanged": True}



def write_handoff(root, receipt, output):
    """Save the actual catalog diff and factual evidence without authoring a PR."""
    changed = set(catalog.git(root, "diff", "--cached", "--name-only").splitlines())
    identifier = receipt["extensionId"]
    allowed = {".gitmodules", "extensions.toml", f"extensions/{identifier}"}
    if not changed.issubset(allowed):
        raise marketplace.GateError("Catalog diff includes an unrelated extension")
    if output.exists() or output.is_symlink():
        raise marketplace.GateError("Use a fresh catalog handoff directory")
    output.mkdir(parents=True)
    patch = subprocess.check_output(["git", "diff", "--cached", "--binary"], cwd=root)
    (output / "catalog.patch").write_bytes(patch)
    result = {
        "status": "HUMAN_SUBMISSION_REQUIRED" if changed else "ALREADY_IN_CATALOG",
        "source": receipt["source"],
        "tag": receipt["tag"],
        "extensionId": identifier,
        "extensionPath": receipt.get("extensionPath", ""),
        "repository": receipt["repository"],
        "version": receipt["version"],
        "qualificationUrl": receipt["qualificationUrl"],
        "upstream": UPSTREAM,
        "upstreamBase": catalog.git(root, "rev-parse", "HEAD"),
        "patchSha256": hashlib.sha256(patch).hexdigest(),
        "changedFiles": sorted(changed),
        "policy": POLICY,
        "remoteMutationPerformed": False,
    }
    (output / "submission.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "README.md").write_text(
        "# Human catalog submission\n\n"
        "The patch and JSON are technical evidence, not a pull-request description.\n"
        "Zed's AI policy requires a human contributor who understands the extension,\n"
        "writes the PR body and answers maintainers in their own words. Autonomous\n"
        "agents must not submit the contribution. Read the current policy: "
        + POLICY
        + "\n\n"
        "A human maintainer should review the saved native evidence, apply catalog.patch\n"
        "to their own fork at upstreamBase, inspect the three-file diff, then write and\n"
        "submit the PR. Keep its scope to this extension and at most three open PRs.\n"
        "No fork, branch, upstream PR or comment was created by this preparation.\n"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--tooling-commit", required=True)
    args = parser.parse_args()
    try:
        receipt = json.loads(args.preflight.read_text())
        tooling = catalog.git(marketplace.ROOT, "rev-parse", "HEAD")
        if (not marketplace.SHA_RE.fullmatch(args.tooling_commit)
                or tooling != args.tooling_commit
                or catalog.git(marketplace.ROOT, "status", "--porcelain",
                               "--untracked-files=no")):
            raise marketplace.GateError("Catalog tooling differs from reviewed dispatch commit")
        source = validate_release_source(args.source_root, receipt, args.tag)
        verify_remote_tag(receipt["repository"], args.tag, source)
        with tempfile.TemporaryDirectory() as folder:
            downloads = Path(folder) / "released"
            downloads.mkdir()
            names = [f"terraphim-lsp-{receipt['version']}.tar.gz",
                     "SHA256SUMS", "package-qualification.json"]
            data = [marketplace.anonymous_download(
                f"https://github.com/{receipt['repository']}/releases/download/{args.tag}/{name}",
                downloads / name) for name in names]
            released = validate_released_package(args.source_root, receipt, args.tag, *data)
            root = Path(folder) / "catalog"
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--quiet",
                    "--depth",
                    "1",
                    f"https://github.com/{UPSTREAM}",
                    str(root),
                ],
                check=True,
            )
            catalog.prepare(
                root,
                receipt["extensionId"],
                receipt["version"],
                receipt["repository"],
                source,
                receipt.get("extensionPath", ""),
            )
            clean_env = {
                k: v
                for k, v in os.environ.items()
                if k not in ["GH_TOKEN", "GITHUB_TOKEN"]
            }
            toolchain = install_and_sort(root, clean_env)
            catalog.git(root, "add", ".gitmodules", "extensions.toml")
            result = write_handoff(root, receipt, args.out)
            result["releasedPackage"] = released
            result["toolingSource"] = tooling
            result["toolchain"] = toolchain
            (args.out / "submission.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result))
    except (
        marketplace.GateError,
        KeyError,
        ValueError,
        OSError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"prepare_catalog: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
