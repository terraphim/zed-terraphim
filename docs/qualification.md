# Qualification

The public source snapshot is derived from the reviewed extension changes at
`0db254a96c5f6b7e41e81516a720ea6d5d847ffc`. Source provenance and per-file hashes
are supplied separately with the snapshot review. Public CI must qualify its
own commit before a release or catalog submission.

## Verified implementation checks

The existing adapter passed 75 native Rust tests; the separate LSP-only package
passed 62 native Rust tests. Native and WASI Clippy ran with warnings denied;
both WASI builds passed. There are 55 Python tests covering packaging integrity,
publication checks, catalog path validation and actual Git patch application.

The LSP-only build shares the existing Rust source and dependency lock, disables
MCP registration and skips private-network provisioning. Neither build tests nor
protocol tests certify native editor interaction or public release installation.

## Required native and release checks

Before qualification, bind the exact extension source SHA, LSP release tag,
server executable SHA-256, Zed version and fixture source bytes. Use an isolated
public project brief and save each resulting file.

1. Install the exact catalog source in stock Zed with the legacy adapter disabled.
2. Start with a clearly identified preauthored annotation or existing KG term,
   swap an alternative, and save, close and reopen the Markdown document.
   Inspect the saved annotations and resulting text; verify undo and redo bytes.
   Separately start from plain Markdown and use the prepared RC4
   `terraphim.alternative.add_and_apply` command in Zed's generic picker with an
   explicit URI/range/text object. Inspect the newly created annotation and
   repeat save/reopen and undo/redo. A seeded fixture cannot qualify authoring.
   The original `terraphim.alternative.add` still returns an edit that the
   generic picker only logs; use the explicit apply command for this check.
3. Choose a trim level and **Done**. Save/reopen and inspect persisted ghost
   anchors, then verify subsequent edits keep the anchors aligned.
4. Export the document knowledge graph twice from the native code action. Verify
   the destination files, matching concept IDs for authored synonyms, equal
   parsed graph data and unchanged source bytes. JSON object key order may vary.
   Test refusal of a dirty output destination.
5. Query the saved graph with released terraphim-grep. Retain baseline, graph-
   enabled retrieval and optional synthesis as separate outputs.
6. Remove the binary override, install from the published source and anonymously
   downloadable release, then confirm the actual provisioned binary's checksum
   and restart from its verified cache.

## Bounded native candidate evidence (14 October 2026)

Stock Zed 1.23.3 with the installed legacy adapter 0.2.0 and an explicit candidate
LSP override completed swaps of a preauthored Risk/Concern annotation, saved
undo/redo, close/reopen, and two graph exports. The saved graph assigns both
terms the same concept ID. Repeated export preserved the source bytes and parsed
graph data; JSON object key order varied. Released terraphim-grep 1.21.19 queried
the actual saved graph: a Concern query changed from zero baseline matches to
one Risk passage, with no synthesis requested.

The candidate LSP was built from source
`34b890841184fd96208fb11f4e2e59aceee90c7a`; its executable SHA-256 was
`a79b5ac5f66c7823b1eb8714c13aee7280c6b510afb851ad2bfafcf53946fde2`.
This run used the existing legacy adapter, not an installed catalog package or
publicly provisioned LSP release. The fixture supplied the alternatives before
native input; it does not demonstrate arbitrary-alternative UI creation.

The completed native pass also persisted 12 ghosts through Trim Done, save and
reopen. A subsequent eight-character edit shifted the saved span and ghost
anchors by eight; each anchor still matched its text. The clean Markdown export
contained exactly the expected 1,349 bytes after removing the marked passages
and annotation fence. An unsaved export destination was refused, preserving both
its disk contents and the user's pending edit. These checks use the settled saved
files after the asynchronous annotation update completes.

The reviewed core changes subsequently merged as
`81afcb8750938495a7176466cf19ebbc27889292`; the LSP/core source and dependency lock
are unchanged from the native-tested candidate. Post-merge tests and
warnings-denied Clippy passed. A source merge does not qualify a new release
binary.

The exact catalog package installation and public LSP provisioning checks remain
pending. All 41 original editor requirements are not certified for stock Zed.

## New-alternative candidate check — 14 October 2026

Stock Zed 1.23.3 ran the new `terraphim.alternative.add_and_apply` command through
its generic LSP picker. A single JSON object supplied a range over `Risk` and
the new text `Concern`; no annotation or synonym relationship existed in the
initial fixture. Zed applied and saved the generated annotation. Native undo
and save restored the original plain Markdown; redo and save restored the
annotation byte for byte. After close/reopen, native graph export produced
`risk` and `concern` with the same concept ID and preserved the source.

This used an explicit candidate binary override (SHA-256
`c7fd75a97184764860b0a7f5a129466e28f817e689f03ca17176d2545a352ba9`).
It qualifies the manual JSON command path, not a selection-aware text prompt,
default release download, or catalog installation. The earlier fixture-based
checks above retain their original scope. See [authoring](alternative-authoring.md).
The Zed application fork is outside this package.

## Historical RC4 installation preparation (14 October 2026)

