#!/usr/bin/env python3
"""Check and stage the exact compiled LSP-only package for native qualification."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

import marketplace
import package

PATH = "catalog/terraphim-lsp"


def validate_source(root):
    """Validate the catalog identity and shared implementation without mutation."""
    catalog_root = root / PATH
    manifest = marketplace.read_manifest(root, PATH)
    marketplace.catalog_manifest(manifest, "v" + manifest["version"])
    legacy = tomllib.loads((root / "extension.toml").read_text())
    cargo = tomllib.loads((catalog_root / "Cargo.toml").read_text())
    shared = tomllib.loads((root / "Cargo.toml").read_text())
    if manifest["id"] != "terraphim-lsp" or manifest.get("context_servers"):
        raise marketplace.GateError(
            "Catalog package must contain only the Terraphim LSP"
        )
    if manifest.get("capabilities"):
        raise marketplace.GateError(
            "Catalog must not request process or filesystem capabilities"
        )
    if legacy["id"] != "terraphim" or not legacy.get("context_servers"):
        raise marketplace.GateError("Preserve the existing combined adapter identity")
    if manifest["language_servers"] != legacy["language_servers"]:
        raise marketplace.GateError("The two packages must register the same LSP")
    if cargo["lib"]["path"] != "../../src/lib.rs":
        raise marketplace.GateError(
            "The catalog must compile the existing adapter source"
        )
    if cargo["features"]["default"] != ["public-catalog"]:
        raise marketplace.GateError(
            "Catalog defaults must disable MCP and private-network downloads"
        )
    if shared["features"]["default"] != ["mcp"]:
        raise marketplace.GateError("Legacy default must retain MCP")
    if cargo["dependencies"] != shared["dependencies"]:
        raise marketplace.GateError("Shared dependency versions drifted")
    expected_lock = (
        (root / "Cargo.lock")
        .read_text()
        .replace('name = "zed-terraphim"', 'name = "zed-terraphim-lsp"')
    )
    if (catalog_root / "Cargo.lock").read_text() != expected_lock:
        raise marketplace.GateError(
            "Catalog lockfile must retain the reviewed dependencies"
        )
    if (catalog_root / "LICENSE").read_bytes() != (root / "LICENSE").read_bytes():
        raise marketplace.GateError("Catalog license differs from the reviewed source")
    return manifest


def stage(root, wasm, output):
    """Save checked bytes and provenance; this receipt never certifies native UAT."""
    manifest = validate_source(root)
    data = wasm.read_bytes()
    if not data.startswith(b"\x00asm") or not 100_000 < len(data) < 450_000:
        raise marketplace.GateError(
            "Catalog WASM is not a size-qualified adapter build"
        )
    output.mkdir(parents=True, exist_ok=True)
    for name in package.FILES:
        shutil.copyfile(root / PATH / name, output / name)
    (output / "extension.wasm").write_bytes(data)
    source = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    receipt = {
        "status": "BUILD_VERIFIED",
        "nativeQualified": False,
        "source": source,
        "extensionPath": PATH,
        "extensionId": manifest["id"],
        "version": manifest["version"],
        "files": {
            name: hashlib.sha256((output / name).read_bytes()).hexdigest()
            for name in [*package.FILES, "extension.wasm"]
        },
        "sourceTreeDirty": bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=root, text=True
            ).strip()
        ),
    }
    (output / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wasm", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=package.ROOT / "dist/catalog")
    args = parser.parse_args()
    print(json.dumps(stage(package.ROOT, args.wasm, args.out), indent=2))


if __name__ == "__main__":
    main()
