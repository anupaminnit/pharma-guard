#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# push_to_github.sh
# Creates the GitHub repo and pushes PharmaGuard
#
# Usage:
#   chmod +x push_to_github.sh
#   GITHUB_TOKEN=your_token ./push_to_github.sh
# ──────────────────────────────────────────────────────────────

set -e

REPO_NAME="pharma-guard"
GITHUB_USER="${GITHUB_USER:-anupaminnit}"
DESCRIPTION="Multilingual pharmaceutical packaging compliance agent powered by Claude AI"

if [ -z "$GITHUB_TOKEN" ]; then
  echo "❌  GITHUB_TOKEN env var not set."
  echo "    Generate one at: https://github.com/settings/tokens (repo scope)"
  exit 1
fi

echo "🚀  Creating GitHub repository: $GITHUB_USER/$REPO_NAME"
curl -s -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d "{\"name\":\"$REPO_NAME\",\"description\":\"$DESCRIPTION\",\"private\":false,\"auto_init\":false}" \
  | python3 -c "import sys,json; r=json.load(sys.stdin); print('✓  Repo URL:', r.get('html_url', r.get('message','unknown')))"

echo ""
echo "📦  Initialising git and pushing..."

cd "$(dirname "$0")"

git init
git add -A
git commit -m "feat: initial PharmaGuard compliance agent

- FastAPI backend with Translation Agent + Vision Agent
- React dashboard with annotated PDF viewer
- Claude claude-sonnet-4-20250514 multimodal pipeline
- Supports French, German, Japanese, and 8+ languages
- Section-level semantic comparison with severity scoring"

git branch -M main
git remote remove origin 2>/dev/null || true
git remote add origin "https://$GITHUB_TOKEN@github.com/$GITHUB_USER/$REPO_NAME.git"
git push -u origin main

echo ""
echo "✅  Done! Repository live at:"
echo "    https://github.com/$GITHUB_USER/$REPO_NAME"
