#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage: scripts/sync_with_comment.sh \"commit message\" [\"commit body\"]" >&2
  exit 2
fi

message="$1"
body="${2:-}"

git add -A

if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

if [ "$body" = "" ]; then
  git commit -m "$message"
else
  git commit -m "$message" -m "$body"
fi

git push
