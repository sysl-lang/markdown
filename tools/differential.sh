#!/bin/zsh
#
# Render a corpus of Markdown through this package and through cmark, and name every file whose HTML
# differs. cmark is the second oracle the spec's own expected HTML cannot be: it reads documents
# nobody wrote a test for.
#
#     tools/differential.sh [--gfm] [file or directory ...]
#
# With no arguments the corpus is
#
#   - the spec's 652 examples (spec/spec.json),
#   - cmark 0.31.2's regression examples (spec/cmark-regression.txt),
#   - the README.md of every repository under ~/dev/sysl-lang (a directory holding a .git directory;
#     a worktree is not a repository), and
#   - every .md file under ~/dev/sysl-lang/sysl-census-34/docs/content.
#
# Arguments replace that corpus: each file is read as it is, and each directory for its .md files.
#
# cmark runs with --unsafe, so that raw HTML is passed through as the spec renders it and as this
# package does. Our side is a small program written into a scratch directory and built against this
# checkout with --lib, so the package's own tree holds no program for `sysl test .` to walk.
#
# --gfm compares GitHub Flavored Markdown instead: this package parses with gfm()'s first five
# extensions (emoji, math, mermaid and alerts are github.com's, not cmark-gfm's) and renders with
# gfm_html(), and the other side is cmark-gfm (`CMARK_GFM` names another binary) run as
# `cmark-gfm --unsafe -e footnotes -e table -e strikethrough -e autolink -e tasklist -e tagfilter`.
# The default corpus then also holds every example of GitHub's spec (spec/gfm-spec.txt) and of
# cmark-gfm's own extension tests (spec/cmark-gfm-extensions.txt).
#
# The report names each differing file, and a unified diff of the two outputs is kept beside it in
# the scratch directory, whose path is printed last. Exits 1 if any file differs.

setopt err_exit pipe_fail no_unset extended_glob

root=${0:A:h:h}
sysl_bin=${SYSL:-sysl}
gfm=0

if [[ ${1:-} == --gfm ]]; then
    gfm=1
    shift
fi

if (( gfm )); then
    cmark_bin=${CMARK_GFM:-cmark-gfm}
    cmark_args=(--unsafe -e footnotes -e table -e strikethrough -e autolink -e tasklist -e tagfilter)
    imports='ParseOptions, parse_with, to_html_with, gfm_html, registry, footnotes, tables, strikethrough, autolinks, task_lists'
    render='to_html_with(parse_with(src, cmark_gfm()), gfm_html())'
    prelude='// gfm() less emoji(), math(), mermaid() and alerts(), which cmark-gfm does not have.
cmark_gfm() -> ParseOptions
    val r = registry()

    r.add(footnotes())
    r.add(tables())
    r.add(strikethrough())
    r.add(autolinks())
    r.add(task_lists())
    ParseOptions(r)
'
else
    cmark_bin=${CMARK:-cmark}
    cmark_args=(--unsafe)
    imports='parse, to_html'
    render='to_html(parse(src))'
    prelude=''
fi

if ! command -v $cmark_bin > /dev/null; then
    print -u2 "differential: no '$cmark_bin' on PATH; install it (or set CMARK / CMARK_GFM)"
    exit 2
fi

work=$(mktemp -d -t markdown-differential)
prog=$work/md2html
corpus=$work/corpus
diffs=$work/diffs

mkdir -p $prog $corpus $diffs

print -r -- 'package {
  name    = "md2html"
  version = "0.0.0"
  sysl    = "0.1.0-alpha.4"
}

dependencies {
  markdown { git = "github.com/sysl-lang/markdown", version = "0.1.0" }
}' > $prog/package.hocon

print -r -- "import sh.sysl.markdown.{$imports}
import sysl.io.{read_all_text, stdin}

$prelude
var input = stdin()

read_all_text(&input) match
    Ok(src) -> prints($render)
    Err(_) -> eprints(\"md2html: the input is not UTF-8\\n\")" > $prog/main.sysl

$sysl_bin build --lib $root -o $work/md2html.bin $prog > $work/build.log 2>&1 || {
    print -u2 "differential: building the renderer failed; see $work/build.log"
    exit 2
}

files=()

if (( $# == 0 )); then
    python3 -I $root/tools/split_examples.py $root/spec/spec.json $corpus spec > /dev/null
    python3 -I $root/tools/split_examples.py $root/spec/cmark-regression.txt $corpus regression > /dev/null

    if (( gfm )); then
        python3 -I $root/tools/split_examples.py $root/spec/gfm-spec.txt $corpus gfm > /dev/null
        python3 -I $root/tools/split_examples.py $root/spec/cmark-gfm-extensions.txt $corpus extensions > /dev/null
    fi

    files+=($corpus/*.md(N))

    for repo in ~/dev/sysl-lang/*(/N); do
        [[ -d $repo/.git && -f $repo/README.md ]] && files+=($repo/README.md)
    done

    files+=(~/dev/sysl-lang/sysl-census-34/docs/content/**/*.md(N))
else
    for arg in "$@"; do
        if [[ -d $arg ]]; then
            files+=($arg/**/*.md(N))
        else
            files+=($arg)
        fi
    done
fi

compared=0
differing=0
undecodable=0

for file in $files; do
    compared=$(( compared + 1 ))

    ours=$work/ours.html
    theirs=$work/theirs.html

    if ! $work/md2html.bin < $file > $ours 2> $work/ours.err || [[ -s $work/ours.err ]]; then
        undecodable=$(( undecodable + 1 ))
        print -r -- "unread  $file  ($(< $work/ours.err))"
        continue
    fi

    $cmark_bin $cmark_args < $file > $theirs

    if ! cmp -s $ours $theirs; then
        differing=$(( differing + 1 ))

        name=${${${file#$HOME/}//\//_}##[._]#}

        diff -u --label cmark --label markdown $theirs $ours > $diffs/$name.diff || true

        # cmark-gfm reads CommonMark 0.29 where cmark reads 0.31.2, so a file on which the two
        # disagree with every extension off is marked: its difference may be the spec's, not ours.
        if (( gfm )) && command -v ${CMARK:-cmark} > /dev/null && \
            ! cmp -s <($cmark_bin --unsafe < $file) <(${CMARK:-cmark} --unsafe < $file); then
            print -r -- "differs $file  (CommonMark 0.29 and 0.31.2 disagree on it)"
        else
            print -r -- "differs $file"
        fi
    fi
done

print -r -- "$compared compared, $differing differ, $undecodable not read; diffs in $diffs"

(( differing == 0 && undecodable == 0 ))
