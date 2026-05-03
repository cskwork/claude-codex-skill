#!/usr/bin/env pwsh
# claude-codex-skill installer (Windows / PowerShell)
# Usage: iwr -useb https://raw.githubusercontent.com/cskwork/claude-codex-skill/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$skillDir = Join-Path $env:USERPROFILE ".claude\skills\codex-cli"
$skillUrl = "https://raw.githubusercontent.com/cskwork/claude-codex-skill/main/SKILL.md"

Write-Host "claude-codex-skill installer" -ForegroundColor Cyan
Write-Host ""

# Verify codex CLI
try {
    $codexVersion = (codex --version 2>$null) -replace '^codex-cli\s+', ''
    Write-Host "  [OK] codex CLI detected: $codexVersion" -ForegroundColor Green
} catch {
    Write-Host "  [WARN] codex CLI not found. Install from https://github.com/openai/codex" -ForegroundColor Yellow
}

# Verify codex login
try {
    $loginStatus = codex login status 2>&1
    if ($loginStatus -match "Logged in") {
        Write-Host "  [OK] codex login: $loginStatus" -ForegroundColor Green
    } else {
        Write-Host "  [WARN] codex not logged in. Run 'codex login' before using /codex image" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARN] could not verify codex login" -ForegroundColor Yellow
}

# Create skill directory
if (-not (Test-Path $skillDir)) {
    New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
}

# Download SKILL.md
$skillPath = Join-Path $skillDir "SKILL.md"
Write-Host ""
Write-Host "Downloading SKILL.md to $skillPath ..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $skillUrl -OutFile $skillPath -UseBasicParsing
Write-Host "  [OK] installed" -ForegroundColor Green
Write-Host ""
Write-Host "Restart Claude Code, then type /codex to confirm." -ForegroundColor Cyan
