# Public Zed publication

This repository continues the existing stock-Zed adapter. Gitea remains the
source of record; the GitHub mirror is the public build/catalog source. It does
not depend on or modify a Zed fork.

## Catalog package and publication gates

`catalog/terraphim-lsp` is the separate **Terraphim LSP** catalog package. Its
Cargo library points to the existing `src/lib.rs`; the provisioning, settings
and all knowledge-graph behavior remain shared. The root `terraphim` package
continues to enable its existing LSP and MCP server. The catalog builds with
`public-catalog` and no `mcp` feature, so it registers only the language server
and skips the private-network Gitea download attempt. The catalog selects from
the pinned public `checksums.txt` using fixed release URLs, without a metadata
API request or PATH fallback. The explicit binary path remains supported. The
legacy adapter retains Gitea-first, GitHub API discovery and PATH fallback; MCP
keeps its independent pin and discovery. Both LSP packages use the same pin and
checksum verification. Remove the legacy adapter before enabling the catalog
package, because they register the same language-server ID.

The catalog entry uses Zed's supported `path = "catalog/terraphim-lsp"` field.
CI checks both identities, equal dependency locks, shared source linkage and
absence of extra capabilities. It compiles/tests the catalog package separately
and saves its actual WASM bytes and hashes in `dist/catalog`. A build receipt
explicitly records `nativeQualified: false`; a passing build cannot attest to
manual Zed behavior or registry acceptance.

Source builds, native source qualification, GitHub packages and official catalog
installation are distinct checks. Before releasing the catalog package, verify
the exact pinned public language-server assets, complete the native checklist
at the tagged extension source, and retain the saved output files. After release,
install the downloaded compiled package and repeat those checks without a rebuild.
[Qualification](qualification.md) retains the dated candidate and released-binary
results, including discovered failures. [Released-package installation](released-package-install.md)
describes how the artifact bytes are preserved through native testing.

An upstream catalog PR must be human-authored under Zed's policy. Acceptance and
registry publication remain separate from this repository's source/release CI.

The scoped public source prerequisite is now satisfied. On 13 October, all 46
files at [the initial public commit](https://github.com/terraphim/zed-terraphim/tree/1fc332292ea41ae98ed55bd97b2daaa0ce48bcd5)
were fetched anonymously and matched the reviewed SHA-256 values and sizes.
That commit has no parents: private Git history was not copied. Source
availability does not certify the remaining LSP, native-host or registry gates.

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
tag matching the catalog manifest. Tag pushes verify the catalog package but do
not publish. Manual dispatch defaults to verification. To publish, dispatch at
that exact tag ref with `publish=true`, the exact native-tested `qualified_commit`
and an immutable raw-GitHub `qualification_url` at a full 40-character commit
in this source repository. CI downloads that JSON, validates its catalog/source
identity, named native checks and saved-output hashes, and requires its recorded
server hash/size to match a verified asset from the pinned public LSP release.
Its source-install WASM hash remains distinct from the CI release module; see the
[receipt schema](qualification.md#native-source-receipt-schema). Catalog publication requires a stable
extension tag. The protected `zed-release` environment retains its tag-only policy;
no branch dispatch can authorize a different tag through an input.

The public preflight executes `examples/release-contract.rs` with the catalog
feature set and obtains the actual `configured_lsp()` contract. It requires fixed
public checksum discovery, no private download and no PATH fallback, then
anonymously downloads and verifies every raw pinned LSP target. It records source,
tag, URLs, sizes and hashes. It does not execute foreign binaries or claim UAT.

The workflow uses the catalog build from `catalog-ci.sh`. `catalog_package.py`
checks the shared source, manifest, locked dependencies, no-MCP policy and module
size, then reuses the deterministic packager to create `terraphim-lsp-<release>.tar.gz`.
The archive contains the catalog LICENSE, README, manifest and exact compiled
`extension.wasm`; legacy root artifacts remain test outputs and are not published
by this workflow. The qualification receipt binds the catalog source path/ID,
tagged file bytes, tested module, archive and checksum manifest.

The publish job consumes the verify job's immutable **artifact ID**. It validates
all bytes and the original native source receipt again and verifies the remote tag still resolves to the tested source.
It creates a draft, uploads only missing assets, compares existing assets byte for
byte, and publishes only after they match. No tag moves, rebuilds, clobber uploads
or repairs of incomplete public releases occur. A failed publish job can retry
against the original artifact and draft. Fresh anonymous downloads of the archive,
checksums and qualification receipt must match before publication is reported.

Freeze generic documentation before native qualification. A normal merge can
preserve the tested PR head as an ancestor of main; tag that exact head. A later
docs-only commit may hold a sanitized UAT receipt while `qualified_commit` still
names the tested source. Finally save a separate receipt for installation of the
actual downloaded CI module; a source dev-build receipt cannot substitute for it.

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
python3 scripts/marketplace.py --catalog --extension-path catalog/terraphim-lsp --tag vX.Y.Z --repo OWNER/REPOSITORY --qualified-commit FULL_SHA --qualification-url "https://raw.githubusercontent.com/OWNER/REPOSITORY/<40-character-evidence-commit>/docs/qualifications/native.json" --out /tmp/zed-catalog-preflight-new
```

Replace OWNER/REPOSITORY with this public source repository, FULL_SHA with the
exact native-tested source, and the evidence-commit placeholder with the full
40-character Git commit containing the sanitized JSON receipt. A branch name,
mutable URL or unrelated repository is rejected. The last command requires a
clean checkout at the existing tag and a fresh output directory.

The intended first catalog package tag is `v0.2.0`, matching the catalog manifest.
It must be created only after the final source checks and native qualification
pass. The language-server dependency is pinned separately to the verified public
[`terraphim_lsp-v1.22.0-rc.7` release](https://github.com/terraphim/terraphim-ai/releases/tag/terraphim_lsp-v1.22.0-rc.7);
a stable extension version does not change that server's prerelease status.
The catalog attaches JSON and JSONC only for passive export-destination tracking;
Markdown features remain restricted to Markdown. Actual release/catalog commands require
the reviewed exact tag and successful receipts; a failed gate is not installation
evidence.
