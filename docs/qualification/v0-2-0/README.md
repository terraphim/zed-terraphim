# Stock-Zed source qualification, 14 October 2026

This receipt records the eight functional checks run against catalog source `b75b475adebe42604ac9ba86023b884c7049bc58` in stock Zed 1.23.3. The fresh profile automatically downloaded the public RC7 LSP. The development-install WASM hash is separate from any CI-built release WASM.

The numbered files are actual saved outputs. Outputs 01–04 prove authoring, undo/redo, reopening and swapping. Outputs 05–08 prove repeated synonym export and released-grep retrieval. Outputs 09–13 prove that a new Hazard synonym was pending while an unsaved interior JSON change was refused and preserved; saving the edit permitted the next export. Outputs 14–18 prove Trim persistence, anchor movement, clean export and dirty Markdown destination protection. The preauthored Trim fixture is input, not newly generated authoring output.

The functional checks passed. Native CUA screenshots showed the refusal and preserved buffers, but native Screenshot and Preview capture attempts did not produce a durable image. No downloadable screenshot is claimed. The receipt records this visual-evidence limitation instead of substituting an image or headless test.

This evidence covers a source development installation. A separate receipt must verify the actual downloaded compiled package after release. Official Zed catalog acceptance and installation remain separate. It does not certify all 41 browser-editor requirements or the Zed application fork.
