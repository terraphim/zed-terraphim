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

The shared LSP supports Markdown alternatives, hover, diagnostics and code actions.
It does not embed the browser editor's visual panels. Alternatives and authored
`synonyms::` relationships use Terraphim's existing Rust types and crates.

## Publication status

This is scoped extension source with public build/release CI. It is not yet an
installable Zed registry entry. The current pin requires a new public LSP release
with graph export and native qualification before marketplace submission.

Automatic provisioning supports macOS and Linux on x86_64 and ARM64. Windows
automatic provisioning is not qualified; an explicit binary path remains possible.

For development, use **Extensions → Install Dev Extension** and select either
this root directory or `catalog/terraphim-lsp`. Remove the other adapter first.
Use `lsp.terraphim-lsp.binary.path` for an explicitly selected candidate server;
record its source and SHA-256 when qualifying it.

## Build and releases

```sh
bash scripts/ci.sh
```

CI checks locked native/WASI builds, warnings-denied Clippy, actual package bytes
and publication regressions. Reviewed immutable tags drive GitHub releases after
anonymous dependency-download checks and artifact/source binding.

[Marketplace instructions](docs/marketplace.md) describe the gates and Zed's
human-authored catalog submission requirement. [Qualification](docs/qualification.md)
distinguishes build tests from native Zed and public installation evidence.

Licensed under [Apache-2.0](LICENSE).
