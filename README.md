# markdown

CommonMark, plus what GitHub renders, for [sysl](https://sysl.sh). The module is `sh.sysl.markdown`.

**Status: in progress.** The document tree, its walk, the HTML renderer and the extension interface
are written and tested. The parser reads every block construct -- block quotes, lists, headings,
code blocks, HTML blocks, thematic breaks, paragraphs -- while inlines are still text and line
breaks only, so spec examples that need emphasis, code spans, links and the rest are compiled but
ignored, each naming what it waits for. Nothing is tagged.

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
- **The HTML renderer is commonmark.js's, byte for byte**: `&`, `<`, `>` and `"` escaped, a link
  destination percent-encoded as `mdurl.encode` does it (an existing `%XX` kept, `ä` as `%C3%A4`).
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

## Testing

```
sysl test .
```

## License

ISC
