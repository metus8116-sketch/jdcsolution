# 지도 생성 + GitHub Pages 게시 (원클릭)
#
# 사용법 (marketing\tools 폴더에서):
#   .\publish_map.ps1
#   .\publish_map.ps1 -poi "아파트,마을회관,경로당" -area "오포,모현" -half 11
#
# 사전 준비:
#   - 키 설정(1회): setx KAKAO_REST_API_KEY "...";  setx KAKAO_JS_KEY "..."
#   - GitHub Pages 켜두기 (Settings > Pages > Branch: claude/dental-offline-marketing-ags60d, 폴더: /docs)

param(
  [string]$poi  = "아파트,오피스텔,빌라,타운하우스,연립주택,마을회관,경로당",
  [string]$area = "오포,모현",
  [double]$half = 10
)

$tools = $PSScriptRoot
$root  = (Resolve-Path (Join-Path $tools "..\..")).Path
$docs  = Join-Path $root "docs"
if (!(Test-Path $docs)) { New-Item -ItemType Directory -Path $docs | Out-Null }

Write-Host "[1/3] 지도 생성 중..." -ForegroundColor Cyan
Set-Location $tools
python isochrone.py --poi $poi --area $area --half $half --out (Join-Path $docs "iso_map.html")
if (!(Test-Path (Join-Path $docs "iso_map.html"))) {
  Write-Host "지도 생성 실패. 키(KAKAO_REST_API_KEY/KAKAO_JS_KEY) 설정을 확인하세요." -ForegroundColor Red
  exit 1
}

Write-Host "[2/3] GitHub에 게시(push) 중..." -ForegroundColor Cyan
Set-Location $root
git add docs/iso_map.html
git commit -m "Update published iso_map" 2>$null
git push origin claude/dental-offline-marketing-ags60d

Write-Host ""
Write-Host "[3/3] 완료! 1~2분 뒤 아래 주소에서 보입니다:" -ForegroundColor Green
Write-Host "  https://metus8116-sketch.github.io/jdcsolution/iso_map.html" -ForegroundColor Yellow
Write-Host ""
Write-Host "※ 처음 1회: 카카오 콘솔 Web 플랫폼에 https://metus8116-sketch.github.io 등록 필요" -ForegroundColor DarkGray
