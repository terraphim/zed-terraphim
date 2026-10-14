# RC7 default-install qualification

The dependency is the public [Terraphim LSP RC7 release](https://github.com/terraphim/terraphim-ai/releases/tag/terraphim_lsp-v1.22.0-rc.7),
source `4fb62d337c306a9105c5e872f3400f3052a2caef`. CI run
[38593509964](https://github.com/terraphim/terraphim-ai/actions/runs/38593509964)
published it on 14 October 2026. All six raw binary assets were independently
downloaded anonymously and verified against that release's `checksums.txt`.

| Asset | SHA-256 |
| --- | --- |
| `terraphim-lsp-aarch64-apple-darwin` | `faf89155be9cdada9e06d87d4c54279405a13409ee74917469c0bc6756462aae` |
| `terraphim-lsp-universal-apple-darwin` | `ed60697248dfbef1d3b731e5f758fd7f02c00c74b3da8581df11dd78fa2e32cd` |
| `terraphim-lsp-x86_64-apple-darwin` | `9532a4e019631d1ec97b3df956fd18304a92660e99a497bf14e6101f618ec0cb` |
| `terraphim-lsp-aarch64-unknown-linux-musl` | `0ded8432af3863296b123f18e514e20989bdf3b120360d6454552dc39d4e63bf` |
| `terraphim-lsp-x86_64-unknown-linux-gnu` | `a535ff81b9de3658b7803b59dc03c6f048a5f913339b0f2746c21001ae85a062` |
| `terraphim-lsp-x86_64-unknown-linux-musl` | `7e646d7ed10fec3a24be9c42248ae2c1974327be7329eb0157eec57336def0c2` |

The adapter checks the actual downloaded checksum file at runtime. This table is
release evidence, not a substitute for that check. The catalog uses fixed public
URLs, no GitHub metadata API, no Gitea request and no PATH fallback. Explicit
`binary.path` remains supported but must be absent during default-install tests.
The legacy adapter retains its source ordering and independent MCP pin.

## Fresh source installation

Freeze and commit the reviewed catalog source before running these checks. Use
an untouched stock-Zed profile and disposable project, with no copied extension
cache, executable, user settings or binary override. Record input files as inputs.
Use `zed --foreground --new --user-data-dir PROFILE PROJECT`; verify that this
instance's settings resolve to `PROFILE/config/settings.json`.

Install the reviewed `catalog/terraphim-lsp` directory through **Extensions →
Install Dev Extension**. Record the exact source SHA and dev-built `extension.wasm`
hash. Open the plain Markdown fixture, then identify the actual spawned server
inside the profile's versioned RC7 work directory. Compare the executable and
`.verified` marker with the public release, run that file's `--version`, and
restart the server to prove verified-cache reuse. No manual executable copy or
PATH result satisfies default provisioning.

## Saved outputs and dirty JSON regression

1. Start with plain `Risk is manageable.` and create `Concern` through
   `terraphim.alternative.add_and_apply`, as in [the authoring walkthrough](alternative-authoring.md).
   Save the resulting annotation. Native undo/save must restore the original;
   redo/save must restore the generated annotation. Close/reopen and swap using
   a code action, then inspect the actual saved text.
2. Export the graph twice and save both actual outputs. Require `risk` and
   `concern` to share a concept ID, equal graph content on repeat export and an
   unchanged source document.
3. Reproduce the RC6 failure with an **interior** unsaved edit to the existing
   graph's `name` string, not an appended suffix. Capture the dirty tab and text
   before export, plus the on-disk hash. Export again from the paired Markdown.
   Require visible refusal, the unsaved interior text still present, and the
   on-disk hash unchanged. Persist a window-only screenshot of the result.
   Save the preserved edit afterward and verify its actual bytes. Repeat for a
   JSONC destination when exercising the JSONC protocol path; the native default
   filename is JSON. An append surviving outside the replaced range is not proof.
4. Verify JSON/JSONC receive no Markdown alternatives, diagnostics or Lab marks.
   Their attachment exists only for passive buffer and version tracking.
5. Run Trim Done on the explicitly preauthored fixture. Save its actual ghost
   annotations, insert a prefix and verify all retained anchor offsets shift by
   the prefix length. Export clean Markdown and verify the saved text. Make an
   unsaved edit in that destination, require refusal and preserve its buffer/disk.
6. Run released `terraphim-grep` against a clean brief first without and then with
   the actual exported graph. Save its version/hash, commands and returned JSON.
   The newly authored synonym must retrieve the canonical passage only when the
   graph is supplied. Keep seeded fixtures separate from these generated outputs.

Save a private detailed receipt and the sanitized public source receipt described
in [qualification.md](qualification.md). A native failure blocks publication;
headless protocol success cannot substitute for this run. Historical RC6 failure
receipts and profiles remain unchanged. These bounded checks do not certify all
41 browser-editor requirements.

## Compiled package and catalog

After exact-source acceptance, a normal merge may preserve that tested PR head;
tag the exact tested source as `v0.2.0`. The evidence can be published in a later
docs-only commit while retaining the tested source identity. The protected release
workflow must qualify and publish its exact catalog archive.

Then use another empty stock-Zed profile to install the **downloaded four-file
archive**, following [released-package installation](released-package-install.md).
Require the loaded WASM hash to equal the released archive's module, with no Cargo
source or Rust rebuild. Save a separate native receipt for these bytes. Catalog
submission remains a human-authored upstream contribution, followed by actual
registry listing and registry-install verification. The Zed application fork is
outside this work.
