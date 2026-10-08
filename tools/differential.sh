#!/bin/zsh
#
# Render a corpus of Markdown through this package and through cmark, and name every file whose HTML
# differs. cmark is the second oracle the spec's own expected HTML cannot be: it reads documents
# nobody wrote a test for.
#
#     tools/differential.sh [file or directory ...]
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
# The report names each differing file, and a unified diff of the two outputs is kept beside it in
# the scratch directory, whose path is printed last. Exits 1 if any file differs.

setopt err_exit pipe_fail no_unset

root=${0:A:h:h}
sysl_bin=${SYSL:-sysl}
cmark_bin=${CMARK:-cmark}

if ! command -v $cmark_bin > /dev/null; then
    print -u2 "differential: no '$cmark_bin' on PATH; install cmark (or set CMARK)"
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

print -r -- 'import sh.sysl.markdown.{parse, to_html}
import sysl.io.{read_all_text, stdin}

var input = stdin()

read_all_text(&input) match
    Ok(src) -> prints(to_html(parse(src)))
    Err(_) -> eprints("md2html: the input is not UTF-8\n")' > $prog/main.sysl

$sysl_bin build --lib $root -o $work/md2html.bin $prog > $work/build.log 2>&1 || {
    print -u2 "differential: building the renderer failed; see $work/build.log"
    exit 2
}

files=()

if (( $# == 0 )); then
    python3 -I $root/tools/split_examples.py $root/spec/spec.json $corpus spec > /dev/null
    python3 -I $root/tools/split_examples.py $root/spec/cmark-regression.txt $corpus regression > /dev/null

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

    $cmark_bin --unsafe < $file > $theirs

    if ! cmp -s $ours $theirs; then
        differing=$(( differing + 1 ))

        name=${${${file#$HOME/}//\//_}##[._]#}

        diff -u --label cmark --label markdown $theirs $ours > $diffs/$name.diff || true
        print -r -- "differs $file"
    fi
done

print -r -- "$compared compared, $differing differ, $undecodable not read; diffs in $diffs"

(( differing == 0 && undecodable == 0 ))
