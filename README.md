# Terraphim for Zed

Knowledge-graph hover, synonym code actions and writing annotations for Markdown
in stock Zed. The adapter launches Terraphim's shared language server; it contains
no separate knowledge-graph engine and does not require a Zed application fork.

## Packages

- `catalog/terraphim-lsp`: the **Terraphim LSP** package for the Zed registry.
  It compiles the existing Rust adapter with MCP disabled, and provisions checked
  public GitHub binaries. See its [README](catalog/terraphim-lsp/README.md).
- Repository root: the existing **Terraphim** adapter with both the LSP and MCP
  server. Its default behavior and extension ID remain compatible with existing
  installations. Use only one LSP adapter in a workspace.

In stock Zed, code actions swap existing KG synonyms and alternatives already
saved in a Markdown annotation. Hover, diagnostics and writing actions use the
shared LSP. To create an alternative, use `terraphim.alternative.add_and_apply`
in Zed's built-in LSP command picker: supply a JSON object with the document URI,
selection range and new text. The server asks Zed to apply the annotation edit.
See the [command-picker walkthrough](docs/alternative-authoring.md).
The original `terraphim.alternative.add` still returns an edit for clients that
apply it themselves. The adapter does not infer the current selection or provide
the browser editor's visual panels.
Alternatives and authored `synonyms::` relationships use Terraphim's existing
Rust types and crates.

## Publication status

The public release workflow packages **Terraphim LSP**, the catalog variant.
[Released-package installation](docs/released-package-install.md) explains how
to verify and load its compiled WASM without rebuilding it. Official Zed catalog
availability requires a separate upstream review and registry build.

[Qualification evidence](docs/qualification.md) distinguishes source tests,
released-package installation and saved editor outputs. Each native receipt
identifies the exact extension source, WASM and language-server binary used.

Automatic provisioning supports macOS and Linux on x86_64 and ARM64. Windows
automatic provisioning is not qualified; an explicit binary path remains possible.

For development, use **Extensions → Install Dev Extension** and select either
this root directory or `catalog/terraphim-lsp`. Remove the other adapter first.
Use `lsp.terraphim-lsp.binary.path` for an explicitly selected candidate server;
record its source and SHA-256 when qualifying it.

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
import of the editor graph. Follow the [complete example](docs/cli-workflows.md) for the source
Markdown, exact Zed export steps and expected saved results.

## Build and releases

```sh
bash scripts/ci.sh
```

CI checks locked native/WASI builds, warnings-denied Clippy, actual package bytes
and publication regressions. Immutable tags run verification. A manual dispatch at the exact tag publishes
the catalog package after native source qualification, anonymous dependency
checks and artifact/source binding; retries reuse the original CI artifact.

[Marketplace instructions](docs/marketplace.md) describe the gates and Zed's
human-authored catalog submission requirement. [Qualification](docs/qualification.md)
distinguishes build tests from native Zed and public installation evidence.

Licensed under [Apache-2.0](LICENSE).
