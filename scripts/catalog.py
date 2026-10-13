#!/usr/bin/env python3
"""Prepare exactly one Zed catalog entry at a verified immutable source commit."""

import argparse
import configparser
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

import marketplace


def registry_entry(text, identifier, version, path=""):
    path = marketplace.extension_path(path)
    data = tomllib.loads(text)
    if (
        identifier in data
        and data[identifier].get("submodule") != f"extensions/{identifier}"
    ):
        raise marketplace.GateError(
            "Existing catalog entry uses a different submodule path"
        )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", identifier) or not re.fullmatch(
        r"\d+\.\d+\.\d+", version
    ):
        raise marketplace.GateError("Invalid catalog identifier/version")
    if identifier in data and data[identifier].get("path", "") != path:
        raise marketplace.GateError(
            "Existing catalog entry uses a different extension directory"
        )
    # Catalog files use one flat table per extension. Retain every other block.
    sections = {}
    prefix = ""
    matches = list(re.finditer(r"^\[([^\[\]\n]+)\]\s*\n", text, re.M))
    if matches:
        prefix = text[: matches[0].start()]
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match[1]] = text[match.start() : end].strip() + "\n"
    if set(sections) != set(data):
        raise marketplace.GateError(
            "Unsupported catalog table shape; review before editing"
        )
    path_line = f'path = "{path}"\n' if path else ""
    sections[identifier] = (
        f'[{identifier}]\nsubmodule = "extensions/{identifier}"\n'
        f'{path_line}version = "{version}"\n'
    )
    return prefix + "\n".join(sections[name] for name in sorted(sections))


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def prepare(root, identifier, version, repo, source, path=""):
    if git(root, "status", "--porcelain"):
        raise marketplace.GateError("Catalog checkout must be clean")
    if not marketplace.REPO_RE.fullmatch(repo) or not marketplace.SHA_RE.fullmatch(
        source
    ):
        raise marketplace.GateError("Invalid source repository/commit")
    registry = root / "extensions.toml"
    next_registry = registry_entry(registry.read_text(), identifier, version, path)
    modules = root / ".gitmodules"
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(modules.read_text())
    section = f'submodule "extensions/{identifier}"'
    url = f"https://github.com/{repo}"
    if (
        config.has_section(section)
        and config[section].get("url", "").removesuffix(".git") != url
    ):
        raise marketplace.GateError("Existing submodule belongs to another repository")
    # git config understands Git's own quoting; do not rewrite unrelated sections.
    subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(modules),
            f"submodule.extensions/{identifier}.path",
            f"extensions/{identifier}",
        ],
        check=True,
        cwd=root,
    )
    subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(modules),
            f"submodule.extensions/{identifier}.url",
            url,
        ],
        check=True,
        cwd=root,
    )
    registry.write_text(next_registry)
    git(root, "add", ".gitmodules", "extensions.toml")
    git(
        root,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{source},extensions/{identifier}",
    )
    changed = set(git(root, "diff", "--cached", "--name-only").splitlines())
    if not changed.issubset(
        {".gitmodules", "extensions.toml", f"extensions/{identifier}"}
    ):
        raise marketplace.GateError("Catalog edit changed an unrelated extension")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-dir", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    try:
        receipt = json.loads(args.preflight.read_text())
        marketplace.validate_receipt(receipt, args.source, args.tag, catalog=True)
        prepare(
            args.catalog_dir,
            receipt["extensionId"],
            receipt["version"],
            receipt["repository"],
            args.source,
            receipt.get("extensionPath", ""),
        )
    except (
        marketplace.GateError,
        KeyError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"catalog: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
