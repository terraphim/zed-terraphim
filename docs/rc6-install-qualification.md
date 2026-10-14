# RC6 default-install qualification

Status: RC6 public release and all six binary checksums verified on 14 October;
fresh native installation is pending after a real metadata API HTTP 403 failure. The [RC4 checklist](rc4-install-qualification.md) and
[RC5 checklist](rc5-install-qualification.md) are retained as history. RC4 failed
in the musl build lanes; RC5 built all six binaries, but final release assembly
rejected x86_64 log names. Neither GitHub binary release was published. Their
crates and tags are unchanged by this recovery.
Do not publish this extension pin or submit its catalog entry before the gates
below pass. No hash in the historical RC3 fixtures is reused as an RC6 hash.

## Dependency and source identity

The shared LSP pin is `terraphim_lsp-v1.22.0-rc.6` in the public
`terraphim/terraphim-ai` repository. The catalog package disables the internal
Gitea attempt and GitHub metadata API. It downloads fixed URLs under the exact
release tag and selects the first supported asset present in `checksums.txt`.
It never searches PATH after a failed download. Explicit `binary.path` settings
remain supported. The legacy combined adapter preserves its source order,
GitHub API discovery, PATH fallback and independent MCP configuration. Both still verify the selected binary against that release's
`checksums.txt` and store a versioned `.verified` marker. Checksums are downloaded
and checked at runtime, not invented or embedded during this preparation.

Before an extension tag is published, run the existing `marketplace.py` public
preflight on the exact reviewed/tagged source. It must anonymously download
and hash all six raw assets: macOS ARM64, macOS x86_64, macOS universal, Linux
x86_64 GNU, Linux x86_64 musl and Linux ARM64 musl. Save its actual receipt and
confirm the public LSP manifest binds the public source and crates.io archive.
macOS binaries are unsigned; retain the release's actual qualification scope.

## Preserved failed installation

The first untouched stock-Zed profile installed the adapter at source
`aee04b9e04136b23b0f6d1ecac99eabf525f0abb`, then failed before obtaining a
binary: GitHub's unauthenticated metadata API returned HTTP 403 (rate limit).
That failed profile and its log are retained as failure evidence. The direct
pinned-asset change must be tested in another empty profile; a populated cache,
manual binary override or PATH binary cannot establish that it fixes this failure.
Pure URL, checksum-selection and fallback tests are local policy evidence, not
proof of a successful network installation.

## Fresh stock-Zed profile

Use the installed stock application, with a new directory outside existing user
projects. The local CLI supports `--foreground`, `--new` and `--user-data-dir`.
The official [CLI documentation](https://zed.dev/docs/reference/cli) describes
this override. Current [path implementation](https://github.com/zed-industries/zed/blob/main/crates/paths/src/paths.rs)
places settings at `<profile>/config/settings.json` when the override is active.
macOS logs may still use the global log directory, so capture this instance's
foreground output separately; do not replace or clear the user's logs.

1. Create new profile and fixture directories. Record the source commit, actual
   WASM hash, Zed version and a pre-install file listing. Start with no extension
   cache, no copied user settings and no `binary.path` or `binary.arguments`.
2. Launch `zed --foreground --new --user-data-dir PROFILE FIXTURE_DIRECTORY`.
   Verify settings opened by this instance resolve inside `PROFILE/config`.
   Never alter the user's existing profile to make this check pass.
3. Use **Extensions → Install Dev Extension** to select the exact reviewed
   `catalog/terraphim-lsp` source. This is the documented
   [development installation route](https://zed.dev/docs/extensions/developing-extensions).
   The isolated profile must contain only one Terraphim language-server adapter.
   A dev installation validates the adapter and its default downloader; it is
   not evidence that the Zed catalog has accepted or installed the extension.
4. Open a fresh Markdown fixture. Observe the completed default download and
   inspect the spawned language-server executable path. Require it to be the
   profile's versioned RC6 extension-work binary, not an explicit path or a PATH
   fallback. Compare that executable and its `.verified` marker with the actual
   anonymous RC6 checksum, then run that exact file's `--version`.
5. Restart the language server and verify the same cached executable and marker
   are reused. Retain the instance log and process-path evidence. A candidate
   override or a binary found on PATH cannot satisfy these checks.

## Saved user-visible outputs

Use the bounded native checks in [qualification.md](qualification.md): swaps of
existing alternatives, save/reopen, undo/redo, Trim Done, clean export, repeated
knowledge-graph export and dirty-destination refusal. Clearly mark preauthored
fixture annotations as input. Separately create a new alternative from plain
Markdown with `terraphim.alternative.add_and_apply` in Zed's generic LSP picker,
as described in [the authoring walkthrough](alternative-authoring.md). Supply
the document URI, selection range and text explicitly; there is no automatic
selection inference. Verify the newly generated annotation, save/reopen and
undo/redo before exporting it. The original return-edit command is unchanged.

Inspect the actual saved graph and unchanged source, then run released
terraphim-grep against that graph. Keep baseline and graph-enabled outputs
separate. Store the native extension/source/asset hashes with saved files and
screenshots. These checks do not certify all 41 browser-editor requirements.

## Catalog gate

After the exact-source native run and extension release succeed, prepare the
existing catalog patch through CI. Zed's upstream AI policy requires a human to
write and submit the catalog PR and maintainer replies. Verify the live registry
listing and a second clean registry installation after upstream acceptance.
The Zed application fork remains outside this work.
