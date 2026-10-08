#!/usr/bin/env python3
"""Write the HTML5 named character references as one sorted packed string.

    python3 tools/gen_entities.py

Reads spec/entities.json (WHATWG's https://html.spec.whatwg.org/entities.json, vendored unmodified)
and writes sh/sysl/markdown/entity_table.sysl. CommonMark recognises only the names written with a
closing ';', so the ones without are left out.

The table is one string literal rather than an array of pairs: a literal compiles in a fraction of
the time thousands of tuple constructors take, and every cold build of a program using this package
pays that cost. Each record is "\\u{2}name\\u{1}value", the records sorted by name byte by byte, and a
final "\\u{2}" ends the last one -- so a lookup can bisect by byte offset, backing up to a record's
"\\u{2}", with no index to compile either.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "spec", "entities.json")
OUT = os.path.join(ROOT, "sh", "sysl", "markdown", "entity_table.sysl")


def lit(s):
    """The body of a sysl string literal holding exactly s: letters and digits as they are,
    everything else as an escape, so no character the lexer treats specially is ever written."""
    return "".join(c if (c.isascii() and c.isalnum()) else "\\u{%x}" % ord(c) for c in s)


def main():
    entities = json.load(open(SRC, encoding="utf-8"))
    rows = sorted((k[1:-1], v["characters"]) for k, v in entities.items() if k.endswith(";"))

    for name, value in rows:
        assert name.isascii() and name.isalnum(), name
        assert "\u0001" not in value and "\u0002" not in value, name

    packed = "".join("\u0002" + n + "\u0001" + v for n, v in rows) + "\u0002"
    longest = max(len(n) for n, _ in rows)

    body = [
        "module sh.sysl.markdown",
        "",
        "// The %d HTML5 named character references CommonMark recognises, those written with a" % len(rows),
        "// closing ';'. Written by tools/gen_entities.py from spec/entities.json; edit that, not this.",
        "//",
        "// One string of records \"\\u{2}name\\u{1}value\", sorted by name, with a \"\\u{2}\" after the last.",
        "",
        "/** The length of the longest name, so that a scan for one can stop. */",
        "private[markdown] const ENTITY_NAME_MAX: usize = %d" % longest,
        "",
        "private[markdown] val entity_records: string = \"%s\"" % lit(packed),
    ]
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n")

    print("%d entities, %d bytes packed, longest name %d" % (len(rows), len(packed.encode("utf-8")), longest))


main()
