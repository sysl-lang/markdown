# markdown

CommonMark, plus what GitHub renders, for [sysl](https://sysl.sh). The module is `sh.sysl.markdown`.

**Status: in progress.** The document tree, its walk, the HTML renderer and the extension interface
are written and tested. The parser reads every block construct -- block quotes, lists, headings,
code blocks, HTML blocks, thematic breaks, paragraphs -- and every inline construct but links:
backslash escapes, entity and numeric character references, code spans, autolinks, raw HTML, line
breaks, and emphasis and strong emphasis. Spec examples that need links are compiled but ignored,
each naming what it waits for. Nothing is tagged.

```hocon
dependencies {
  markdown { git = "github.com/sysl-lang/markdown", version = "0.1.0" }
}
```

```sysl
import sh.sysl.markdown.{parse, to_html}

print(to_html(parse("# Hello\n")))
```

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
- **Extensions are an open trait**, `Extension`, asked at three points: a block starter (with whether
  it may interrupt a paragraph, a continuation check and a close), an inline trigger byte, and a pass
  over the finished tree. The built-in extensions are written against the same trait.
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

### The differential check against cmark

```
tools/differential.sh [file or directory ...]
```

renders a corpus through this package and through `cmark --unsafe` and names every file whose HTML
differs, keeping a diff of each. With no arguments the corpus is the spec's examples, cmark's
regression examples, the README of every repository under `~/dev/sysl-lang` and the pages of
`~/dev/sysl-lang/sysl-census-34/docs/content`; it needs `cmark` on the `PATH` (`brew install
cmark`) and `python3`. `SYSL` and `CMARK` name other binaries.

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

## License

ISC
