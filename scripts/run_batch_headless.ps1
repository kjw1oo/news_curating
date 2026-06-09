# Headless Claude batch runner for Windows Task Scheduler (collect + score).
# No API key needed; uses the logged-in Claude Code credentials. Consumes Claude usage.
# ASCII-only on purpose: Windows PowerShell 5.1 misreads BOM-less UTF-8 scripts, so we
# derive paths at runtime via $PSScriptRoot instead of hardcoding the (Korean) project path.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot   # project root = parent of scripts\
Set-Location -LiteralPath $root
$env:PYTHONIOENCODING = 'utf-8'

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $root ('data\_headless_{0}.log' -f $stamp)
"=== batch start $stamp ===" | Out-File -LiteralPath $log -Encoding utf8

# Resolve the claude CLI (PATH first, then npm global fallback).
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { $claude = Join-Path $env:APPDATA 'npm\claude.cmd' }
"claude = $claude" | Out-File -LiteralPath $log -Append -Encoding utf8

# Read the batch prompt as UTF-8 (it contains Korean) and run headless Claude (print mode).
$prompt = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'batch_prompt.txt') -Raw -Encoding UTF8
$prompt | & $claude -p --dangerously-skip-permissions *>> $log

"=== batch end $(Get-Date -Format 'yyyyMMdd_HHmmss') exit=$LASTEXITCODE ===" | Out-File -LiteralPath $log -Append -Encoding utf8

# Keep only the 10 most recent headless logs.
Get-ChildItem (Join-Path $root 'data') -Filter '_headless_*.log' |
  Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 |
  Remove-Item -Force -ErrorAction SilentlyContinue
