#!/usr/bin/env python3
"""Write the CommonMark and GitHub spec examples as sysl tests.

    python3 tools/gen_spec_tests.py

Reads spec/spec.json (CommonMark 0.31.2) and writes sh/sysl/markdown/tests_spec_<section>.sysl, each
example a `@test` asserting that parsing its Markdown and rendering the tree gives the spec's HTML
exactly -- no normalisation, since the spec's HTML is the reference renderer's own output.

A section not named in ENABLED is still generated, with every example marked `ignore`: the
assertion is the correct one and compiles, and it runs once the section is listed. The generated
files are committed; rerun this after changing ENABLED or the spec.

It also writes the GitHub Flavored Markdown files, both read with the GFM presets (`gfm()` and
`gfm_html()`):

- tests_gfm_<section>.sysl -- every extension example of spec/gfm-spec.txt (GitHub's spec, the
  examples marked `table`, `strikethrough`, `autolink`, `disabled` (the task lists) and
  `tagfilter`), compared exactly. The CommonMark examples GitHub's spec also carries are its
  CommonMark 0.29 copy, so they are not taken from there.
- tests_gfm_commonmark.sysl -- the 652 CommonMark 0.31.2 examples again, with every GitHub
  extension on: each must still render as the spec says, except the ones GFM_CHANGES lists, which an
  extension legitimately changes, as cmark-gfm's own test runner lists them. Those assert the HTML
  written there, which is what cmark-gfm renders with the same extensions on.
"""

import json
import os
import re
import sys

# The spec sections the parser reads, by their name in spec.json. Their examples run.
ENABLED = {
    "Thematic breaks",
    "ATX headings",
    "Paragraphs",
    "Blank lines",
    "Precedence",
    "Soft line breaks",
    "Hard line breaks",
    "Textual content",
    "Setext headings",
    "Indented code blocks",
    "Fenced code blocks",
    "HTML blocks",
    "Tabs",
    "Block quotes",
    "List items",
    "Lists",
    "Backslash escapes",
    "Entity and numeric character references",
    "Code spans",
    "Autolinks",
    "Raw HTML",
    "Inlines",
    "Emphasis and strong emphasis",
    "Links",
    "Images",
    "Link reference definitions",
}

# Examples in an ENABLED section that need a construct the parser does not read yet, by number, with
# the reason written into their `ignore:`. Every CommonMark construct is read, so it is empty; an
# extension's own corpus uses it the same way.
IGNORED = {}

# CommonMark 0.31.2 examples a GitHub extension changes, by number: why, and the HTML they render as
# with every extension on -- cmark-gfm 0.29.0.gfm.13's, with the same extensions, which with them off
# renders each exactly as the spec does.
TAGFILTER = "the tag filter writes the '<' of a filtered tag as '&lt;'"
AUTOLINK = "an extended autolink"
GFM_CHANGES = {
    170: (TAGFILTER, '&lt;script type="text/javascript">\n// JavaScript example\n\ndocument.getElementById("demo").innerHTML = "Hello JavaScript!";\n&lt;/script>\n<p>okay</p>\n'),
    171: (TAGFILTER, "&lt;textarea>\n\n*foo*\n\n_bar_\n\n&lt;/textarea>\n"),
    172: (TAGFILTER, '&lt;style\n  type="text/css">\nh1 {color:red;}\n\np {color:blue;}\n&lt;/style>\n<p>okay</p>\n'),
    173: (TAGFILTER, '&lt;style\n  type="text/css">\n\nfoo\n'),
    176: (TAGFILTER, "&lt;style>p{color:red;}&lt;/style>\n<p><em>foo</em></p>\n"),
    178: (TAGFILTER, "&lt;script>\nfoo\n&lt;/script>1. *bar*\n"),
    602: (AUTOLINK, '<p>&lt;<a href="https://foo.bar/baz">https://foo.bar/baz</a> bim&gt;</p>\n'),
    606: (AUTOLINK, '<p>&lt;<a href="mailto:foo+@bar.example.com">foo+@bar.example.com</a>&gt;</p>\n'),
    608: (AUTOLINK, '<p>&lt; <a href="https://foo.bar">https://foo.bar</a> &gt;</p>\n'),
    611: (AUTOLINK, '<p><a href="https://example.com">https://example.com</a></p>\n'),
    612: (AUTOLINK, '<p><a href="mailto:foo@bar.example.com">foo@bar.example.com</a></p>\n'),
}

