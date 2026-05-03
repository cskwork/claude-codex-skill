#!/usr/bin/env bash
# claude-codex-skill installer (macOS / Linux)
# Usage: curl -fsSL https://raw.githubusercontent.com/cskwork/claude-codex-skill/main/install.sh | bash

set -euo pipefail

SKILL_DIR="${HOME}/.claude/skills/codex-cli"
SKILL_URL="https://raw.githubusercontent.com/cskwork/claude-codex-skill/main/SKILL.md"

echo "claude-codex-skill installer"
echo ""

if command -v codex >/dev/null 2>&1; then
  echo "  [OK] codex CLI detected: $(codex --version)"
else
  echo "  [WARN] codex CLI not found. Install from https://github.com/openai/codex"
fi

if codex login status 2>&1 | grep -q "Logged in"; then
  echo "  [OK] codex login: $(codex login status 2>&1 | head -1)"
else
  echo "  [WARN] codex not logged in. Run 'codex login' before using /codex image"
fi

mkdir -p "${SKILL_DIR}"

echo ""
echo "Downloading SKILL.md to ${SKILL_DIR}/SKILL.md ..."
curl -fsSL "${SKILL_URL}" -o "${SKILL_DIR}/SKILL.md"
echo "  [OK] installed"
echo ""
echo "Restart Claude Code, then type /codex to confirm."
