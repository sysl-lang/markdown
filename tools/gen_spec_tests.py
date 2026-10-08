#!/usr/bin/env python3
"""Write the CommonMark spec examples as sysl tests, one file per spec section.

    python3 tools/gen_spec_tests.py

Reads spec/spec.json (CommonMark 0.31.2) and writes sh/sysl/markdown/tests_spec_<section>.sysl, each
example a `@test` asserting that parsing its Markdown and rendering the tree gives the spec's HTML
exactly -- no normalisation, since the spec's HTML is the reference renderer's own output.

A section not named in ENABLED is still generated, with every example marked `ignore`: the
assertion is the correct one and compiles, and it runs once the section is listed. The generated
files are committed; rerun this after changing ENABLED or the spec.
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "spec", "spec.json")
OUT = os.path.join(ROOT, "sh", "sysl", "markdown")
PREFIX = "tests_spec_"


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


main()
