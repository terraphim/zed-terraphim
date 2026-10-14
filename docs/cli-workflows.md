# From Zed alternatives to search and agent memory

Use one project brief to connect an authored alternative to search. Then save a
decision explicitly with the separate agent CLI. The examples below were checked
with the released Terraphim clients **1.21.20** on macOS ARM64.

## Install the extension and CLIs

Install the compiled [Terraphim LSP 0.2.0 GitHub package](https://github.com/terraphim/zed-terraphim/releases/tag/v0.2.0)
using the [released-package instructions](released-package-install.md). The
package pins language server 1.22.0-rc.7. Official Zed catalog availability still
requires upstream acceptance and a registry build; the GitHub release is available
now. Stock Zed supplies code actions and the command picker, not the browser
editor's visual panels.

Download the archive for your operating system and architecture from
[Terraphim clients 1.21.20](https://github.com/terraphim/terraphim-clients/releases/tag/v1.21.20),
verify its release checksum, extract it and place `terraphim-grep` and
`terraphim-agent` on your PATH. These are separate CLI installations; the Zed
extension only provisions its language server. Check the installed versions:

```sh
terraphim-grep --version
terraphim-agent --version
```

## Author and export a synonym

Start in a new example directory. Create and open `brief.md` in Zed with this
first line:

```markdown
Risk is manageable.
```

Open the command palette and run **lsp command selector: toggle**. Select
`terraphim.alternative.add_and_apply`, press Tab to focus **Arguments**, and
enter this one object, replacing the URI with your open file's absolute URI:

```json
{"uri":"file:///absolute/path/to/brief.md","range":{"start":{"line":0,"character":0},"end":{"line":0,"character":4}},"text":"Concern"}
```

Press Enter and save. The sentence remains unchanged; its saved annotation now
contains the alternative. Select `Risk` and open its code actions to swap to
`Concern`, then save. The [authoring guide](alternative-authoring.md) explains
ranges, undo/redo and stale-document handling.

In the same LSP picker, run `terraphim.export_knowledge_graph` with:

```json
{"uri":"file:///absolute/path/to/brief.md"}
```

Save the generated **`brief.knowledge-graph.json`** beside the brief. Inspect its
`risk` and `concern` entries: they share a concept ID. Save any pending edits in
an existing export destination before exporting again; dirty destinations are
protected. To use this graph for suggestions in other Markdown files, set
`lsp.terraphim-lsp.initialization_options.thesaurus` to its absolute path in
`.zed/settings.json`, as shown in the [package README](../catalog/terraphim-lsp/README.md#choose-your-knowledge-graph).
The initial server graph is empty; authoring a new alternative works without one.

The same relationship can be authored in a Markdown concept note, for example
`Risk.md`, using Logseq-compatible PKM property syntax:

```markdown
# Risk
synonyms:: concern

A possible event that could delay the project.
```

Keep `synonyms::` in the concept note. It is authored source, not a search-result
field. The CLI command below consumes the **exported JSON graph**, not the raw
Markdown note; adding a note alone does not compile or reload a graph.

## Search by the new synonym

From the directory containing `brief.knowledge-graph.json`, prepare a small
corpus containing only the canonical word. Use an empty example directory so
this command does not overwrite an existing `decision.md`:

```sh
mkdir -p corpus
printf '%s\n' 'The release decision is to keep a second supplier because Risk could delay launch.' > corpus/decision.md
terraphim-grep Concern --search-only --haystack all --paths ./corpus \
  --thesaurus ./brief.knowledge-graph.json --json -n 3
```

In a fresh example directory, the JSON response has one chunk from `decision.md`
containing `Risk`, despite the query being `Concern`. Its `answer` is null:
`--search-only` returns retrieved passages without synthesis. This demonstrates
the authored relationship crossing from editor output into search. It does not
require a model provider.

## Save and read a decision with terraphim-agent

Memory capture is an explicit second workflow. It writes the supplied content to
the agent's configured local memory store; the current directory alone does not
isolate that store, and this command does not import the editor graph.

```sh
terraphim-agent --format json memory capture \
  --content 'Risk requires a Decision: approve a second supplier as the mitigation.' \
  --provenance-tag 'public-project-brief'
```

Set `MEMORY_ID` to the returned memory ID, replacing the placeholder below:

```sh
MEMORY_ID='paste-the-returned-memory-id'
terraphim-agent memory show "$MEMORY_ID" --json
```

The saved record should contain the exact supplied decision and provenance tag.
The tag describes the source; it is not the memory content. Capture and show do
not require a model provider.

Learn more: [online synonym-to-search walkthrough](https://terraphim.ai/how-tos/synonym-search/),
[agent memory walkthrough](https://terraphim.ai/posts/cold-start-tax-agentic-memory/),
[agent hooks walkthrough](https://terraphim.ai/posts/native-hook-support/),
and [Terraphim clients source](https://github.com/terraphim/terraphim-clients).
