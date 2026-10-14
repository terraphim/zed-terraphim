# Stock-Zed 0.2.1 source qualification, 14 October 2026

All eight required native checks passed against exact catalog source `38f1f948db9fb62851ea469f7c344abb3f141b1f` in stock Zed 1.23.3 on macOS ARM64. The fresh isolated profile automatically downloaded the pinned public RC7 server; no binary override or cache seed was supplied. A native language-server restart reused the same verified cache bytes and modification time. The [receipt](source-qualification.json) identifies the actual source-install WASM, server, inputs and saved output hashes.

## Inputs and actual outputs

The files in [inputs](inputs/) are the unchanged plain Markdown inputs. Neither contains annotations or preauthored synonyms. The numbered files were read from disk after native actions and Save; they are outputs, not seeded fixtures.

- **01–04:** A generic LSP command authored Concern as an alternative to Risk. Native undo/save restored the plain input; redo/save and close/reopen restored the generated annotation byte for byte. A native code action then swapped the wording to Concern and saved it.
- **05–08:** Two graph exports preserved parsed graph data. Risk and Concern share one concept ID. Released terraphim-grep 1.21.20 searched a separate unchanged Risk passage: the Concern query changed from zero passages to one when the actual exported graph was supplied. These are search-only results; no synthesis is claimed.
- **09–13:** Native authoring added Hazard to the document, leaving a real new export pending. An unsaved interior JSON edit changed the graph name to `UNSAVED INTERIOR 0.2.1`. Export was visibly refused, disk bytes remained identical, and a subsequent native Save preserved that exact edit. After saving, export succeeded and included Hazard.
- **14–18:** Trim **Tighten more ~20%**, then **Done**, generated 11 ghosts from plain prose. Save/reopen and an eight-character prefix edit moved all anchors by eight characters; each anchor still matches its saved text. Clean export removed the ghosts and annotation fence. An unsaved clean-export prefix was refused and preserved, then saved as output 18.

Native CUA screenshots in the execution transcript showed the actual extension, commands, Trim preview, refusal messages and preserved dirty buffers. No downloadable screenshot or video is claimed. A second Save followed asynchronous anchor reconciliation before inspecting the final persisted anchors. An additional plain-document thesaurus-settings check was prepared after these eight checks, but the Mac locked before its result could be tested; that extra check is explicitly blocked.

## Reproduce the saved graph search

Install terraphim-grep separately from the [v1.21.20 client release](https://github.com/terraphim/terraphim-clients/releases/tag/v1.21.20). In a disposable directory, copy `inputs/brief.md` to `corpus/decision.md` and output `06-repeated-export.json` to `brief.knowledge-graph.json`, then run:

```sh
terraphim-grep Concern --search-only --haystack all --paths ./corpus --json -n 3
terraphim-grep Concern --search-only --haystack all --paths ./corpus --json -n 3 --thesaurus ./brief.knowledge-graph.json
```

The first command returned zero passages; the second returned the unchanged Risk sentence in `decision.md`. Timings may differ on another run.

This qualification covers a source development installation. The actual CI-built release archive must be downloaded and installed separately before compiled-package installation is qualified. Official Zed catalog acceptance and installation remain separate. This bounded evidence does not certify all 41 browser-editor requirements or the Zed application fork. Historical 0.2.0 receipts remain unchanged.
