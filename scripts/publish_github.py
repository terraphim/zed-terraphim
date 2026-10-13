#!/usr/bin/env python3
"""Publish an already tested package; never replace an existing release asset."""

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

import marketplace
import package
import package_qualification


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True)


def api(path):
    return json.loads(gh("api", path))


def release(repo, tag):
    pages = json.loads(
        gh("api", "--paginate", "--slurp", f"repos/{repo}/releases?per_page=100")
    )
    found = [item for page in pages for item in page if item["tag_name"] == tag]
    if len(found) > 1:
        raise marketplace.GateError("Ambiguous release tag")
    return found[0] if found else None


def verify_package(artifacts, tag, source, root=package.ROOT):
    return package_qualification.verify(root, artifacts, tag, source)


@contextmanager
def qualified_snapshot(artifacts, tag, source, root=package.ROOT):
    """Validate a private snapshot and use those same bytes through publication."""
    package.check_tag(tag, package.read_version((root / "extension.toml").read_text()))
    with tempfile.TemporaryDirectory(prefix="zed-qualified-") as tmp:
        snapshot = Path(tmp)
        for relative in [
            "public-preflight/preflight.json",
            f"release-dist/terraphim-zed-{tag[1:]}.tar.gz",
            "release-dist/SHA256SUMS",
            f"release-dist/{package_qualification.RECEIPT}",
        ]:
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write((artifacts / relative).read_bytes())
        yield verify_package(snapshot, tag, source, root)


def verify_remote_tag(repo, tag, source):
    value = api(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    for _ in range(4):
        if value["type"] == "commit":
            if value["sha"] != source:
                raise marketplace.GateError(
                    "Remote tag no longer matches the tested source"
                )
            return
        if value["type"] != "tag":
            break
        value = api(f"repos/{repo}/git/tags/{value['sha']}")["object"]
    raise marketplace.GateError("Release tag does not resolve to a commit")


def fresh_readback(artifacts):
    """Retain previous attempts while allowing safe publication retries."""
    return Path(tempfile.mkdtemp(prefix="public-readback-", dir=artifacts))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not marketplace.REPO_RE.fullmatch(args.repo):
            raise marketplace.GateError("Invalid GitHub repository")
        source = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=package.ROOT, text=True
        ).strip()
        with qualified_snapshot(args.artifacts, args.tag, source) as (receipt, files):
            if receipt["repository"] != args.repo:
                raise marketplace.GateError("Preflight belongs to another repository")
            verify_remote_tag(args.repo, args.tag, source)
            current = release(args.repo, args.tag)
            prerelease = package.check_tag(args.tag, receipt["version"])
            if current is None:
                notes = args.artifacts / "release-notes.md"
                notes.write_text(
                    f"Zed extension {args.tag}; source `{source}`.\n\nPackage SHA-256 is in SHA256SUMS; package-qualification.json binds its files and WASM to this source and CI preflight. Public pinned LSP downloads passed the release gate. This package is not a claim of Zed catalog acceptance. See docs/marketplace.md for catalog prerequisites.\n"
                )
                command = [
                    "release",
                    "create",
                    args.tag,
                    "--repo",
                    args.repo,
                    "--verify-tag",
                    "--draft",
                    "--title",
                    args.tag,
                    "--notes-file",
                    str(notes),
                ]
                if prerelease:
                    command.append("--prerelease")
                gh(*command)
                current = release(args.repo, args.tag)
            if current is None or current["prerelease"] != prerelease:
                raise marketplace.GateError("Release metadata is inconsistent")
            names = [item["name"] for item in current["assets"]]
            if len(names) != len(set(names)) or not set(names).issubset(
                {p.name for p in files}
            ):
                raise marketplace.GateError("Unexpected or duplicate remote release assets")
            with tempfile.TemporaryDirectory() as tmp:
                for path in files:
                    if path.name not in names:
                        if not current["draft"]:
                            raise marketplace.GateError(
                                "Published release has missing assets; refusing repair in place"
                            )
                        gh("release", "upload", args.tag, str(path), "--repo", args.repo)
                    # Existing bytes are checked as well; no --clobber, deletes or tag creation.
                    gh(
                        "release",
                        "download",
                        args.tag,
                        "--pattern",
                        path.name,
                        "--repo",
                        args.repo,
                        "--dir",
                        tmp,
                    )
                    if (Path(tmp) / path.name).read_bytes() != path.read_bytes():
                        raise marketplace.GateError(
                            f"Remote {path.name} differs from the tested package"
                        )
            verify_remote_tag(args.repo, args.tag, source)
            if current["draft"]:
                gh("release", "edit", args.tag, "--repo", args.repo, "--draft=false")
            readback = fresh_readback(args.artifacts)
            for path in files:
                data = marketplace.anonymous_download(
                    f"https://github.com/{args.repo}/releases/download/{args.tag}/{path.name}",
                    readback / path.name,
                )
                if data != path.read_bytes():
                    raise marketplace.GateError(
                        "Anonymous published release readback differs"
                    )
            result = {
                "status": "PUBLISHED_PUBLIC_VERIFIED",
                "tag": args.tag,
                "source": source,
                "assets": [
                    {
                        "name": path.name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "bytes": path.stat().st_size,
                    }
                    for path in files
                ],
            }
            (readback / "publication.json").write_text(json.dumps(result, indent=2) + "\n")
            (args.artifacts / "publication.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
            print(json.dumps(result))
    except (
        marketplace.GateError,
        package.PackageError,
        KeyError,
        ValueError,
        subprocess.CalledProcessError,
        OSError,
        tarfile.TarError,
    ) as error:
        print(f"publish_github: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
