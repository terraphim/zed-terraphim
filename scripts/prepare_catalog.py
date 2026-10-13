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
from publish_github import verify_remote_tag

UPSTREAM = "zed-industries/extensions"
POLICY = "https://github.com/zed-industries/extensions/blob/main/AI_POLICY.md"


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
    args = parser.parse_args()
    try:
        receipt = json.loads(args.preflight.read_text())
        source = catalog.git(marketplace.ROOT, "rev-parse", "HEAD")
        marketplace.validate_receipt(receipt, source, args.tag, catalog=True)
        verify_remote_tag(receipt["repository"], args.tag, source)
        with tempfile.TemporaryDirectory() as folder:
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
            subprocess.run(
                [
                    "npm",
                    "install",
                    "--package-lock=false",
                    "--ignore-scripts",
                    "--omit=dev",
                    "--no-audit",
                    "--no-fund",
                ],
                cwd=root,
                check=True,
                env=clean_env,
            )
            subprocess.run(
                ["npm", "run", "sort-extensions"], cwd=root, check=True, env=clean_env
            )
            catalog.git(root, "add", ".gitmodules", "extensions.toml")
            print(json.dumps(write_handoff(root, receipt, args.out)))
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