The earlier shared pin targeted `terraphim_lsp-v1.22.0-rc.4`, built from public
crates.io dependencies. Its crate was published, but the GitHub binary release
failed in the two musl lanes. Its [prepared checklist](rc4-install-qualification.md)
and the retained RC3 fixtures do not prove a default release installation.

## Historical RC5 installation preparation (14 October 2026)

RC5 published its crate and built all six binaries, but final release assembly
rejected x86_64 log names. Its GitHub binary release was not published. The
[RC5 checklist](rc5-install-qualification.md) and untouched isolated input fixture
remain historical preparation, not proof of a default installation.

## Released RC6 default-provisioning check (14 October 2026)

Source `140e25b573865efa372418ac5475771a12c4785d` installed the catalog adapter in
an empty stock-Zed 1.23.3 profile and downloaded RC6 through its pinned public
asset URLs, with no binary override or PATH fallback. The actual universal macOS
server SHA-256 was `3b07976ffde477cbbe2705b078d64188fa2dd27e9a93a6b4052e8f152a4510f3`.
A restart reused the verified cache. Native authoring, swap, saved undo/redo,
reopen, two graph exports, Trim, clean export and released-grep retrieval produced
saved outputs. This was a Zed dev build of the catalog source, not installation
of a GitHub-published extension archive.

The dirty-JSON regression **failed**: graph export overwrote an unsaved interior
change in an open JSON destination. Native Undo recovered the test edit. A dirty
Markdown clean-export destination was correctly refused; that does not qualify
JSON protection. The earlier append-only JSON test also did not prove refusal.
The discovered JSON failure must be repaired and verified with a new released
server and exact catalog source before release admission.

The earlier [RC6 checklist](rc6-install-qualification.md) preserves the original
prepared steps. Its earlier metadata-API HTTP 403 profile remains separate from
the successful direct-download profile. RC4/RC5 source and release history above
remain unchanged.

## RC7 dirty-destination repair (14 October 2026)

The public [RC7 server release](https://github.com/terraphim/terraphim-ai/releases/tag/terraphim_lsp-v1.22.0-rc.7)
is built from source `4fb62d337c306a9105c5e872f3400f3052a2caef`. All six binary
assets were anonymously downloaded and checked against the release checksums.
Actual downloaded macOS ARM64 and universal binaries passed protocol checks for
JSON and JSONC dirty-destination refusal after buffer changes, with a changed
pending graph payload.
Those process-level checks do not establish stock-Zed UI behavior.

The catalog registers JSON and JSONC as passive buffers for this protection;
they receive no Markdown alternatives, Lab analysis or diagnostics. Follow the
[RC7 checklist](rc7-install-qualification.md) on the final source to reproduce the
previous interior-edit failure, require visible refusal and preserve both the
unsaved buffer and disk. Publication also requires the remaining native checks
and a separately verified compiled-package installation. Historical RC6 evidence
above remains unchanged.

## Compiled release-package qualification

Follow [released-package installation](released-package-install.md) in a second
empty profile. Record the anonymous download checksum, exact archive files and
loaded WASM hash, with no Cargo source or compiler invocation. Then perform the
native checks above and save their actual outputs. Keep this receipt separate
from the source dev-build receipt; identify which bytes each run exercised.
Official Zed catalog installation still requires upstream acceptance and an
actual registry install. None of these bounded checks certifies all 41 browser
requirements for stock Zed.

## Native source receipt schema

The manually reviewed source-install receipt is JSON at an immutable raw GitHub
URL in this repository: `https://raw.githubusercontent.com/terraphim/zed-terraphim/<40-character-evidence-commit>/docs/qualifications/<receipt>.json`.
The evidence commit may follow the tested source, provided `qualifiedCommit`
remains the exact tested/tagged source. Publish only sanitized public fixtures;
keep local absolute paths, account details and private original receipts outside
this repository.

The schema requires:

- `schema: 1`, `status: "PASS"`, `scope: "stock-zed-source"` and exact `qualifiedCommit`.
- `extensionId: "terraphim-lsp"`, `extensionPath: "catalog/terraphim-lsp"` and the catalog `version`.
- `sourceInstallWasm` containing the actual native dev-install module's SHA-256 and byte count.
- `server` containing `releaseTag`, `sha256` and `bytes`, matching an anonymously verified asset of that pinned public release.
- `checks` with PASS for `defaultProvisioning`, `cacheRestart`, `createApplySaveUndoRedoReopen`, `synonymGraphExportTwice`, `dirtyJsonRefusal`, `trimDoneAnchorShift`, `cleanExportDirtyRefusal` and `releasedGrepSharedSynonym`.
- Nonempty `savedOutputs`, each with a unique public filename `name`, actual `sha256` and `bytes`. Inputs must remain identified separately in the human-reviewed evidence.

CI checks these declarations and binds the downloaded receipt's exact bytes to
preflight/package qualification. It does not rerun native UI interactions or
substitute the receipt's dev-module hash for the different CI module. Publication
uses the saved receipt from the original verify-job artifact. After publication,
a separate actual downloaded-package installation receipt identifies the CI WASM
loaded in stock Zed and its resulting saved outputs.
