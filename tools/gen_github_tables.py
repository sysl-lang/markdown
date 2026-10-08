#!/usr/bin/env python3
"""Write GitHub's emoji shortcodes and its slug alphabet as packed tables, and the slug fixtures as tests.

    python3 tools/gen_github_tables.py

Three outputs, from three files vendored unmodified (README "The spec" has their SHA-256):

- sh/sysl/markdown/emoji_table.sysl, from spec/gemoji.json (github/gemoji's db/emoji.json): every
  alias and the emoji it names, as one sorted string of "\\u{2}alias\\u{1}emoji" records with a final
  "\\u{2}" -- the layout entity_table.sysl uses, read by the same bisection. GitHub's custom emoji
  (`:octocat:`, `:shipit:`) have no Unicode form and are not in the file, so they stay text.
- sh/sysl/markdown/slug_table.sysl, from spec/github-slugger-regex.js (github-slugger 2.0.0's
  generated regex): the code points a slug drops, as sorted ranges, each twelve hex digits -- six for
  the first code point and six for the last -- so a lookup bisects by record with no separator.
  The regex has no `u` flag, so it is matched against UTF-16: a code point past U+FFFF is tested as
  its surrogate pair, which is exactly how JavaScript reads it, quirks included.
- sh/sysl/markdown/tests_slug_fixtures.sysl, from spec/github-slugger-fixtures.json: github-slugger's
  own fixtures, run in order through one slugger as its test runs them.

When node is on the PATH, the drop set is also checked against the regex run by JavaScript itself.
"""

import json
import os
import re
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(ROOT, "spec")
OUT = os.path.join(ROOT, "sh", "sysl", "markdown")


def lit(s):
    """The body of a sysl string literal holding exactly s: letters and digits as they are,
    everything else as an escape, so no character the lexer treats specially is ever written."""
    return "".join(c if (c.isascii() and c.isalnum()) else "\\u{%x}" % ord(c) for c in s)


def readable(s):
    """A string literal body for a test: printable ASCII as it is, all else escaped."""
    return "".join(c if (" " <= c <= "~" and c not in "\"\\${}") else "\\u{%x}" % ord(c) for c in s)


def utf16(cp):
    """The code point as JavaScript holds it: itself, or its surrogate pair."""
    if cp < 0x10000:
        return chr(cp)
    v = cp - 0x10000
    return chr(0xD800 + (v >> 10)) + chr(0xDC00 + (v & 0x3FF))


def write(name, lines):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def emoji():
    rows = {}
    for e in json.load(open(os.path.join(SPEC, "gemoji.json"), encoding="utf-8")):
        for a in e["aliases"]:
            assert a not in rows, a
            assert re.fullmatch(r"[a-z0-9_+-]+", a), a
            rows[a] = e["emoji"]

    rows = sorted(rows.items())
    packed = "".join("\u0002" + n + "\u0001" + v for n, v in rows) + "\u0002"
    longest = max(len(n) for n, _ in rows)

    write("emoji_table.sysl", [
        "module sh.sysl.markdown",
        "",
        "// The %d emoji shortcodes GitHub reads, every alias of github/gemoji's db/emoji.json. Written" % len(rows),
        "// by tools/gen_github_tables.py from spec/gemoji.json; edit that, not this.",
        "//",
        "// One string of records \"\\u{2}alias\\u{1}emoji\", sorted by alias, with a \"\\u{2}\" after the last.",
        "",
        "/** The length of the longest alias, so that a scan for one can stop. */",
        "private[markdown] const EMOJI_NAME_MAX: usize = %d" % longest,
        "",
        "private[markdown] val emoji_records: string = \"%s\"" % lit(packed),
    ])
    return len(rows), len(packed.encode("utf-8")), longest


