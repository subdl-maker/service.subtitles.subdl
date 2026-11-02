#!/bin/sh
# Run the add-on in a real Kodi inside Docker and check it end to end.
#
#   sh e2e/run.sh                   Kodi 21 (Debian trixie)
#   sh e2e/run.sh ubuntu:22.04      Kodi 19 (the oldest Kodi the add-on supports)
#   sh e2e/run.sh debian:trixie mock    one phase only (missing_key, refused_key, mock)
#   SUBDL_LIVE_KEY=... sh e2e/run.sh debian:trixie live    against the real API with a real key
#
# Needs a running Docker daemon (on a Mac: `colima start`). Screenshots and
# report.json land in e2e/out/<image>/. The refused-key phase sends one request with
# a made-up key to the real api.subdl.com; every other request goes to the mock.
set -eu
cd "$(dirname "$0")/.."
BASE="${1:-debian:trixie}"
[ $# -gt 0 ] && shift  # anything after the image names drive.py phases
TAG="subdl-kodi-e2e:$(echo "$BASE" | tr ':/' '--')"
NAME="subdl-kodi-e2e-$$"
OUT="e2e/out/$(echo "$BASE" | tr ':/' '--')"

docker build -q -t "$TAG" --build-arg BASE="$BASE" e2e >/dev/null
docker run -d --init --name "$NAME" --shm-size=512m "$TAG" sleep infinity >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT

find service.subtitles.subdl -name __pycache__ -prune -exec rm -rf {} +
docker cp service.subtitles.subdl "$NAME:/addon"
docker exec "$NAME" mkdir -p /harness
for file in setup.sh drive.py mock_subdl.py; do
  docker cp "e2e/$file" "$NAME:/harness/$file"
done
docker exec "$NAME" sh /harness/setup.sh
status=0
docker exec -e SUBDL_LIVE_KEY "$NAME" python3 /harness/drive.py "$@" || status=$?
rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
docker cp "$NAME:/harness/out" "$OUT"
docker cp "$NAME:/home/viewer/.kodi/temp/kodi.log" "$OUT/kodi.log" 2>/dev/null || true
echo "screenshots and report: $OUT"
exit $status
