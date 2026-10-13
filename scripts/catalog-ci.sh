#!/usr/bin/env bash
# Qualify the LSP-only package using the shared adapter sources and lockfile.
set -euo pipefail
cd "$(dirname "$0")/.."
manifest=catalog/terraphim-lsp/Cargo.toml
cargo fmt --manifest-path "$manifest" -- --check
cargo fetch --locked --manifest-path "$manifest"
cargo clippy --locked --offline --manifest-path "$manifest" --all-targets -- -D warnings
cargo clippy --locked --offline --manifest-path "$manifest" --target wasm32-wasip2 -- -D warnings
cargo test --locked --offline --manifest-path "$manifest" --all-targets
cargo build --locked --offline --manifest-path "$manifest" --release --target wasm32-wasip2
python3 scripts/catalog_package.py --wasm "${CARGO_TARGET_DIR:-catalog/terraphim-lsp/target}/wasm32-wasip2/release/zed_terraphim_lsp.wasm"
