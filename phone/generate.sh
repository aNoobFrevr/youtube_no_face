#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

TOPIC="${1:-}"
WORKFLOW="generate.yml"

if [[ -z "$TOPIC" ]]; then
  echo 'Usage: ./phone/generate.sh "topic"'
  exit 2
fi

gh workflow run "$WORKFLOW" --ref main -f topic="$TOPIC" -f from_stage=1
sleep 3
RUN_ID="$(gh run list --workflow "$WORKFLOW" --limit 1 --json databaseId --jq '.[0].databaseId')"

echo "Watching GitHub Actions run $RUN_ID"
gh run watch "$RUN_ID" --exit-status

DEST="$HOME/storage/downloads/youtube_no_face/$RUN_ID"
mkdir -p "$DEST"
gh run download "$RUN_ID" --dir "$DEST"
echo "Artifact downloaded to $DEST"
