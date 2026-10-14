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

## Choose your knowledge graph

For hover and replacement suggestions from an existing graph, add its absolute
JSON path to the project's `.zed/settings.json`:

```json
{
  "lsp": {
    "terraphim-lsp": {
      "initialization_options": {
        "thesaurus": "/absolute/path/to/brief.knowledge-graph.json"
      }
    }
  }
}
```

The default graph is empty. Export or compile an existing role's thesaurus to
JSON to use it here; this adapter has no named-role picker. You can author new
alternatives and export their document graph without loading an existing graph.

## Use the graph with Terraphim CLIs

Install `terraphim-grep` and `terraphim-agent` separately from the
[Terraphim clients releases](https://github.com/terraphim/terraphim-clients/releases/tag/v1.21.20).
The Zed extension does not install either CLI. After exporting your graph, search
notes by an authored synonym:

```sh
terraphim-grep Concern --search-only --haystack all --paths ./corpus \
  --thesaurus ./brief.knowledge-graph.json --json -n 3
```

You can also explicitly save a project decision to the agent's local memory:

```sh
terraphim-agent --format json memory capture \
  --content 'Risk requires a Decision: approve a second supplier as the mitigation.' \
  --provenance-tag 'public-project-brief'
MEMORY_ID='paste-the-returned-memory-id'
terraphim-agent memory show "$MEMORY_ID" --json
```

Set `MEMORY_ID` to the capture response's ID before running `memory show`. Memory uses the
agent's configured local store; capture is a separate action, not an automatic
import of the editor graph. Follow the [complete example](https://github.com/terraphim/zed-terraphim/blob/main/docs/cli-workflows.md) for the source
Markdown, exact Zed export steps and expected saved results.
