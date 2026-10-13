#!/usr/bin/env python3
"""Fail-closed public release/catalog preflight (Python 3.11+, cargo, curl)."""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from urllib.parse import quote, urlparse

import package

ROOT = package.ROOT
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SHA_RE = re.compile(r"[0-9a-f]{40}")


class GateError(Exception):
    """A prerequisite is missing; no publication is authorized."""


def checksums(text):
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(
            r"([0-9a-fA-F]{64}) [ *]([A-Za-z0-9][A-Za-z0-9_.-]*)", line
        )
        if not match or match[2] in result:
            raise GateError("Malformed or duplicate checksum entry")
        result[match[2]] = match[1].lower()
    if not result:
        raise GateError("Empty checksum manifest")
    return result


def verify_binary(path, expected):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected:
        raise GateError(f"{path.name}: SHA-256 mismatch")
    # Provisioning consumes raw executables, never archives or an HTML login page.
    if len(data) < 64 or data[:4] not in [
        b"\x7fELF",
        b"\xcf\xfa\xed\xfe",
        b"\xfe\xed\xfa\xcf",
        b"\xca\xfe\xba\xbe",
        b"\xca\xfe\xba\xbf",
    ]:
        raise GateError(f"{path.name}: not a raw ELF/Mach-O executable")
    return {"name": path.name, "bytes": len(data), "sha256": digest}


