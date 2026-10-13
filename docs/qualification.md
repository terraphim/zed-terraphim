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
2. Create/swap alternatives and save, close and reopen the Markdown document.
   Inspect the saved annotations and resulting text; verify undo and redo bytes.
3. Choose a trim level and **Done**. Save/reopen and inspect persisted ghost
   anchors, then verify subsequent edits keep the anchors aligned.
4. Export the document knowledge graph twice from the native code action. Verify
   the destination files, matching concept IDs for authored synonyms, stable
   output and unchanged source. Test refusal of a dirty output destination.
5. Query the saved graph with released terraphim-grep. Retain baseline, graph-
   enabled retrieval and optional synthesis as separate outputs.
6. Remove the binary override, install from the published source and anonymously
   downloadable release, then confirm the actual provisioned binary's checksum
   and restart from its verified cache.

Current candidate native requalification is pending. The Mac lock prevented
native input on 13 October; no save/reopen, Done or export success is claimed
from that attempt. All 41 original editor requirements are not certified for
stock Zed. The Zed application fork is outside this package.
