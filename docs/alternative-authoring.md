# Author a new alternative with Zed's command picker

Status: verified with a candidate RC4 server in stock Zed 1.23.3. The public
RC4 GitHub binary release failed in the musl build lanes. The prospective RC5
release and default-install verification remain pending.

Zed's built-in **lsp command selector: toggle** action can pass JSON arguments
to a language server. The prepared RC4 server advertises
`terraphim.alternative.add_and_apply`, which asks Zed to apply the annotation
and confirms that the document changed. This uses the stock application.

For a Markdown file beginning with `Risk is manageable.`, open the command
palette, run **lsp command selector: toggle**, and select
`terraphim.alternative.add_and_apply`. Press Tab to focus **Arguments** and
enter one JSON object, replacing the URI with your open file's absolute URI:

```json
{"uri":"file:///path/to/brief.md","range":{"start":{"line":0,"character":0},"end":{"line":0,"character":4}},"text":"Concern"}
```

Press Enter, then save the document. The original sentence keeps its wording, while the Markdown annotation records `Concern` as its
alternative. The URI and range are explicit input: the picker does not infer
your selection. LSP line and character positions start at zero; character
offsets use UTF-16. An optional `version` rejects a stale document version.

You can then select the word and use its alternative code action to swap the
wording. Save/reopen preserves the annotation; normal undo and redo apply to
the edit. Run `terraphim.export_knowledge_graph` through the same picker with:

```json
{"uri":"file:///path/to/brief.md"}
```

Save the generated `brief.knowledge-graph.json`. Its `risk` and `concern`
entries share a concept ID; released `terraphim-grep` can consume that graph.
The source document retains its annotation.

The original `terraphim.alternative.add` returns a WorkspaceEdit for clients
that apply it themselves. Zed's generic picker only logs a command's return
value, so use the explicit `add_and_apply` variant here. It requires versioned
edits and client apply support. A rejection or stale document is reported as a
failure. If acknowledgement or the matching document change times out, inspect
the document before retrying: the edit may still arrive. A successful command
returns an acknowledgement rather than a second edit to apply.
