#!/usr/bin/env bash
# One test/build contract shared by GitHub and local release preparation.
set -euo pipefail
cd "$(dirname "$0")/.."
export CARGO_BUILD_BUILD_DIR="${CARGO_BUILD_BUILD_DIR:-target/build}"
cargo fmt --all -- --check
cargo fetch --locked
cargo clippy --locked --offline --all-targets --all-features -- -D warnings
cargo clippy --locked --offline --target wasm32-wasip2 --all-features -- -D warnings
cargo test --locked --offline --all-targets --all-features
cargo build --locked --offline --release --target wasm32-wasip2
sh scripts/guards.sh
python3 scripts/package.py --wasm "${CARGO_TARGET_DIR:-target}/wasm32-wasip2/release/zed_terraphim.wasm"

bash scripts/catalog-ci.sh

python3 -m unittest discover -s scripts -p 'test_*.py'