def dropped():
    src = open(os.path.join(SPEC, "github-slugger-regex.js"), encoding="utf-8").read()
    m = re.search(r"export const regex = /(.*)/g\s*$", src, re.S)
    rx = re.compile(m.group(1))
    drop = [cp for cp in range(0x110000) if not (0xD800 <= cp <= 0xDFFF) and rx.fullmatch(utf16(cp))]

    if shutil.which("node"):
        script = (
            "import {regex} from %s;\n"
            "const out = [];\n"
            "for (let cp = 0; cp < 0x110000; cp++) {\n"
            "  if (cp >= 0xD800 && cp <= 0xDFFF) continue;\n"
            "  const s = String.fromCodePoint(cp);\n"
            "  if (s.replace(regex, '') !== s) out.push(cp);\n"
            "}\n"
            "console.log(JSON.stringify(out));\n"
        ) % json.dumps("file://" + os.path.join(SPEC, "github-slugger-regex.js"))
        js = json.loads(subprocess.run(["node", "--input-type=module", "-e", script],
                                       capture_output=True, text=True, check=True).stdout)
        assert js == drop, "the Python reading of the regex disagrees with node's"
        print("checked against node: the same %d code points" % len(drop))

    ranges = []
    for cp in drop:
        if ranges and ranges[-1][1] + 1 == cp:
            ranges[-1][1] = cp
        else:
            ranges.append([cp, cp])

    # A surrogate is never in a string, so a range may run straight across the gap.
    merged = []
    for lo, hi in ranges:
        if merged and merged[-1][1] == 0xD7FF and lo == 0xE000:
            merged[-1][1] = hi
        else:
            merged.append([lo, hi])

    packed = "".join("%06x%06x" % (lo, hi) for lo, hi in merged)

    body = [
        "module sh.sysl.markdown",
        "",
        "// The %d code points a GitHub slug drops, in %d ranges: what github-slugger 2.0.0's regex" % (len(drop), len(merged)),
        "// matches. Written by tools/gen_github_tables.py from spec/github-slugger-regex.js; edit that, not",
        "// this.",
        "//",
        "// Each record is twelve hex digits, the first and the last code point of a range, six each.",
        "",
        "private[markdown] val slug_drop_ranges: string = \"%s\"" % packed,
    ]
    write("slug_table.sysl", body)
    return len(drop), len(merged)


def fixtures():
    rows = json.load(open(os.path.join(SPEC, "github-slugger-fixtures.json"), encoding="utf-8"))
    out = [
        "module sh.sysl.markdown",
        "",
        "@tests",
        "",
        "// github-slugger's own fixtures, in order, through one slugger as its test runs them -- the",
        "// duplicates in the list are numbered against the slugs before them. Written by",
        "// tools/gen_github_tables.py from spec/github-slugger-fixtures.json; edit that, not this.",
        "",
        "@test",
        "github_slugger_fixtures()",
        "    var s = slugger()",
        "",
    ]
    for r in rows:
        out.append("")
        out.append("    // %s" % readable(r["name"]))
        out.append("    assert_eq(s.unique(github_slug(\"%s\")), \"%s\")" % (readable(r["input"]), readable(r["expected"])))
    # The same list as headings of one document: each `# <input>` with every ASCII punctuation
    # character backslash-escaped, so that the heading's text is the input exactly (`__proto__` would
    # otherwise be strong emphasis), or the Markdown the fixture gives where a bare input would not
    # survive as a heading's text (a leading or trailing space, which a heading trims).
    def escaped(s):
        assert "\n" not in s, s
        return "".join("\\" + c if c in "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~" else c for c in s)

    doc = "".join((r.get("markdownOverwrite") or "# " + escaped(r["input"])) + "\n\n" for r in rows)
    out += [
        "",
        "@test",
        "github_slugger_fixtures_as_headings()",
        "    val d = parse_with(\"%s\", heading_id_options())" % readable(doc),
        "    val ids = heading_ids_of(d)",
        "",
        "    assert_eq(ids.len(), %d)" % len(rows),
    ]
    for i, r in enumerate(rows):
        out.append("    assert_eq(ids[%d], \"%s\")" % (i, readable(r["expected"])))
    write("tests_slug_fixtures.sysl", out)
    return len(rows)


def main():
    print("%d aliases, %d bytes packed, longest %d" % emoji())
    print("%d code points dropped, %d ranges" % dropped())
    print("%d slug fixtures" % fixtures())


main()
