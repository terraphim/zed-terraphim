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

## Prospective public RC5 installation (14 October 2026)

The prepared shared pin is `terraphim_lsp-v1.22.0-rc.5`. Its public assets,
checksums and native default-download results remain pending. The candidate
checks above retain their original identities. The next run follows the
[RC5 isolated installation checklist](rc5-install-qualification.md), using the
catalog package without a binary override and inspecting the actual provisioned
path. A successful local build alone cannot qualify release installation.