# GitHub's spec writes these examples' HTML normalised -- attributes sorted, no closing slash -- as
# its runner compares after normalising. Their exact HTML, by number, is cmark-gfm's own output.
GFM_NORMALISED = {
    279: '<ul>\n<li><input type="checkbox" disabled="" /> foo</li>\n<li><input type="checkbox" checked="" disabled="" /> bar</li>\n</ul>\n',
    280: '<ul>\n<li><input type="checkbox" checked="" disabled="" /> foo\n<ul>\n<li><input type="checkbox" disabled="" /> bar</li>\n<li><input type="checkbox" checked="" disabled="" /> baz</li>\n</ul>\n</li>\n<li><input type="checkbox" disabled="" /> bim</li>\n</ul>\n',
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "spec", "spec.json")
GFM_SPEC = os.path.join(ROOT, "spec", "gfm-spec.txt")
EXT_SPEC = os.path.join(ROOT, "spec", "cmark-gfm-extensions.txt")
OUT = os.path.join(ROOT, "sh", "sysl", "markdown")
PREFIX = "tests_spec_"
GFM_PREFIX = "tests_gfm_"
FENCE = "`" * 32

# The label GitHub's spec gives each extension's examples, and the section its tests are filed under.
GFM_LABELS = {
    "table": "tables",
    "strikethrough": "strikethrough",
    "autolink": "autolinks",
    "disabled": "task_lists",
    "tagfilter": "tagfilter",
}


def lit(s):
    """A sysl string literal holding exactly s."""
    out = []
    for c in s:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif ord(c) < 32 or ord(c) > 126:
            out.append("\\u{%x}" % ord(c))
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def slug(section):
    return re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_")


def gfm_examples(spec=None):
    """Every example of GitHub's spec (or of `spec`, written the same way) as (number, label,
    markdown, html), numbered as its own renderer numbers them -- every example in order, from 1 --
    with a tab where it writes a →."""
    examples = []
    lines = open(spec or GFM_SPEC, encoding="utf-8").read().split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith(FENCE) and line[len(FENCE):].strip().startswith("example"):
            label = line[len(FENCE):].strip()[len("example"):].strip()
            i += 1
            md = []

            while lines[i] != ".":
                md.append(lines[i] + "\n")
                i += 1

            i += 1
            html = []

            while not lines[i].startswith(FENCE):
                html.append(lines[i] + "\n")
                i += 1

            examples.append((len(examples) + 1, label, "".join(md).replace("→", "\t"), "".join(html).replace("→", "\t")))

        i += 1

    return examples


def write(name, body):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n")


def generated(name):
    """Whether the file `name` in OUT was written by this script, which a hand-written one is not."""
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return "Written by tools/gen_spec_tests.py" in f.read(1000)


def footnotes():
    """cmark-gfm's own footnote examples (spec/cmark-gfm-extensions.txt, its test/extensions.txt),
    read with gfm() and rendered with gfm_html(), as cmark-gfm's runner reads them with every
    extension and its footnotes option on."""
    exs = [(n, md, html) for n, _, md, html in gfm_examples(EXT_SPEC) if "[^" in md]
    body = [
        "module sh.sysl.markdown",
        "@tests",
        "",
        "// cmark-gfm's own footnote examples (spec/cmark-gfm-extensions.txt), read with gfm() and",
        "// rendered with gfm_html(), compared exactly. Written by tools/gen_spec_tests.py; edit that, not this.",
    ]
    for n, md, html in exs:
        body += [
            "",
            '@test("cmark-gfm extensions example %d")' % n,
            "gfm_extensions_example_%d()" % n,
            "    assert_eq(to_html_with(parse_with(%s, gfm()), gfm_html()), %s)" % (lit(md), lit(html)),
        ]
    write(GFM_PREFIX + "footnotes.sysl", body)
    print("%d cmark-gfm footnote examples" % len(exs))


