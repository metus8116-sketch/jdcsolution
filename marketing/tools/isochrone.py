#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
isochrone.py — 죽전에스치과까지 "차로 N분 이내" 도달 영역을 계산해서
카카오맵 위에 10/11/12/13분 색깔 띠(등시간 지도)로 그려주는 도구.

동작 방식:
  - 치과 좌표: 카카오 키워드/주소 검색 (카카오맵 API)
  - 드라이브타임: OSRM(무료·키 불필요·승인 불필요, 실시간 교통 미반영)으로 격자 점별 소요시간
  - 지역 이름: 카카오 좌표→행정구역(coord2regioncode) API로 "N분 이내 동/읍/리" 목록 추출
  - 시각화: 자체 완결형 HTML(iso_map.html) 생성 → 카카오맵 JavaScript SDK로 띠 표시

산출물:
  - iso_map.html : 브라우저로 열면 카카오맵에 색깔 띠가 표시됨 (JS 키 필요)
  - 콘솔 요약    : 10/11/12/13분 이내에 포함되는 행정구역 목록

필요한 것:
  - 카카오 REST API 키 (KAKAO_REST_API_KEY) : 치과 검색 + 좌표→행정구역
  - 카카오 JavaScript 키 (--js-key)         : iso_map.html 지도 표시용 (REST 키와 다름!)
    └ 카카오 콘솔 [앱 설정 > 앱 키 > JavaScript 키], 그리고 [플랫폼 > Web]에 http://localhost 등록

사용 예:
  export KAKAO_REST_API_KEY=REST키
  python3 isochrone.py --js-key JS키
  python3 isochrone.py --clinic "37.32,127.10" --js-key JS키 --spacing 0.4 --half 9
  # 그다음:  python3 -m http.server 8000   → 브라우저에서 http://localhost:8000/iso_map.html
