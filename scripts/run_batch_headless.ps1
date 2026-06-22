# 헤드리스 Claude로 뉴스 모니터링 배치 전체 사이클(수집+채점)을 실행한다.
# Windows 작업 스케줄러가 8·13·17시에 호출 → Claude 앱/세션 없이도 배치가 돈다.
#
# 인증: 데스크톱 앱의 OAuth access 토큰은 짧게 만료되고 헤드리스는 갱신을 못 해 401난다.
#   → scripts\.headless_token (gitignore됨)에 `claude setup-token`으로 만든 장기 토큰(sk-ant-oat...)을
#     저장해 두면, 이 스크립트가 CLAUDE_CODE_OAUTH_TOKEN으로 주입해 안정적으로 인증한다.
#     (OAuth 토큰은 ANTHROPIC_API_KEY가 아니라 CLAUDE_CODE_OAUTH_TOKEN으로 줘야 동작)
#
# ※ 이 파일은 반드시 UTF-8(BOM)로 저장한다. Windows PowerShell 5.1은 BOM 없는
#    UTF-8 스크립트의 한글을 깨뜨리므로 경로는 $PSScriptRoot로 런타임에 구한다.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot   # 프로젝트 루트 = scripts\ 의 상위
Set-Location -LiteralPath $root
$env:PYTHONIOENCODING = 'utf-8'

# 실행 로그: data\_headless_<날짜시각>.log
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $root ('data\_headless_{0}.log' -f $stamp)
"=== 배치 시작 $stamp ===" | Out-File -LiteralPath $log -Encoding utf8

# 장기 인증 토큰 주입(있으면) — 헤드리스 OAuth 만료(401) 회피.
$tokFile = Join-Path $PSScriptRoot '.headless_token'
if (Test-Path -LiteralPath $tokFile) {
  $tok = (Get-Content -LiteralPath $tokFile -Raw).Trim()
  if ($tok) {
    $env:CLAUDE_CODE_OAUTH_TOKEN = $tok
    "OAuth 토큰 주입됨(길이 $($tok.Length))" | Out-File -LiteralPath $log -Append -Encoding utf8
  }
} else {
  "경고: scripts\.headless_token 없음 — OAuth 자격증명에 의존(만료 시 401 가능)" | Out-File -LiteralPath $log -Append -Encoding utf8
}

# claude CLI 경로(PATH 우선, 없으면 npm 전역 폴백).
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { $claude = Join-Path $env:APPDATA 'npm\claude.cmd' }
"claude = $claude" | Out-File -LiteralPath $log -Append -Encoding utf8

# 배치 프롬프트(한글)를 UTF-8로 읽어 헤드리스 Claude(print 모드)로 실행. 무인 실행 위해 권한 스킵.
$prompt = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'batch_prompt.txt') -Raw -Encoding UTF8
$prompt | & $claude -p --dangerously-skip-permissions *>> $log

"=== 배치 종료 $(Get-Date -Format 'yyyyMMdd_HHmmss') exit=$LASTEXITCODE ===" | Out-File -LiteralPath $log -Append -Encoding utf8

# 오래된 헤드리스 로그 정리(최근 10개만 유지).
Get-ChildItem (Join-Path $root 'data') -Filter '_headless_*.log' |
  Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 |
  Remove-Item -Force -ErrorAction SilentlyContinue