def gfm(examples):
    """The GitHub files: the extension examples, and the CommonMark ones with every extension on."""
    for name in os.listdir(OUT):
        if name.startswith(GFM_PREFIX) and name.endswith(".sysl") and generated(name):
            os.remove(os.path.join(OUT, name))

    files = {}

    for n, label, md, html in gfm_examples():
        if label in GFM_LABELS:
            files.setdefault(GFM_LABELS[label], []).append((n, md, html))

    stray = [n for n in GFM_NORMALISED if not any(n == e[0] for v in files.values() for e in v)]
    if stray:
        sys.exit("GFM_NORMALISED names examples that are not extension examples: %s" % sorted(stray))

    for section, exs in files.items():
        body = [
            "module sh.sysl.markdown",
            "@tests",
            "",
            "// GitHub's spec's '%s' examples (spec/gfm-spec.txt), read with gfm() and rendered with" % section,
            "// gfm_html(), compared exactly. Written by tools/gen_spec_tests.py; edit that, not this.",
        ]
        for n, md, html in exs:
            body.append("")
            if n in GFM_NORMALISED:
                html = GFM_NORMALISED[n]
                body.append("// The spec writes this normalised; this is the HTML cmark-gfm writes.")
            body += [
                '@test("gfm example %d")' % n,
                "gfm_example_%d()" % n,
                "    assert_eq(to_html_with(parse_with(%s, gfm()), gfm_html()), %s)" % (lit(md), lit(html)),
            ]
        write(GFM_PREFIX + section + ".sysl", body)

    stray = [n for n in GFM_CHANGES if not any(e["example"] == n for e in examples)]
    if stray:
        sys.exit("GFM_CHANGES names examples the spec does not have: %s" % sorted(stray))

    body = [
        "module sh.sysl.markdown",
        "@tests",
        "",
        "// The CommonMark 0.31.2 spec's examples read with every GitHub extension on: each renders as the",
        "// spec says, but for the few an extension changes, which assert what cmark-gfm renders with the",
        "// same extensions. Written by tools/gen_spec_tests.py from spec/spec.json; edit that, not this.",
    ]
    for e in examples:
        n = e["example"]
        html = e["html"]
        body.append("")
        if n in GFM_CHANGES:
            why, html = GFM_CHANGES[n]
            body.append("// %s" % why)
        body += [
            '@test("example %d with the GitHub extensions")' % n,
            "gfm_commonmark_%d()" % n,
            "    assert_eq(to_html_with(parse_with(%s, gfm()), gfm_html()), %s)" % (lit(e["markdown"]), lit(html)),
        ]
    write(GFM_PREFIX + "commonmark.sysl", body)

    print("%d GitHub extension examples in %d files; %d CommonMark examples with the extensions on, %d changed"
          % (sum(len(v) for v in files.values()), len(files), len(examples), len(GFM_CHANGES)))


def main():
    examples = json.load(open(SPEC, encoding="utf-8"))

    sections = {}
    for e in examples:
        sections.setdefault(e["section"], []).append(e)

    unknown = ENABLED - set(sections)
    if unknown:
        sys.exit("ENABLED names sections the spec does not have: %s" % sorted(unknown))

    stray = [n for n in IGNORED if not any(e["example"] == n and e["section"] in ENABLED for e in examples)]
    if stray:
        sys.exit("IGNORED names examples outside the ENABLED sections: %s" % sorted(stray))

    for name in os.listdir(OUT):
        if name.startswith(PREFIX) and name.endswith(".sysl"):
            os.remove(os.path.join(OUT, name))

    for section, exs in sections.items():
        on = section in ENABLED
        body = [
            "module sh.sysl.markdown",
            "@tests",
            "",
            "// The CommonMark 0.31.2 spec's examples from '%s', each rendered and compared exactly." % section,
            "// Written by tools/gen_spec_tests.py from spec/spec.json; edit that, not this.",
        ]
        for e in exs:
            n = e["example"]
            attr = '@test("example %d")' % n
            if not on:
                attr = '@test("example %d", ignore: "the parser does not read %s")' % (n, section)
            elif n in IGNORED:
                attr = '@test("example %d", ignore: "%s")' % (n, IGNORED[n])
            body += [
                "",
                attr,
                "example_%d()" % n,
                "    assert_eq(to_html(parse(%s)), %s)" % (lit(e["markdown"]), lit(e["html"])),
            ]
        with open(os.path.join(OUT, PREFIX + slug(section) + ".sysl"), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")

    total = len(examples)
    live = sum(len(sections[s]) for s in ENABLED) - len(IGNORED)
    print("%d sections, %d examples: %d run, %d ignored" % (len(sections), total, live, total - live))

    gfm(examples)
    footnotes()


main()
