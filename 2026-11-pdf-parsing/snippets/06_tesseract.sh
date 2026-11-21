#!/usr/bin/env bash
# OCR with Tesseract, and the words it was unsure about (article section 6).
#
#   ./06_tesseract.sh ../demo/scanned-page.jpg
#
# Needs the tesseract binary (distribution package `tesseract` plus a language
# pack such as `tesseract-data-eng`). For a PDF, render it first:
#   pdftoppm -r 300 -png scanned.pdf page
set -euo pipefail
img=${1:-../demo/scanned-page.jpg}

echo "===== text ====="
tesseract "$img" - 2>/dev/null

echo "===== words with confidence below 60 ====="
# TSV columns: level page block par line word left top width height conf text
tesseract "$img" - tsv 2>/dev/null |
  awk -F'\t' 'NR > 1 && $12 != "" && $11 >= 0 && $11 < 60 { printf "%5.1f  %s\n", $11, $12 }'