def anonymous_download(url, destination):
    """Fetch normal HTTPS URLs with no curl config, credentials or auth headers."""
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise GateError("Anonymous downloads require an ordinary HTTPS URL")
    if destination.exists() or destination.is_symlink():
        raise GateError(f"Refusing to overwrite {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "curl",
            "--disable",
            "--fail",
            "--silent",
            "--show-error",
            "--location",
            "--proto",
            "=https",
            "--proto-redir",
            "=https",
            "--max-redirs",
            "5",
            "--connect-timeout",
            "15",
            "--max-time",
            "300",
            "--retry",
            "2",
            "--output",
            str(destination),
            "--write-out",
            "%{http_code}",
            url,
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode or result.stdout != "200":
        # Do not emit environment or response bodies, which may contain secrets.
        raise GateError(
            f"Anonymous GET unavailable: {url} (HTTP {result.stdout}, curl {result.returncode})"
        )
    return destination.read_bytes()


def source_ancestry(repo, comparison, source):
    if repo.get("private") is not False:
        raise GateError("Catalog/release source repository must be public")
    if (
        comparison.get("status") not in ["ahead", "identical"]
        or comparison.get("merge_base_commit", {}).get("sha") != source
    ):
        raise GateError(
            "Exact release source must be reachable from the public default branch"
        )


def extension_path(value):
    """Accept a repository-relative extension directory, never a traversal."""
    if value and not re.fullmatch(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", value):
        raise GateError("Invalid extension subdirectory")
    return value


def read_manifest(root, path=""):
    path = extension_path(path)
    directory = root / path
    if not directory.resolve().is_relative_to(root.resolve()):
        raise GateError("Extension directory escapes the source repository")
    manifest = tomllib.loads((directory / "extension.toml").read_text())
    cargo = tomllib.loads((directory / "Cargo.toml").read_text())
    if manifest["version"] != cargo["package"]["version"]:
        raise GateError("Extension and Cargo versions differ")
    return manifest


def catalog_manifest(manifest, tag):
    version = manifest["version"]
    if package.check_tag(tag, version):
        raise GateError("Catalog submission requires a stable extension tag")
    identifier = manifest["id"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier):
        raise GateError("Catalog id must be kebab-case")
    if "zed" in identifier.split("-") or "extension" in identifier.split("-"):
        raise GateError("Catalog id must not contain zed or extension")
    if manifest.get("context_servers"):
        if len(manifest["context_servers"]) != 1 or manifest.get("language_servers"):
            raise GateError(
                "Zed requires MCP extensions to provide one MCP server and nothing else; preserve the existing adapter until it is split or a maintainer exception is obtained"
            )
        if not (
            identifier.startswith("mcp-server-") or identifier.endswith("-mcp-server")
        ):
            raise GateError("MCP catalog id must identify its server role")
    elif manifest.get("language_servers") and not identifier.endswith(
        ("-lsp", "-language-server")
    ):
        raise GateError(
            "Language-server-only catalog id must end in -lsp or -language-server"
        )


def qualification(source, qualified_commit, url):
    if qualified_commit != source or not SHA_RE.fullmatch(source):
        raise GateError("Native Zed qualification must name the exact release commit")
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise GateError(
            "Native Zed qualification requires a reviewable HTTPS evidence URL"
        )


def validate_receipt(receipt, source, tag, catalog=False):
    if (
        receipt.get("status") != "PASS"
        or receipt.get("source") != source
        or receipt.get("tag") != tag
    ):
        raise GateError(
            "Public preflight receipt does not match this release source/tag"
        )
    if catalog and receipt.get("catalog") is not True:
        raise GateError("Receipt does not authorize catalog submission")


def preflight(args):
    if not REPO_RE.fullmatch(args.repo):
        raise GateError("--repo must be owner/name")
    manifest = read_manifest(ROOT, args.extension_path)
    package.check_tag(args.tag, manifest["version"])
    source = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    tag_source = subprocess.check_output(
        ["git", "rev-parse", f"refs/tags/{args.tag}^{{commit}}"], cwd=ROOT, text=True
    ).strip()
    if source != tag_source:
        raise GateError("Tag must already point at the exact checked-out source")
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
    ).strip():
        raise GateError("Release source has tracked modifications")
    if args.catalog:
        catalog_manifest(manifest, args.tag)
        qualification(source, args.qualified_commit, args.qualification_url)
    if args.out.exists() or args.out.is_symlink():
        raise GateError("Use a new output directory for each public preflight")
    args.out.mkdir(parents=True)
    repo = json.loads(
        anonymous_download(
            f"https://api.github.com/repos/{args.repo}", args.out / "repository.json"
        )
    )
    branch = quote(repo.get("default_branch", ""), safe="")
    comparison = json.loads(
        anonymous_download(
            f"https://api.github.com/repos/{args.repo}/compare/{source}...{branch}",
            args.out / "source-ancestry.json",
        )
    )
    source_ancestry(repo, comparison, source)
    contract = json.loads(
        subprocess.check_output(
            [
                "cargo",
                "run",
                "--locked",
                "--offline",
                "--quiet",
                "--example",
                "release-contract",
            ],
            cwd=ROOT,
            text=True,
        )
    )
    # These values come from compiled provision::LSP/candidate_assets, not a second pin.
    if not REPO_RE.fullmatch(contract["repo"]) or not re.fullmatch(
        r"[A-Za-z0-9_.-]+", contract["tag"]
    ):
        raise GateError("Unsafe release contract repository/tag")
    names = contract["assets"]
    if (
        not names
        or len(names) != len(set(names))
        or any(
            not re.fullmatch(r"[A-Za-z0-9_.-]+", n)
            for n in names + [contract["checksum_file"]]
        )
    ):
        raise GateError("Invalid release asset contract")
    base = f"https://github.com/{contract['repo']}/releases/download/{contract['tag']}"
    sums = anonymous_download(
        f"{base}/{contract['checksum_file']}", args.out / contract["checksum_file"]
    )
    expected = checksums(sums.decode("utf-8"))
    missing = set(names) - expected.keys()
    if missing:
        raise GateError(
            "Public LSP checksum manifest is missing: " + ", ".join(sorted(missing))
        )
    assets = []
    for name in names:
        url = f"{base}/{name}"
        anonymous_download(url, args.out / name)
        record = verify_binary(args.out / name, expected[name])
        record["url"] = url
        assets.append(record)
    receipt = {
        "status": "PASS",
        "checkedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": source,
        "tag": args.tag,
        "repository": args.repo,
        "version": manifest["version"],
        "extensionId": manifest["id"],
        "extensionPath": args.extension_path,
        "catalog": args.catalog,
        "qualificationUrl": args.qualification_url if args.catalog else None,
        "publicLsp": contract,
        "assets": assets,
    }
    (args.out / "preflight.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("--extension-path", default="")
    parser.add_argument("--qualified-commit", default="")
    parser.add_argument("--qualification-url", default="")
    args = parser.parse_args()
    try:
        result = preflight(args)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "source": result["source"],
                    "lspAssets": len(result["assets"]),
                }
            )
        )
    except (
        GateError,
        package.PackageError,
        KeyError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"marketplace gate: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
