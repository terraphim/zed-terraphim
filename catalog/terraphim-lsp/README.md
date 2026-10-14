# Terraphim LSP for Zed

Knowledge-graph hover, synonym code actions, diagnostics and writing annotations
for Markdown in stock Zed. This catalog package uses the same Rust adapter and
pinned language server as the existing Terraphim extension. The language server
uses Terraphim's shared crates for alternatives and `synonyms::` relationships.

JSON and JSONC are attached only to track open export destinations. Unsaved
changes cause graph export to refuse the write, preserving the buffer and disk.
They do not receive Markdown alternatives, Lab analysis or diagnostics.

This package supplies the language server only. It downloads verified release
assets from fixed, pinned GitHub URLs without a metadata API request or PATH
fallback, or uses the user's explicit `lsp.terraphim-lsp.binary.path`.
It does not provide the browser editor's panels or an MCP server.

The language-server version is pinned in the shared adapter source. Each release
binds that dependency, the extension source and compiled package bytes in its
qualification receipt. See the repository's
[qualification evidence](https://github.com/terraphim/zed-terraphim/blob/main/docs/qualification.md).

## Install and migrate

For a precompiled GitHub release, verify its checksums and select the extracted
four-file directory in **Extensions → Install Dev Extension**. It contains the
released `extension.wasm` and no Cargo source; Zed loads those exact bytes.
Follow the [released-package instructions](https://github.com/terraphim/zed-terraphim/blob/main/docs/released-package-install.md).

For source development, select this `catalog/terraphim-lsp` source directory
instead; Zed compiles a dev build. A catalog listing is available only after
Zed maintainers accept the submission and the registry build completes.

Remove/disable the legacy **Terraphim** extension before enabling **Terraphim LSP**:
both register the same `terraphim-lsp` server for Markdown. Existing settings under
`lsp.terraphim-lsp` still apply. Users needing the legacy MCP server should keep the
combined adapter until they have configured the MCP server separately; do not run
both LSP adapters on the same workspace.

The source is shared through the Cargo library path; no knowledge-graph or
provisioning implementation is copied into this package. See the repository's
`docs/marketplace.md` for CI, public release checks and native acceptance evidence.
