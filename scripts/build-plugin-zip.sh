#!/usr/bin/env bash
# Build a distributable zip of the plugin for the Claude Code desktop app.
# Output: dist/jem-product-scrape-kit-intel-<version>.zip (dist/ is gitignored).
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="$(python3 -c "import json,sys; print(json.load(open('.claude-plugin/plugin.json'))['version'])")"
OUT="dist/jem-product-scrape-kit-intel-${VERSION}.zip"

mkdir -p dist
rm -f "$OUT"

# Zip the plugin at the archive root (so .claude-plugin/plugin.json is top-level).
# Exclude dev cruft and the marketplace manifest (that's for the marketplace route).
zip -r "$OUT" . \
  -x '.git/*' \
     '.venv/*' \
     '.pytest_cache/*' \
     '.superpowers/*' \
     '.agents/*' \
     'dist/*' \
     '*__pycache__/*' \
     '*.pyc' \
     '.DS_Store' \
     '.claude-plugin/marketplace.json' \
  >/dev/null

echo "built $OUT"
unzip -l "$OUT" | tail -1
