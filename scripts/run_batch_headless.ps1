# 헤드리스 Claude로 뉴스 모니터링 배치 전체 사이클(수집+채점)을 실행한다.
# Windows 작업 스케줄러가 8·13·17시에 호출 → Claude 앱/세션 없이도 배치가 돈다.
# (API 키 불필요 — 로그인된 Claude Code 자격증명 사용. Claude 사용량은 소비됨.)
#
# ※ 이 파일은 반드시 UTF-8(BOM) 로 저장한다. Windows PowerShell 5.1은 BOM 없는
#    UTF-8 스크립트의 한글을 깨뜨리므로(=경로·주석 손상), 한글을 쓰려면 BOM이 필수다.
#    경로는 하드코딩하지 않고 $PSScriptRoot 로 런타임에 구한다(인코딩 무관 안전장치).
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot   # 프로젝트 루트 = scripts\ 의 상위
Set-Location -LiteralPath $root
$env:PYTHONIOENCODING = 'utf-8'

# 실행 로그: data\_headless_<날짜시각>.log
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $root ('data\_headless_{0}.log' -f $stamp)
"=== 배치 시작 $stamp ===" | Out-File -LiteralPath $log -Encoding utf8

# claude CLI 경로 확인(PATH 우선, 없으면 npm 전역 경로 폴백).
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
if (-not $claude) { $claude = Join-Path $env:APPDATA 'npm\claude.cmd' }
"claude = $claude" | Out-File -LiteralPath $log -Append -Encoding utf8

# 배치 프롬프트(한글)는 UTF-8로 명시해 읽고, 헤드리스 Claude(print 모드)로 실행한다.
# 무인 실행을 위해 권한 확인을 건너뛴다.
$prompt = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'batch_prompt.txt') -Raw -Encoding UTF8
$prompt | & $claude -p --dangerously-skip-permissions *>> $log

"=== 배치 종료 $(Get-Date -Format 'yyyyMMdd_HHmmss') exit=$LASTEXITCODE ===" | Out-File -LiteralPath $log -Append -Encoding utf8

# 오래된 헤드리스 로그 정리(최근 10개만 유지).
Get-ChildItem (Join-Path $root 'data') -Filter '_headless_*.log' |
  Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 |
  Remove-Item -Force -ErrorAction SilentlyContinue
