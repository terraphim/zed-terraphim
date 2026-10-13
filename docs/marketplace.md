# Public Zed publication

This repository continues the existing stock-Zed adapter. Gitea remains the
source of record; the GitHub mirror is the public build/catalog source. It does
not depend on or modify a Zed fork.

## Catalog package and remaining publication gates (2026-10-13)

`catalog/terraphim-lsp` is the separate **Terraphim LSP** catalog package. Its
Cargo library points to the existing `src/lib.rs`; the provisioning, settings
and all knowledge-graph behavior remain shared. The root `terraphim` package
continues to enable its existing LSP and MCP server. The catalog builds with
`public-catalog` and no `mcp` feature, so it registers only the language server
and skips the private-network Gitea download attempt. Both use the same pin and
checksum verification. Remove the legacy adapter before enabling the catalog
package, because they register the same language-server ID.

The catalog entry uses Zed's supported `path = "catalog/terraphim-lsp"` field.
CI checks both identities, equal dependency locks, shared source linkage and
absence of extra capabilities. It compiles/tests the catalog package separately
and saves its actual WASM bytes and hashes in `dist/catalog`. A build receipt
explicitly records `nativeQualified: false`; a passing build cannot attest to
manual Zed behavior or registry acceptance.

The live official registry had no Terraphim entry when checked on 13 October.
Publication still requires these actual dependencies:

1. A publicly downloadable LSP release with authored-synonym export. The
   existing `terraphim_lsp-v1.22.0-rc.3` pin returned HTTP 404 on public GitHub.
   Do not downgrade it, substitute local bytes or call internal access public
   installation proof. Update the shared pin only after the new immutable
   release is verified across all supported assets.
2. A scoped public source mirror. `github.com/terraphim/zed-terraphim` returned
   HTTP 404; copying private monorepo history is not part of this publication.
3. Manual stock-Zed qualification at the exact source commit submitted, then
   a human-authored catalog PR under the upstream AI policy. Upstream review
   and registry publication remain distinct from source or release publication.

Current official prerequisites require an LSP-only ID ending in `-lsp` or
`-language-server`, while MCP extensions contain one MCP server and nothing else:
<https://zed.dev/docs/extensions/publishing/prerequisites>. The existing legacy
package is preserved; this change does not modify the Zed application.

## CI and package release

`.github/workflows/ci.yml` runs on Linux and macOS for pull requests and main.
It uses the repository's pinned Rust toolchain and Cargo.lock. `scripts/ci.sh`
runs native and WASI Clippy with warnings denied, native tests, both WASI release
builds, the existing architecture guards, Python publication regressions, and
the existing deterministic `package.py` packager. No publication token is
available to this workflow. Existing Gitea workflows retain their own channel.

`.github/workflows/release.yml` accepts an existing `vX.Y.Z` or `vX.Y.Z-rc.N`
tag matching `extension.toml`. A tag push publishes only after all checks;
manual dispatch defaults to verification without publication. It never creates
or moves tags. A release source must be on the public mirror's default branch.

The public preflight compiles `examples/release-contract.rs`, which obtains the
pin and all six raw LSP candidates directly from the existing Rust
`provision::LSP` and `candidate_assets` types/functions. It anonymously downloads
`checksums.txt` and every named raw binary using ordinary GitHub URLs, verifies
SHA-256 and native executable format, and records the source/tag, URLs, sizes
and hashes. It does not execute foreign binaries or claim native-host UAT.
The internal Gitea source and PATH overrides cannot satisfy this gate.

After preflight, the tested WASI module is packaged again for the exact tag. The
publication job consumes only this run's artifact, validates its receipt,
archive layout, tagged source-file bytes, tested WASM hash and checksums, and verifies the remote tag still names the
source. The post-build package-qualification.json is published alongside the archive and checksums. It creates a draft, uploads missing assets, compares existing assets
byte-for-byte, and only then publishes. Existing bytes are never overwritten.
Three fresh anonymous downloads must match before it reports
`PUBLISHED_PUBLIC_VERIFIED`. A partial public release or different existing
bytes fails closed and requires diagnosis rather than a clobber operation.

