#!/usr/bin/env bash
# Rebuild numbers, figures and the PDF from the result files. Run from the repo root: bash paper/build.sh
set -euo pipefail
PY=".venv/Scripts/python.exe"; [ -x "$PY" ] || PY=python
TEX="${MIKTEX_BIN:-$LOCALAPPDATA/Programs/MiKTeX/miktex/bin/x64}"
[ -x "$TEX/pdflatex.exe" ] || TEX="$(dirname "$(command -v pdflatex)")"
"$PY" paper/make_numbers.py
"$PY" paper/make_figures.py
cd paper
for step in pdflatex bibtex pdflatex pdflatex; do
  if [ "$step" = bibtex ]; then "$TEX/bibtex" main >/dev/null; else
    "$TEX/pdflatex" -interaction=nonstopmode -halt-on-error main.tex >/dev/null; fi
done
grep -E "Warning: (Citation|Reference)|undefined" main.log || true
grep -o "Output written on main.pdf ([0-9]* pages" main.log
