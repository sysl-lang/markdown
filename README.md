# markdown

CommonMark, plus what GitHub renders, for [sysl](https://sysl.sh). The module is `sh.sysl.markdown`.

**Status: CommonMark and GitHub's core extensions complete, not yet tagged.** Every one of the
CommonMark spec's 652 examples renders exactly, with the GitHub extensions off and on; every
extension example of GitHub's spec renders exactly; hostile inputs are read in linear time; and
differential checks against cmark and cmark-gfm agree on their whole corpora but for the cases
listed below. Footnotes, alerts, heading ids, emoji, math and mermaid are still to come.

```hocon
dependencies {
  markdown { git = "github.com/sysl-lang/markdown", version = "0.1.0" }
}
```

```sysl
import sh.sysl.markdown.{parse, to_html}

print(to_html(parse("# Hello\n")))      // <h1>Hello</h1>
```

## The API

```sysl
parse(src: string) -> Doc                                   // CommonMark: parse_with(src, commonmark())
parse_with(src: string, opts: ParseOptions) -> Doc
parse_with_regions(src: string, opts: ParseOptions, regions: Buf[Region]) -> Result[Doc, RegionError]

to_html(d: Doc) -> string                                   // as the spec renders: to_html_with(d, commonmark_html())
to_html_with(d: Doc, opts: HtmlOptions) -> string
render_html(d: Doc, opts: HtmlOptions, out: *Writer)

plain_text(d: Doc, n: NodeId) -> string                     // the text under a node, for slugs, alt text, search

struct ParseOptions                                         // commonmark(): no extensions
    exts: Registry                                          // gfm(): tables, strikethrough, autolinks, task lists

struct HtmlOptions                                          // commonmark_html(): true, "\n", None, false
    raw_html: bool                                          // gfm_html(): true, "\n", None, true
    softbreak: string
    highlight: Option[&Fn(string, string) -> Option[string]]   // (info, code) -> the block's markup
    tagfilter: bool                                         // GitHub's filter on raw HTML

struct Region                                               // a run of program lines, for weave
    span: Span
    info: string
    literal: string
```

- **A parse and a rendering are told separately**, so one parse can be rendered several ways; the
  link reference definitions live on the `Doc`.
- **`raw_html`**: `true` passes raw HTML through as the spec renders it (the CommonMark preset);
  `false` writes `<!-- raw HTML omitted -->` in place of each HTML block and each piece of inline
  HTML, as cmark's "safe" mode does. It governs raw HTML only -- a `javascript:` link is written
  either way.
- **`highlight`** is asked about every code block with its whole info string and its text; what it
  answers replaces the whole `<pre><code>…</code></pre>`, and `None` falls back to that.
- **`parse_with_regions`** reads a woven file: each region -- whole lines, in source order, not
  overlapping -- closes every open block and becomes a code block of the document whose span points
  into the real file. The rest is Markdown, and it is one document with one set of link references.
- **`plain_text`** is the text a reader sees: entities decoded, code spans' content, link and image
  text but not their destinations, no raw HTML, a soft break as a space and a hard break as a
  newline, one newline between blocks.

This is checked line for line by `tests_api.sysl`'s `readme_example`:

```sysl
import sh.sysl.markdown.*

val d = parse("# Hello, *world*\n\nSee <b>this</b>.\n")

print(to_html(d))                                       // <h1>Hello, <em>world</em></h1> <p>See <b>this</b>.</p>
print(to_html_with(d, HtmlOptions(false, "\n", None, false)))  // ... <p>See <!-- raw HTML omitted -->this<!-- raw HTML omitted -->.</p>
print(plain_text(d, d.root()))                          // Hello, world / See this.

val code: &Fn(string, string) -> Option[string] = (info, text) ->
    if info == "sysl" then Some("<pre class=\"sysl\">" + escape_html(text) + "</pre>") else None

val opts = HtmlOptions(true, "\n", Some(code), false)

print(to_html_with(parse("```sysl\na < b\n```\n"), opts))   // <pre class="sysl">a &lt; b</pre>
```

## GitHub Flavored Markdown

```sysl
val d = parse_with("| a | b |\n|---|--:|\n| ~~c~~ | www.d.com |\n", gfm())

print(to_html_with(d, gfm_html()))
```

`gfm()` turns on the six extensions GitHub renders with, and `gfm_html()` its tag filter. Each
extension is an ordinary `Extension`, so a parse wanting some of them builds its own `Registry`:
`footnotes()` (first, as cmark-gfm settles footnotes before the others look at the tree),
`tables()`, `strikethrough()`, `autolinks()`, `task_lists()`, `alerts()`. **Every rule but the
alerts' is cmark-gfm's** (0.29.0.gfm.13, which GitHub runs), down to the corners its spec does not
write down:

- **Tables** -- a delimiter row under a paragraph whose last line has as many cells; `\|` is a pipe
  in a cell, code spans included; a short row is filled out and a long one cut; any line that is not
  blank continues the table unless a block starts on it; a paragraph that met a delimiter row of the
  wrong width never becomes a table; and a table stops taking rows once it has filled out 524,288
  cells, so a wide header over many one-cell rows stays linear. Cells carry `align="…"`.
- **Strikethrough** -- `~a~` or `~~a~~`, both runs the same length; three or more `~` are text.
- **Task list items** -- `[ ]`, `[x]` or `[X]` after a list marker that begins the line, written as a
  disabled checkbox (`Item(Some(checked))` in the tree).
- **Extended autolinks** -- `http://`, `https://`, `ftp://`, `www.` and email addresses (with
  `mailto:` and `xmpp:` forms), without trailing punctuation or an unmatched `)`.
- **The tag filter** -- `HtmlOptions.tagfilter` writes the `<` of `title`, `textarea`, `style`,
  `xmp`, `iframe`, `noembed`, `noframes`, `script` and `plaintext` as `&lt;`.
- **Footnotes** -- `[^label]` refers to a definition `[^label]: text`, which holds blocks: the rest of
  its line, then lines indented four columns, empty lines and lazy lines. Labels match as link
  labels do, the first of two definitions wins, footnotes are numbered by first reference (those
  inside definitions counting where they stand), an unreferenced definition is dropped and a
  reference to nothing is the text `[^label]`. The definitions are written at the end in
  `<section class="footnotes" data-footnotes><ol>`, each `<li id="fn-label">` ending in `↩`
  back-references, the second and later references to a footnote taking ids `fnref-label-2`…
  The one place this departs from cmark-gfm is a reference with a line break inside it, whose label
  cmark-gfm measures by column and loses (`tests_gfm_deviations.sysl`).
- **Alerts** -- a block quote directly in the document whose first line is `[!NOTE]`, `[!TIP]`,
  `[!IMPORTANT]`, `[!WARNING]` or `[!CAUTION]` (any case, nothing else on the line) and which holds
  something more. cmark-gfm does not read these -- GitHub adds them afterwards -- so the rules are
  what GitHub's renderer was observed to do (its `/markdown` API in `gfm` mode, 2026-10-08): a marker
  inside a list item or a nested quote is text, `\[!NOTE]` is still a marker and `*[!NOTE]*` is not,
  and a quote holding only the marker stays a quote. The HTML is GitHub's structure without the
  octicon `<svg>` it puts before the title's word, and with a newline between blocks as everywhere
  else:

  ```html
  <div class="markdown-alert markdown-alert-note">
  <p class="markdown-alert-title">Note</p>
  <p>body</p>
  </div>
  ```

## Writing an extension

An extension is an `impl Extension`; every method but `name` has a default that declines, so it
writes only the hooks it uses. The built-in extensions are written against exactly this.

```sysl
trait Extension
    name(self) -> string
    block_start(self, line: Line) -> BlockStart = Declined
    interrupts_paragraph(self) -> bool = false
    block_continue(self, line: Line, kind: Kind, state: *u64) -> BlockContinue = Ends
    block_close(self, c: Closing, state: u64) -> Kind = c.kind
    triggers(self) -> string = ""
    inline_match(self, s: Subject) -> InlineMatch = NoMatch
    delimiter_node(self, ch: u8, opener: usize, closer: usize) -> Option[Kind] = None
    bracket(self, s: Subject, from: usize) -> Option[Kind] = None
    post_pass(self, d: Doc) = ()
    render(self, w: *HtmlWriter, d: Doc, n: NodeId, ev: Event) = ()

enum BlockStart
    Declined
    Mark(word: u64)                                             // decline, and keep a word with the paragraph
    Leaf(kind: Kind, consumed: usize, state: u64)               // lines taken verbatim
    Container(kind: Kind, consumed: usize, state: u64)          // holds blocks
    Lines(kind: Kind, consumed: usize, state: u64, from_para: usize)   // lines taken as a paragraph's
    Retag(container: Kind, consumed: usize)                     // re-mark the block the line reached

struct ExtNode                                                  // Kind.Ext(node: ExtNode)
    ext: string                                                 // the extension that made it, and renders it
    tag: u32
    data: string
    holds: bool                                                 // has children
```

- **A node of the extension's own is `Ext(ExtNode(...))`**, so an extension outside this package adds
  kinds of node without touching `Kind`. The document keeps the registry it was read with, and the
  HTML renderer hands each `Ext` node to the `render` of the extension `ext` names -- on entering it,
  and on exiting it where it holds children -- with the `HtmlWriter` the page goes to: `lit`, `tag`
  (nothing inside an image's alt text), `esc`, `href`, `cr` and `options()`.
- **A block hook sees a `Line`** -- the text, where the containers' prefixes stop, the block the line
  has reached (`within`), the open paragraph's text (`para`) and the word the extension kept with it
  (`para_word`). `Lines` is how a block takes a paragraph's last lines as its own, as a table's
  header does; `Retag` is how a task list marks its list item.
- **A closing block is shown a `Closing`**: its text, and `child(parent, kind, from, to)` and
  `inlines(node, pieces)`, which give it children read from that text -- each mapped back to the
  source for its span, and `pieces` leaving out bytes the block's own syntax owns, as a cell's `\|`.
- **An inline hook sees a `Subject`** -- the leaf's text, the trigger's offset, and whether a link's
  brackets are open -- and answers a node (a container node is given the bytes it read as its `Text`)
  or a run of delimiters, paired by the rule of three as emphasis is, then by `delimiter_node`.
- **`bracket` is asked about a `]` that closed an active `[` or `![` without making a link** -- a
  `Subject` at the `]` and where the bracketed text begins -- and `Some(kind)` replaces the brackets
  and everything between them with one node, as a footnote reference does.
- **`block_continue` may answer `Indented(columns)`** where the block takes indentation by column, a
  tab counted to its stop, as a footnote definition takes its four.
- **`post_pass` sees the finished `Doc`** and rewrites it with `set_kind`, `append_child`,
  `insert_after`, `append_node` and `unlink`, as the email autolinks, the footnotes and the alerts
  do.

## What it is

- **The syntax is CommonMark 0.31.2**, checked against the spec's 652 examples, comparing HTML
  exactly with no normalisation: the spec's HTML is the reference renderer's own output.
- **Plus what GitHub renders**, as extensions: tables, strikethrough, task lists, extended autolinks,
  footnotes, alerts (`> [!NOTE]`), heading ids slugged as GitHub slugs them, and emoji shortcodes.
- **Plus math and mermaid, as GitHub does them**: `$…$`, `$$…$$` and ```` ```math ```` fences are
  written out as TeX for a client-side renderer; ```` ```mermaid ```` fences are handed on the way
  GitHub hands them to mermaid.js.
- **Raw HTML is passed through as the spec renders it.** GitHub's tag filter is an option, off in
  the CommonMark preset.
- **Out unless asked for**: Pandoc attributes, definition lists, smart punctuation.

## How it is built

- **One arena of nodes, linked by index.** Blocks and inlines alike live in one `Buf[Node]` on the
  `Doc`, each with its parent, first and last child, and siblings as indices, and a byte `Span` into
  the source. A rewrite over every node is a flat loop with `set_kind`; moving a node is a relink.
- **Walking and rendering do not recurse**, so input nested a hundred thousand deep renders.
- **The HTML renderer writes what the reference renderers write, byte for byte**: `&`, `<`, `>` and
  `"` escaped, a link destination percent-encoded as `mdurl.encode` does it (an existing `%XX` kept,
  `ä` as `%C3%A4`), and a code block's class from the info string's first word as cmark cuts it, at
  ASCII whitespace, with no second `language-` before one that has it.
- **Linear on hostile input.** cmark's pathological inputs are read in time proportional to their
  size, and references expand to at most the document's size (or 100,000 bytes, whichever is more),
  as cmark caps them, so a long definition used many times cannot make the output explode.
- **Extensions are an open trait**, `Extension`, asked at three points -- a block starter (with whether
  it may interrupt a paragraph, a continuation check and a close), an inline trigger byte, and a pass
  over the finished tree -- and asked to render the nodes it made. The built-in extensions are
  written against the same trait; see *Writing an extension*.
- **Link reference definitions live on the `Doc`**, so one parse can be rendered several ways.

## The spec

`spec/spec.json` is CommonMark 0.31.2's, unmodified, as published at
<https://spec.commonmark.org/0.31.2/spec.json>:

```
sha256  d431b29d97b6f73e69d547109cf5081578fac931e72afe95639ebe766c1b2a20
```

`tools/gen_spec_tests.py` writes it out as `sh/sysl/markdown/tests_spec_*.sysl`, one file per spec
section and one `@test` per example. A section the parser does not read yet is generated with its
examples ignored; listing it in the script's `ENABLED` and rerunning makes them run. The generated
files are committed.

`spec/gfm-spec.txt` is GitHub Flavored Markdown's spec, unmodified, as `test/spec.txt` of
[github/cmark-gfm](https://github.com/github/cmark-gfm) at the tag **0.29.0.gfm.13** (commit
`587a12bb54d95ac37241377e6ddc93ea0e45439b`):

```
sha256  7d8e5814befec287ac116786d81ff14e0adc9b13295b4494649e995408fd871c
```

The same script writes its 24 extension examples -- 8 tables, 2 strikethrough, 2 task lists, 11
autolinks, 1 tag filter -- as `tests_gfm_<extension>.sysl`, read with `gfm()` and `gfm_html()` and
compared exactly. The two task-list examples' HTML is written normalised in that spec (its runner
normalises before comparing), so their tests assert the HTML cmark-gfm writes. Its CommonMark
examples are 0.29's and are not taken; instead `tests_gfm_commonmark.sysl` reads all 652 of
CommonMark 0.31.2's with every extension on. Eleven render differently, as cmark-gfm's own runner
lists such examples -- six HTML blocks the tag filter rewrites and five autolink examples whose text
an extended autolink now links -- and each asserts what cmark-gfm renders with the same extensions.
None of the 652 changes with footnotes and alerts on.

`spec/cmark-gfm-extensions.txt` is cmark-gfm's own extension tests, unmodified, as
`test/extensions.txt` at the same tag:

```
sha256  a2a45e98be9fca95f564f927265a0f63beea6cae5369d1cf4bde44caa51b2a3a
```

GitHub's spec has no footnote examples; this file's three are written out as
`tests_gfm_footnotes.sysl`, compared exactly.

`spec/entities.json` is WHATWG's list of HTML5 named character references, unmodified, as published
at <https://html.spec.whatwg.org/entities.json>:

```
sha256  d741d877ac77c4194c4ad526b5b4a19aef8dfe411ab840a466891cdbb9f362e6
```

`tools/gen_entities.py` writes the 2,125 names that end in `;` -- the only ones CommonMark
recognises -- into `sh/sysl/markdown/entity_table.sysl` as one sorted string, which a lookup
bisects. One string literal adds about 0.01 s to a cold build, where a table of pairs would add
seconds. The generated file is committed.

## Testing

```
sysl test .
```

`sh/sysl/markdown/tests_pathological.sysl` carries every input of cmark's
`test/pathological_tests.py` at the tag **0.31.2**
(<https://github.com/commonmark/cmark/blob/0.31.2/test/pathological_tests.py>), each at cmark's size
and a tenth of it, with the HTML checked exactly at both and the time checked against the input's
growth: a ratio under 20 where linear reading gives about 10 and quadratic about 100.
`tests_gfm_scaling.sysl` does the same for the extensions' own hostile inputs: tables of 50,000
columns and of 50,000 rows, a cell of escaped pipes, a paragraph of mismatched delimiter rows, runs of
`~`, and text an autolink almost starts in at every byte. `tests_footnote_scaling.sysl` does it for
footnotes and alerts: 20,000 references to one footnote, 20,000 footnotes, 20,000 unreferenced
definitions, 20,000 definitions nested one inside the next, undefined references and unclosed `[^`,
20,000 alerts and a 20,000-byte almost-marker.

`tests_footnotes.sysl` holds 36 footnote cases, each asserting the HTML cmark-gfm writes for it, and
`tests_alerts.sysl` 34 alert cases asserting the HTML GitHub writes (less the icon).

`tests_gfm_edges.sysl` holds 187 corner cases for the extensions, each asserting the HTML cmark-gfm
writes for it -- the inputs `tools/differential.sh --gfm` was run over while they were written.

### The differential check against cmark

```
tools/differential.sh [--gfm] [file or directory ...]
```

renders a corpus through this package and through `cmark --unsafe` and names every file whose HTML
differs, keeping a diff of each. With no arguments the corpus is the spec's examples, cmark's
regression examples, the README of every repository under `~/dev/sysl-lang` and the pages of
`~/dev/sysl-lang/sysl-census-34/docs/content`; it needs `cmark` on the `PATH` (`brew install
cmark`) and `python3`. `SYSL` and `CMARK` name other binaries.

**`--gfm`** compares GitHub Flavored Markdown: `gfm()` less its alerts (which cmark-gfm does not
read) and `gfm_html()` here against `cmark-gfm --unsafe -e footnotes -e table -e strikethrough -e
autolink -e tasklist -e tagfilter` (`brew install cmark-gfm`; `CMARK_GFM` names another binary),
with GitHub's spec examples and cmark-gfm's extension tests added to the corpus. cmark-gfm reads
CommonMark 0.29, so a file on which it and cmark 0.31.2 disagree with every extension off is marked
as such: there the difference is the CommonMark version's, and this package renders as cmark 0.31.2
does. Over the whole corpus -- 1,590 files -- every difference is one of those.

`spec/cmark-regression.txt` is cmark 0.31.2's `test/regression.txt`, unmodified:

```
sha256  aaa16d0e50464dfd03628acb4eaa4db462efb3ae523d7419ba15787add74d3ed
```

**Where cmark and this package disagree and the spec decides for this package**, each is pinned in
`tests_cmark_deviations.sysl`:

| input | cmark 0.31.2 | the spec |
|---|---|---|
| a comment whose text ends in `-`: `<!--<!---->` | not a comment | §6.6, an HTML comment is `<!--`, text not including `-->`, and `-->` (example 625) |
| a CDATA section whose text ends in `]`: `<![CDATA[x]]]>` | not raw HTML | §6.6, a CDATA section (example 629) |
| `<![CDATA[…]]>` or `<!X…>` after an unclosed `<!--` | text | §6.6: each kind of raw HTML is matched on its own |
| leading whitespace of a lazy line, or of one indented four or more | kept, showing in code spans, after a hard break, and stopping a definition | §4.8, examples 222 and 223: leading spaces or tabs are skipped |
| `[a]: /u` then `"t"x` on the next line | `[a]` keeps the title `t` | §4.7, example 210: the title is not part of the definition |
| `[x [a](b) [c] ](d)` | a link inside a link | §6.3, examples 518 and 519: links never contain links |
| `<script/>` alone on a line | an HTML block | §4.6, start condition 7 excludes open tags named `pre`, `script`, `style` and `textarea` |
| a tab before a line ending | removed | §6.8: *spaces* at the end of a line are removed |

**Where cmark-gfm and this package disagree with the extensions on**, each is pinned in
`tests_gfm_deviations.sysl`:

| input | cmark-gfm 0.29.0.gfm.13 | this package |
|---|---|---|
| a link reference definition in the lines above a table's header | left as paragraph text, and never defined | a definition (CommonMark §4.7) |
| `\|` in the lines above a table's header | its backslash removed, inside a code span too | CommonMark's escape, which a code span does not read |
| a `'` in a link's destination | written `&#x27;` (cmark does the same) | written `'`, as commonmark.js writes it |

## License

ISC
