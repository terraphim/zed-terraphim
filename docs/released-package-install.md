# Install the compiled Terraphim LSP package

Use a release from [terraphim/zed-terraphim](https://github.com/terraphim/zed-terraphim/releases)
that includes all three files:

- `terraphim-lsp-<version>.tar.gz`
- `SHA256SUMS`
- `package-qualification.json`

Check that the receipt names `terraphim-lsp`, source path
`catalog/terraphim-lsp`, the intended tag and archive checksum. Verify the archive
against `SHA256SUMS` before extracting it into a new empty directory. The extracted
directory must contain exactly LICENSE, README.md, extension.toml and extension.wasm.
The manifest ID must be `terraphim-lsp`; compare all four file hashes against the
receipt. Do not replace files with a local build or add Cargo.toml/Rust source.

In stock Zed, open **Extensions → Install Dev Extension** and choose that extracted
directory. Although the UI calls it a dev extension, this directory contains the
released module and no source to compile. Zed loads the existing extension.wasm.
The source-development route instead selects `catalog/terraphim-lsp` in a Git
checkout and compiles a different dev module; its hashes may differ.

Disable/remove the combined legacy Terraphim adapter before enabling this package
because both register the same LSP. The language server is downloaded from the
pinned public GitHub release, verified against its checksum, and reused on
restart. Keep `lsp.terraphim-lsp.binary.path` unset to verify default provisioning.
The catalog package has no PATH fallback and no private-network download.

For release qualification, use a fresh isolated Zed profile and disposable project.
Record the archive/module checksums before installation and again from the actual
installed path afterward. Confirm the module was not rebuilt, record the provisioned
server/version/checksum marker, and save the create/swap/undo/redo/reopen/export,
dirty-destination refusal, Trim and grep outputs described in
[qualification](qualification.md). A downloaded input is not evidence of successful
execution; the receipt must include the actual resulting files.

This is manual installation of a released package. An official catalog install is
available only after Zed's upstream review and registry build; it is a separate
acceptance check. The [publication instructions](marketplace.md) describe the
CI and human-authored catalog submission gates.
