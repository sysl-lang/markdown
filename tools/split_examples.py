#!/usr/bin/env python3
"""Write each example of a CommonMark spec corpus to a file of its own.

    split_examples.py <corpus> <out dir> <prefix>

<corpus> is either a spec.json (a list of {"markdown": ...} objects) or a file in the spec's own
text format, as cmark's test/regression.txt is: an example is the lines between a fence of 32
backticks followed by " example" and a line holding only ".", with "→" standing for a tab. Each
example's Markdown is written to <out dir>/<prefix>-<n>.md, numbered from 1 in the corpus's order.
"""

import json
import os
import sys

FENCE = "`" * 32


def from_json(text):
    return [e["markdown"] for e in json.loads(text)]


def from_spec_text(text):
    examples = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        if lines[i].startswith(FENCE) and lines[i][len(FENCE):].strip().startswith("example"):
            i += 1
            body = []

            while i < len(lines) and lines[i] != ".":
                body.append(lines[i] + "\n")
                i += 1

            examples.append("".join(body).replace("→", "\t"))

        i += 1

    return examples


def main():
    corpus, out, prefix = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(corpus, encoding="utf-8") as f:
        text = f.read()

    examples = from_json(text) if corpus.endswith(".json") else from_spec_text(text)

    os.makedirs(out, exist_ok=True)

    for n, md in enumerate(examples, 1):
        with open(os.path.join(out, "%s-%04d.md" % (prefix, n)), "w", encoding="utf-8", newline="") as f:
            f.write(md)

    print(len(examples))


main()
