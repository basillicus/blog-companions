#!/usr/bin/env bash
# Rebuild the demo files from demo-page.html. Needs chromium, poppler-utils
# (pdftoppm) and ImageMagick 7 (magick).
set -euo pipefail
cd "$(dirname "$0")"

# born-digital PDF: Chromium writes a text layer and a tagged structure tree
chromium --headless --disable-gpu --no-first-run --no-pdf-header-footer \
  --user-data-dir="$(mktemp -d)" --print-to-pdf=demo-page.pdf demo-page.html
pdftoppm -r 110 -png -singlefile demo-page.pdf demo-page

# fake office scan: 150 dpi grayscale, rotated by one degree, blurred, noisy, JPEG,
# wrapped into a PDF without a text layer
pdftoppm -r 150 -gray -png -singlefile demo-page.pdf /tmp/scan150
magick /tmp/scan150.png -background white -rotate 1.0 -blur 0x0.6 \
  -attenuate 0.35 +noise Gaussian -quality 70 scanned-page.jpg
magick scanned-page.jpg -density 150 -units PixelsPerInch scanned-page.pdf

# the same scan with an ink blot over station B's phosphorus value (17)
magick /tmp/scan150.png -fill 'gray(25)' -draw "ellipse 778,601 22,15 0,360" \
  -fill 'gray(60)' -draw "ellipse 790,596 12,9 0,360" -background white -rotate 1.0 \
  -blur 0x0.6 -attenuate 0.35 +noise Gaussian -quality 70 damaged-page.jpg
