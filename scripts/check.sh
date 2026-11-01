#!/bin/sh
# Unit tests on Kodi 19's Python (3.8) and a current one, the zip, and Kodi's
# kodi-addon-checker run the way the repo-scripts CI runs it. Needs uv.
set -eu
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1

for version in 3.8 3.12; do
  echo "== unit tests, Python $version"
  uv run --no-project --python "$version" python -m unittest discover -s tests -t .
done

echo "== zip"
uv run --no-project --python 3.12 python scripts/build_zip.py

echo "== kodi-addon-checker --branch=matrix"
find service.subtitles.subdl -name __pycache__ -prune -exec rm -rf {} +
uvx --python 3.12 kodi-addon-checker --branch=matrix --PR service.subtitles.subdl
