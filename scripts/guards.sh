#!/bin/sh
# Architecture guards run by CI after the release wasm build.
#   I4 thin adapter: no terraphim_* crate in the wasm dependency tree, and the
#      release wasm stays under a size budget.
#   I5 no process execution: extension.toml declares no capabilities at all
#      (so no process:exec).
# Run from the repository root after:
#   cargo build --release --target wasm32-wasip2
set -eu

# Release wasm size at the time of writing: 353501 bytes (2026-10-06). The
# budget leaves about 25% headroom; raise it only with a reason in the commit.
WASM_BUDGET_BYTES=450000

fail=0

# I4a: dependency names, any version, normal edges, wasm target.
terraphim_crates=$(cargo tree --offline --prefix none --edges normal --target wasm32-wasip2 |
    awk '/^terraphim/ { print $1 }' | sort -u)
if [ -n "$terraphim_crates" ]; then
    echo "I4 violated: terraphim crates in the wasm dependency tree:" >&2
    echo "$terraphim_crates" >&2
    fail=1
else
    echo "I4 ok: no terraphim_* crates in the dependency tree"
fi

# I4b: size budget.
wasm="${CARGO_TARGET_DIR:-target}/wasm32-wasip2/release/zed_terraphim.wasm"
if [ ! -f "$wasm" ]; then
    echo "I4: $wasm not found; build it first" >&2
    exit 2
fi
size=$(wc -c <"$wasm" | tr -d ' ')
if [ "$size" -gt "$WASM_BUDGET_BYTES" ]; then
    echo "I4 violated: $wasm is $size bytes, budget $WASM_BUDGET_BYTES" >&2
    fail=1
else
    echo "I4 ok: wasm is $size bytes (budget $WASM_BUDGET_BYTES)"
fi

# I5: no capability declarations (they are how process:exec is requested).
capabilities=$(awk '/^[[:space:]]*(\[\[?capabilities|capabilities[[:space:]]*=)|process:exec/ { print NR ": " $0 }' extension.toml)
if [ -n "$capabilities" ]; then
    echo "I5 violated: extension.toml declares capabilities:" >&2
    echo "$capabilities" >&2
    fail=1
else
    echo "I5 ok: extension.toml declares no capabilities"
fi

exit "$fail"
