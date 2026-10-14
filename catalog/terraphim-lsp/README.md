# Terraphim LSP for Zed

Knowledge-graph hover, synonym code actions, diagnostics and writing annotations
for Markdown in stock Zed. This catalog package uses the same Rust adapter and
pinned language server as the existing Terraphim extension. The language server
uses Terraphim's shared crates for alternatives and `synonyms::` relationships.

This package supplies the language server only. It downloads verified release
assets from GitHub, or uses the user's explicit `lsp.terraphim-lsp.binary.path`.
It does not provide the browser editor's panels or an MCP server.

The prepared dependency is `terraphim_lsp-v1.22.0-rc.6`. Public release downloads
and a clean default installation remain pending; the historical RC3 test
checksums are not evidence for this pin. Follow the
[installation checklist](../../docs/rc6-install-qualification.md) before publishing.

## Install and migrate

For local qualification, choose **Extensions → Install Dev Extension** and select
this `catalog/terraphim-lsp` directory. A catalog listing is available only after
Zed maintainers accept the submission and the registry build completes.

Remove/disable the legacy **Terraphim** extension before enabling **Terraphim LSP**:
both register the same `terraphim-lsp` server for Markdown. Existing settings under
`lsp.terraphim-lsp` still apply. Users needing the legacy MCP server should keep the
combined adapter until they have configured the MCP server separately; do not run
both LSP adapters on the same workspace.

The source is shared through the Cargo library path; no knowledge-graph or
provisioning implementation is copied into this package. See the repository's
`docs/marketplace.md` for CI, public release checks and native acceptance evidence.