Configure the `zed-release` GitHub environment according to the project's
release policy. Its job uses only the repository's `GITHUB_TOKEN` with
`contents: write`; PR CI remains read-only. Gitea tokens are not copied to
GitHub. GitHub publication does not imply a Gitea source sync or Zed catalog
acceptance.

## Catalog preparation and human submission

Zed publishes only after maintainers merge a PR into
[`zed-industries/extensions`](https://zed.dev/docs/extensions/publishing/publishing-guide).
The current [upstream AI policy](https://github.com/zed-industries/extensions/blob/main/AI_POLICY.md)
allows AI-assisted implementation but requires human-authored PR descriptions and
maintainer replies, and disallows autonomous-agent contributions. Build, package
and release CI remain automated; the upstream submission is a human action.

1. Publish reviewed source and the exact immutable dependency release. Test that
   exact source manually in stock Zed and save the output evidence described in
   [qualification.md](qualification.md).
2. Dispatch `catalog.yml` with its existing stable tag, the exact native-qualified
   source SHA and an HTTPS evidence URL. No cross-repository token is needed.
3. CI repeats tests and public download checks, then `prepare_catalog.py` checks
   out the official catalog, updates only this extension's gitlink, `.gitmodules`
   and `extensions.toml` (with the catalog subdirectory), and runs upstream sorting.
   Package install hooks are disabled; package tooling receives no GitHub token.
4. The artifact contains `catalog.patch`, `submission.json` and human handoff
   instructions. It records `HUMAN_SUBMISSION_REQUIRED`, exact source/tag/base,
   evidence URL and patch hash. It creates no fork, branch, PR or comment.
5. A human maintainer reviews the outputs, applies the patch to their personal
   catalog fork, writes the PR explanation in their own words and submits it.
   Keep one extension per PR and no more than three open PRs per submitter.
   After maintainer merge, verify the actual registry listing and downloaded
   extension; a prepared patch or accepted PR alone is not installation proof.

The retired `submit_catalog.py` exits before all remote actions, even if a token
is supplied. Regression tests apply the generated patch to a real clean Git
checkout, verify its three-file scope, reject unrelated changes and refuse
stale output directories. Action dependencies remain pinned to immutable SHAs.

## Shared source and the upstream builder

The repository subdirectory is supported by the current official builder:

- [Catalog checkout and path selection](https://github.com/zed-industries/extensions/blob/c63c15ce892e8ea02d0be53ae5d2526105e03519/src/package-extensions.js)
  initializes the complete submodule, then passes its selected extension path
  to the packaging CLI. It does not copy only the subdirectory before compilation.
- [CLI compile-before-copy sequence](https://github.com/zed-industries/zed/blob/36682547bea1c3d4fa60c08d341cf60081853941/crates/extension_cli/src/main.rs)
  compiles directly at the canonical source directory before copying runtime
  resources into the archive.
- [Cargo invocation](https://github.com/zed-industries/zed/blob/36682547bea1c3d4fa60c08d341cf60081853941/crates/extension/src/extension_builder.rs)
  uses the extension directory as its working directory, retaining the enclosing
  checkout. Thus `../../src/lib.rs` remains available during compilation.

Both package builds pass locally using this layout. That source inspection and
build result do not claim an upstream CI run or native manual acceptance.

## Local verification

Python 3.11+, Rust via rustup, curl, Git and gh are required; catalog automation
also uses npm for the upstream formatter. No publication is performed by:

```sh
bash scripts/ci.sh
cargo run --locked --offline --example release-contract
python3 scripts/marketplace.py --tag vX.Y.Z --repo OWNER/REPOSITORY --out /tmp/zed-public-preflight-new
# Catalog preflight additionally requires exact native qualification evidence:
python3 scripts/marketplace.py --catalog --extension-path catalog/terraphim-lsp --tag vX.Y.Z --repo OWNER/REPOSITORY --qualified-commit FULL_SHA --qualification-url https://example.com/actual-evidence --out /tmp/zed-catalog-preflight-new
```

The last command requires a clean checkout at the existing tag and a fresh
output directory. It is intentionally expected to fail for the current
unpublished public rc.3 dependency. A failed gate is a blocker, not successful
installation evidence. Actual release/catalog commands must be run only after
reviewing the exact tag and the successful receipt.
