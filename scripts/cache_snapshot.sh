#!/bin/sh
# Pack or restore the Wikidata cache that the published numbers were computed from.
#   scripts/cache_snapshot.sh pack     -> eval/wikidata-cache.tar.gz + .sha256
#   scripts/cache_snapshot.sh restore  <- eval/wikidata-cache.tar.gz (checksum verified)
# With the restored cache, `uv run wdlink eval --offline` reproduces eval/results/ exactly.
set -eu
cd "$(dirname "$0")/.."
ARCHIVE=eval/wikidata-cache.tar.gz
case "${1:-}" in
  pack)
    mkdir -p dist
    tar -czf "$ARCHIVE" -C .cache wikidata
    shasum -a 256 "$ARCHIVE" > "$ARCHIVE.sha256"
    du -h "$ARCHIVE"; cat "$ARCHIVE.sha256"
    ;;
  restore)
    shasum -a 256 -c "$ARCHIVE.sha256"
    mkdir -p .cache
    tar -xzf "$ARCHIVE" -C .cache
    echo "restored .cache/wikidata ($(cat .cache/wikidata/manifest.json | tr -d '\n '))"
    ;;
  *)
    echo "usage: $0 pack|restore" >&2; exit 2
    ;;
esac
