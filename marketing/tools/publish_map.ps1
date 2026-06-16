# Generate iso_map.html and publish to GitHub Pages (one click)
#
# Usage (run inside marketing\tools):
#   .\publish_map.ps1
#   .\publish_map.ps1 -half 11
#   .\publish_map.ps1 -poi "villa,office" -area "opo"   # override (ASCII or Korean from CLI both OK)
#
# Korean default keywords live in isochrone.py (Python handles UTF-8 safely).
# This script is intentionally ASCII-only so Windows PowerShell 5.1 never mis-reads it.
#
# Prereqs:
#   - Keys once: setx KAKAO_REST_API_KEY "..."; setx KAKAO_JS_KEY "..."
#   - GitHub Pages on (Settings > Pages > Branch: claude/dental-offline-marketing-ags60d, folder: /docs)

param(
  [string]$poi  = "",
  [string]$area = "",
  [double]$half = 10,
  [double]$tf   = 0,      # OSRM time calibration factor (e.g. 1.8). 0 = use default 1.0
  [string]$engine = ""    # "kakao" for real Kakao Navi times (needs activation), else OSRM
)

$tools = $PSScriptRoot
$root  = (Resolve-Path (Join-Path $tools "..\..")).Path
$docs  = Join-Path $root "docs"
if (!(Test-Path $docs)) { New-Item -ItemType Directory -Path $docs | Out-Null }
$out = Join-Path $docs "iso_map.html"

Write-Host "[1/3] generating map..." -ForegroundColor Cyan
Set-Location $tools
$pyArgs = @("isochrone.py", "--half", $half, "--out", $out)
if ($poi)      { $pyArgs += @("--poi",  $poi) }
if ($area)     { $pyArgs += @("--area", $area) }
if ($tf -gt 0)  { $pyArgs += @("--time-factor", $tf) }
if ($engine)    { $pyArgs += @("--engine", $engine) }
python @pyArgs

if (!(Test-Path $out)) {
  Write-Host "FAILED: map not created. Check KAKAO_REST_API_KEY / KAKAO_JS_KEY." -ForegroundColor Red
  exit 1
}

Write-Host "[2/3] pushing to GitHub..." -ForegroundColor Cyan
Set-Location $root
git add docs/iso_map.html
git commit -m "Update published iso_map" 2>$null
git push origin HEAD

Write-Host ""
Write-Host "[3/3] Done! Live in ~1-2 min at:" -ForegroundColor Green
Write-Host "  https://metus8116-sketch.github.io/jdcsolution/iso_map.html" -ForegroundColor Yellow
Write-Host "  (first time: register https://metus8116-sketch.github.io in Kakao Web platform)" -ForegroundColor DarkGray