"""

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KAKAO_LOCAL = "https://dapi.kakao.com/v2/local"
OSRM_TABLE = "https://router.project-osrm.org/table/v1/driving"

# 시간 띠 정의 (분 상한, 라벨, 색상)
BANDS = [
    (10, "≤ 10분", "#1b8a3a"),   # 진초록
    (11, "10~11분", "#7cc242"),  # 연두
    (12, "11~12분", "#f2c511"),  # 노랑
    (13, "12~13분", "#ef7d00"),  # 주황
]
MAX_MIN = BANDS[-1][0]


def kakao_get(url, key, params):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {key}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise SystemExit(f"[카카오 API 오류] HTTP {e.code}\n응답: {body}\n"
                         "→ 카카오맵(로컬) 활성화 / REST 키 / 플랫폼 등록을 확인하세요.")


def resolve_clinic(clinic, key, name_query):
    """치과 좌표 (lng, lat, label) 반환."""
    if clinic:
        s = clinic.strip()
        if "," in s:
            lat, lng = [float(p) for p in s.split(",")]
            return lng, lat, f"입력좌표({lat},{lng})"
    # 키워드 검색
    data = kakao_get(f"{KAKAO_LOCAL}/search/keyword.json", key, {"query": name_query, "size": 1})
    docs = data.get("documents", [])
    if docs:
        d = docs[0]
        return float(d["x"]), float(d["y"]), d.get("place_name", name_query)
    # 주소 검색 백업
    data = kakao_get(f"{KAKAO_LOCAL}/search/address.json", key, {"query": "경기 용인시 수지구 정든로 5"})
    docs = data.get("documents", [])
    if docs:
        d = docs[0]
        return float(d["x"]), float(d["y"]), d.get("address_name", name_query)
    raise SystemExit("[오류] 치과 좌표를 찾지 못했습니다. --clinic \"위도,경도\" 로 직접 넣어주세요.")


def build_grid(lat, lng, half_km, spacing_km):
    """치과 중심 정사각 격자 셀 중심점 목록 + 셀 반폭(도) 반환."""
    dlat = spacing_km / 110.574
    dlng = spacing_km / (111.320 * math.cos(math.radians(lat)))
    n = int(round(half_km / spacing_km))
    cells = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            cells.append((lat + i * dlat, lng + j * dlng))
    return cells, dlat / 2.0, dlng / 2.0


def osrm_durations(src_lng, src_lat, dests, chunk=90):
    """OSRM table로 출발지→각 목적지 소요시간(초) 목록. 실패분은 None."""
    out = []
    for k in range(0, len(dests), chunk):
        batch = dests[k:k + chunk]
        coords = ";".join([f"{src_lng},{src_lat}"] + [f"{lng},{lat}" for (lat, lng) in batch])
        dest_idx = ";".join(str(i) for i in range(1, len(batch) + 1))
        url = f"{OSRM_TABLE}/{coords}?sources=0&destinations={dest_idx}&annotations=duration"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "iso/1.0"})
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            row = data.get("durations", [[None] * len(batch)])[0]
            out.extend(row)
        except Exception as e:
            print(f"  [경고] OSRM 배치 실패({k}): {e}", file=sys.stderr)
            out.extend([None] * len(batch))
        time.sleep(0.4)  # 공용 서버 예의
    return out


def region_name(key, lng, lat, cache):
    """좌표→행정구역 (시군구 읍면동/리). 캐시(약 1km 격자)."""
    rk = (round(lat, 2), round(lng, 2))
    if rk in cache:
        return cache[rk]
    name = ""
    try:
        data = kakao_get(f"{KAKAO_LOCAL}/geo/coord2regioncode.json", key, {"x": lng, "y": lat})
        docs = data.get("documents", [])
        doc = next((d for d in docs if d.get("region_type") == "B"), docs[0] if docs else None)
        if doc:
            parts = [doc.get("region_2depth_name", ""), doc.get("region_3depth_name", ""),
                     doc.get("region_4depth_name", "")]
            name = " ".join(p for p in parts if p).strip()
    except SystemExit:
        name = ""
    except Exception:
        name = ""
    cache[rk] = name
    time.sleep(0.03)
    return name


def gather_pois(key, reachable, keywords, search_radius_m=800):
    """도달 영역 안에서 keywords(예: 아파트, 빌라, 마을회관) 시설 수집.
    반환: [(name, lat, lng, ptype, addr)] (중복 제거)."""
    coarse = {}
    for clat, clng, _m, _bi in reachable:
        ck = (round(clat, 2), round(clng, 2))  # 약 1.1km 격자로 검색 지점 축약
        coarse.setdefault(ck, (clat, clng))
    print(f"🏢 시설 수집: {keywords}  (검색 지점 {len(coarse)}곳 × {len(keywords)}종)", file=sys.stderr)
    found = {}
    for kw in keywords:
        for (clat, clng) in coarse.values():
            for page in (1, 2):
                params = {"query": kw, "x": clng, "y": clat,
                          "radius": search_radius_m, "sort": "distance", "size": 15, "page": page}
                try:
                    data = kakao_get(f"{KAKAO_LOCAL}/search/keyword.json", key, params)
                except SystemExit:
                    break
                for d in data.get("documents", []):
                    nm = d.get("place_name", "")
                    cat = d.get("category_name", "")
                    if kw not in nm and kw not in cat:
                        continue
                    pid = d["id"]
                    if pid in found:
                        continue
                    addr = d.get("road_address_name") or d.get("address_name", "")
                    found[pid] = (nm, float(d["y"]), float(d["x"]), kw, addr)
                if data.get("meta", {}).get("is_end", True):
                    break
                time.sleep(0.04)
    return list(found.values())


def region_of(addr):
    """주소에서 구/읍/면 단위 추출. 읍·면을 구보다 우선(더 구체적).
    예: '용인시 처인구 모현읍 오산리'→'모현읍', '용인시 수지구 죽전동'→'수지구'."""
    if not addr:
        return "기타"
    toks = addr.split()
    for tok in toks:                      # 1순위: 읍/면 (가장 구체적)
        if tok and tok[-1] in ("읍", "면"):
            return tok
    for tok in toks:                      # 2순위: 구
        if tok and tok[-1] == "구":
            return tok
    for tok in toks:                      # 3순위: 시/군
        if tok and tok[-1] in ("시", "군"):
            return tok
    return "기타"


def main():
    ap = argparse.ArgumentParser(description="죽전에스치과 차로 N분 등시간 지도 생성")
    ap.add_argument("--clinic", default=None, help="치과 좌표 '위도,경도' (미지정 시 카카오 검색)")
    ap.add_argument("--name", default="죽전에스치과", help="치과 검색어 (기본: 죽전에스치과)")
    ap.add_argument("--half", type=float, default=9.0, help="격자 반경 km (기본 9)")
    ap.add_argument("--spacing", type=float, default=0.5, help="격자 간격 km (작을수록 정밀·느림, 기본 0.5)")
    ap.add_argument("--js-key", default=os.environ.get("KAKAO_JS_KEY", ""), help="카카오 JavaScript 키 (지도 표시용)")
    ap.add_argument("--key", default=os.environ.get("KAKAO_REST_API_KEY"), help="카카오 REST 키")
    ap.add_argument("--out", default="iso_map.html", help="출력 HTML 파일명")
    ap.add_argument("--no-regions", action="store_true", help="행정구역 목록 추출 생략(더 빠름)")
    ap.add_argument("--poi", default="아파트,오피스텔,빌라,타운하우스,연립주택,마을회관,경로당",
                    help="시간대별로 세분할 시설 키워드(쉼표로 여러 개). 빈 문자열이면 시설 표시 안 함")
    ap.add_argument("--area", default="오포,모현",
                    help="주소에 이 단어가 포함된 곳만 표시(쉼표로 여러 개). 빈 문자열이면 전체")
    args = ap.parse_args()

    if not args.key:
        sys.exit("[오류] 카카오 REST 키가 없습니다. KAKAO_REST_API_KEY 또는 --key.")

    lng, lat, label = resolve_clinic(args.clinic, args.key, args.name)
    print(f"🏥 치과: {label}  (lat={lat}, lng={lng})")

    cells, half_lat, half_lng = build_grid(lat, lng, args.half, args.spacing)
    print(f"🧭 격자 {len(cells)}칸 (반경 {args.half}km, 간격 {args.spacing}km) — OSRM 드라이브타임 계산 중...")
    secs = osrm_durations(lng, lat, cells)

    # 도달 셀 분류
    reachable = []  # (lat, lng, minutes, band_index)
    for (clat, clng), s in zip(cells, secs):
        if s is None:
            continue
        m = s / 60.0
        if m > MAX_MIN:
            continue
        bi = next(i for i, b in enumerate(BANDS) if m <= b[0])
        reachable.append((clat, clng, round(m, 1), bi))
    print(f"✅ {MAX_MIN}분 이내 도달 셀: {len(reachable)}칸\n")

    # 행정구역 목록
    band_regions = [set() for _ in BANDS]
    if not args.no_regions and reachable:
        print("🗺  행정구역 이름 추출 중...", file=sys.stderr)
        cache = {}
        for clat, clng, m, bi in reachable:
            nm = region_name(args.key, clng, clat, cache)
            if nm:
                band_regions[bi].add(nm)

    # 누적(≤N분) 지역 출력
    print("=" * 70)
    print(f"🚗 '{label}'까지 차로 도달 가능한 지역 (OSRM 추정, 교통량 미반영)")
    print("=" * 70)
    cumulative = set()
    for bi, (cap, lbl, _color) in enumerate(BANDS):
        cumulative |= band_regions[bi]
        cells_n = sum(1 for r in reachable if r[3] <= bi)
        area = cells_n * args.spacing * args.spacing
        print(f"\n● 차로 {cap}분 이내  (약 {area:.1f}㎢, {cells_n}칸)")
        if cumulative:
            for nm in sorted(cumulative):
                print(f"    - {nm}")
        else:
            print("    (행정구역 추출 생략 또는 없음)")

    # 시설(아파트/빌라/타운하우스/마을회관 등) 세분화
    pois = []  # (name, lat, lng, minutes, band_index, ptype)
    poi_keywords = [k.strip() for k in args.poi.split(",") if k.strip()] if args.poi else []
    area_tokens = [a.strip() for a in args.area.split(",") if a.strip()] if args.area else []
    if poi_keywords and reachable:
        raw = gather_pois(args.key, reachable, poi_keywords)
        if area_tokens:
            raw = [r for r in raw if any(a in (r[4] or "") for a in area_tokens)]
            print(f"   지역필터 [{','.join(area_tokens)}] 적용 → {len(raw)}곳", file=sys.stderr)
        if raw:
            print(f"🚗 시설 {len(raw)}곳 드라이브타임 계산 중...", file=sys.stderr)
            psecs = osrm_durations(lng, lat, [(r[1], r[2]) for r in raw])
            for (name, plat, plng, ptype, addr), s in zip(raw, psecs):
                if s is None:
                    continue
                m = s / 60.0
                if m > MAX_MIN:
                    continue
                bi = next(i for i, b in enumerate(BANDS) if m <= b[0])
                pois.append((name, plat, plng, round(m, 1), bi, ptype, region_of(addr)))
        # 시간대별 출력
        title = "·".join(poi_keywords) + (f" @ {','.join(area_tokens)}" if area_tokens else "")
        print("\n" + "=" * 70)
        print(f"🏢 '{title}' 시설 세분화 (시간대별)")
        print("=" * 70)
        for bi, (cap, lbl, _c) in enumerate(BANDS):
            group = sorted([p for p in pois if p[4] == bi], key=lambda p: p[3])
            print(f"\n● 차로 {lbl}  ({len(group)}곳)")
            for name, _plat, _plng, m, _bi, ptype, region in group:
                print(f"    - [{ptype}|{region}] {name}  ({m:.0f}분)")
        # 합계 요약
        bcount = {i: sum(1 for p in pois if p[4] == i) for i in range(len(BANDS))}
        tcount = {}
        for p in pois:
            tcount[p[5]] = tcount.get(p[5], 0) + 1
        print("\n" + "-" * 70)
        print(f"📊 합계: 총 {len(pois)}곳")
        print("   시간대별: " + " / ".join(f"{BANDS[i][1]} {bcount[i]}곳" for i in range(len(BANDS))))
        print("   종류별:   " + " / ".join(f"{t} {c}곳" for t, c in tcount.items()))

    # HTML 생성
    write_html(args.out, args.js_key, label, lat, lng, reachable, half_lat, half_lng, pois)
    print("\n" + "=" * 70)
    print(f"🗺  지도 파일 생성: {args.out}")
    if not args.js_key:
        print("   ⚠ JavaScript 키가 없습니다. --js-key 로 넣어야 지도가 보입니다.")
    print("   보기:  python3 -m http.server 8000  실행 후")
    print(f"          브라우저에서 http://localhost:8000/{args.out}")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__TITLE__ 드라이브타임 지도</title>
<style>
  html,body{margin:0;height:100%;font-family:'Malgun Gothic',sans-serif}
  #map{width:100%;height:100%}
  #legend{position:absolute;left:12px;bottom:24px;z-index:5;background:#fff;
    padding:12px 14px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.25);font-size:13px}
  #legend b{display:block;margin-bottom:6px;font-size:14px}
  .row{display:flex;align-items:center;margin:3px 0}
  .sw{width:16px;height:16px;border-radius:3px;margin-right:8px;opacity:.55}
  #title{position:absolute;left:12px;top:12px;z-index:5;background:#fff;
    padding:8px 12px;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.2);font-size:14px}
  #warn{position:absolute;right:12px;top:12px;z-index:5;background:#fff3cd;color:#664d03;
    padding:6px 10px;border-radius:6px;font-size:11px;max-width:240px}
  #panel{position:absolute;right:12px;top:56px;bottom:24px;width:250px;z-index:5;background:#fff;
    border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,.25);font-size:12px;overflow-y:auto;padding:10px 12px}
  #panel b{font-size:14px}
  #panel .grp{margin-top:8px}
  #panel .gh{font-weight:bold;padding:3px 6px;border-radius:4px;color:#fff;display:inline-block;margin-bottom:3px}
  #panel .it{padding:1px 0 1px 8px;color:#333}
  #panel.hidden{display:none}
</style>
</head>
<body>
<div id="map"></div>
<div id="title"><b>🚗 __TITLE__</b><br/>차로 도달 시간대(분) 지도</div>
<div id="warn">OSRM 추정치(교통량 미반영). 광고 타깃 참고용.</div>
<div id="legend"><b>차로 도달 시간</b><div id="legend-rows"></div></div>
<div id="panel" class="hidden"><b>🏢 단지 목록</b><div id="panel-body"></div></div>
<script>
const JS_KEY = "__JSKEY__";
const ISO = __DATA__;
const BANDS = __BANDS__;

function initMap(){
  const center = new kakao.maps.LatLng(ISO.clinic.lat, ISO.clinic.lng);
  const map = new kakao.maps.Map(document.getElementById('map'), {center, level: 7});

  // 시간 띠 사각형
  ISO.cells.forEach(function(c){
    const sw = new kakao.maps.LatLng(c.lat - ISO.half.lat, c.lng - ISO.half.lng);
    const ne = new kakao.maps.LatLng(c.lat + ISO.half.lat, c.lng + ISO.half.lng);
    new kakao.maps.Rectangle({
      bounds: new kakao.maps.LatLngBounds(sw, ne),
      strokeWeight: 0, fillColor: BANDS[c.b].color, fillOpacity: 0.45
    }).setMap(map);
  });

  // 치과 마커
  const marker = new kakao.maps.Marker({position: center});
  marker.setMap(map);
  const iw = new kakao.maps.InfoWindow({
    content: '<div style="padding:6px 10px;font-size:13px">🏥 ' + ISO.clinic.name + '</div>'
  });
  iw.open(map, marker);

  // 범례
  const rows = document.getElementById('legend-rows');
  BANDS.forEach(function(b){
    const div = document.createElement('div'); div.className='row';
    div.innerHTML = '<span class="sw" style="background:'+b.color+'"></span>'+b.label;
    rows.appendChild(div);
  });

  // 시설 점 + (종류·지역) 필터 + 패널 목록
  const infoPoi = new kakao.maps.InfoWindow({zIndex: 10});
  if (ISO.pois && ISO.pois.length){
    const allCircles = [];  // {circle, poi}
    ISO.pois.forEach(function(p){
      const circle = new kakao.maps.Circle({
        center: new kakao.maps.LatLng(p.lat, p.lng),
        radius: 35, strokeWeight: 1, strokeColor: '#333', strokeOpacity: 0.8,
        fillColor: BANDS[p.b].color, fillOpacity: 0.95
      });
      circle.setMap(map);
      kakao.maps.event.addListener(circle, 'mouseover', function(){
        infoPoi.setContent('<div style="padding:4px 8px;font-size:12px">'+p.name+' · '+(p.t||'')+' · '+(p.r||'')+' · '+p.min+'분</div>');
        infoPoi.setPosition(new kakao.maps.LatLng(p.lat, p.lng));
        infoPoi.setMap(map);
      });
      kakao.maps.event.addListener(circle, 'mouseout', function(){ infoPoi.setMap(null); });
      allCircles.push({circle: circle, poi: p});
    });

    // 종류·지역 목록과 개수
    function counts(field){ const o={}; ISO.pois.forEach(function(p){o[p[field]]=(o[p[field]]||0)+1;}); return o; }
    const typeCnt = counts('t'), regionCnt = counts('r');
    const activeType = {}, activeRegion = {};
    Object.keys(typeCnt).forEach(function(t){ activeType[t]=true; });
    Object.keys(regionCnt).forEach(function(r){ activeRegion[r]=true; });

    function isVisible(p){ return activeType[p.t] && activeRegion[p.r]; }
    function applyFilters(){
      allCircles.forEach(function(o){ o.circle.setMap(isVisible(o.poi) ? map : null); });
      renderGroups();
    }

    const panel = document.getElementById('panel'); panel.classList.remove('hidden');
    const body = document.getElementById('panel-body');

    function makeFilter(title, cntObj, activeObj){
      const box = document.createElement('div');
      box.style.cssText = 'margin-bottom:8px;padding:6px 8px;background:#eef2f5;border-radius:6px;font-size:12px';
      box.innerHTML = '<b>'+title+'</b><br/>';
      Object.keys(cntObj).sort().forEach(function(k){
        const lab = document.createElement('label');
        lab.style.cssText = 'display:inline-block;margin:3px 8px 0 0;white-space:nowrap;cursor:pointer';
        lab.innerHTML = '<input type="checkbox" checked> '+k+'('+cntObj[k]+')';
        box.appendChild(lab);
        lab.querySelector('input').addEventListener('change', function(e){
          activeObj[k] = e.target.checked; applyFilters();
        });
      });
      return box;
    }
    body.appendChild(makeFilter('종류 필터', typeCnt, activeType));
    body.appendChild(makeFilter('지역 필터 (구/읍/면)', regionCnt, activeRegion));

    const groups = document.createElement('div');
    body.appendChild(groups);

    function renderGroups(){
      groups.innerHTML = '';
      const visible = ISO.pois.filter(isVisible);
      const sum = document.createElement('div');
      sum.style.cssText = 'margin:2px 0 8px;padding:6px 8px;background:#f4f6f8;border-radius:6px;font-size:12px';
      const tc = {}; visible.forEach(function(p){ tc[p.t] = (tc[p.t]||0)+1; });
      const tline = Object.keys(tc).map(function(k){ return k+' '+tc[k]; }).join(' / ');
      sum.innerHTML = '총 <b>'+visible.length+'</b>곳' + (tline ? ' &nbsp;<span style="color:#555">('+tline+')</span>' : '');
      groups.appendChild(sum);
      BANDS.forEach(function(b, bi){
        const grp = visible.filter(function(p){ return p.b===bi; }).sort(function(a,c){ return a.min-c.min; });
        if (!grp.length) return;
        const wrap = document.createElement('div'); wrap.className='grp';
        wrap.innerHTML = '<span class="gh" style="background:'+b.color+'">'+b.label+' ('+grp.length+')</span>';
        grp.forEach(function(p){
          const it = document.createElement('div'); it.className='it';
          it.textContent = '• '+p.name+' ['+(p.t||'')+'/'+(p.r||'')+'] ('+p.min+'분)';
          wrap.appendChild(it);
        });
        groups.appendChild(wrap);
      });
    }
    renderGroups();
  }
}

const s = document.createElement('script');
s.src = "//dapi.kakao.com/v2/maps/sdk.js?appkey=" + JS_KEY + "&autoload=false";
s.onload = function(){ kakao.maps.load(initMap); };
document.head.appendChild(s);
</script>
</body>
</html>
"""


def write_html(path, js_key, label, lat, lng, reachable, half_lat, half_lng, pois=None):
    data = {
        "clinic": {"lat": lat, "lng": lng, "name": label},
        "half": {"lat": half_lat, "lng": half_lng},
        "cells": [{"lat": r[0], "lng": r[1], "b": r[3]} for r in reachable],
        "pois": [{"name": p[0], "lat": p[1], "lng": p[2], "min": p[3], "b": p[4],
                  "t": (p[5] if len(p) > 5 else ""), "r": (p[6] if len(p) > 6 else "기타")}
                 for p in (pois or [])],
    }
    bands = [{"label": b[1], "color": b[2]} for b in BANDS]
    html = (HTML_TEMPLATE
            .replace("__TITLE__", label)
            .replace("__JSKEY__", js_key or "JS_KEY_HERE")
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BANDS__", json.dumps(bands, ensure_ascii=False)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
