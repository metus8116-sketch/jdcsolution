#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dentist_rank.py — 출발지에서 자동차로 가까운 치과 순위를 자동으로 뽑고,
특정 치과(기본: 죽전에스치과)가 몇 등인지 알려주는 도구.

네이버 지도에서 "출발지 → 주변 치과 → 거리순"을 손으로 세는 작업을 자동화합니다.
카카오 로컬 API(주변 치과 목록·좌표) + 카카오모빌리티 길찾기 API(실제 자동차 거리)를 사용합니다.

필요한 것: 카카오 REST API 키 1개 (developers.kakao.com)
  - "카카오맵(로컬) API" 활성화  → 주변 치과 검색/주소 좌표 변환
  - "카카오내비(모빌리티) 길찾기 API" 활성화 → 자동차 실제 거리 (driving 모드에서만)
  환경변수 KAKAO_REST_API_KEY 또는 --key 로 전달.

사용 예:
  export KAKAO_REST_API_KEY=발급받은키
  python3 dentist_rank.py --start "용인시 처인구 모현읍 오산리 양촌마을회관"
  python3 dentist_rank.py --start "37.31,127.17" --target "죽전에스치과" --radius 8000 --mode driving
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KAKAO_LOCAL = "https://dapi.kakao.com/v2/local"
KAKAO_NAVI = "https://apis-navi.kakaomobility.com/v1/directions"
OSRM = "https://router.project-osrm.org/route/v1/driving"


def _get(url, key, params=None):
    """카카오 API GET 요청 (Authorization: KakaoAK)."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {key}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        msg = [f"[카카오 API 오류] HTTP {e.code}", f"응답: {body}"]
        if e.code in (401, 403):
            msg += [
                "",
                "▶ 확인하세요 (카카오 developers 콘솔):",
                "  1) 쓰신 키가 'REST API 키'가 맞나요? (JavaScript/Admin 키 아님)",
                "  2) [앱 설정 > 플랫폼]에 Web 플랫폼이 1개 등록돼 있나요? (예: http://localhost)",
                "  3) [카카오맵] 사용 설정이 ON 인가요? (로컬/검색 API)",
                "  4) driving 모드라면 [카카오내비] 사용 설정도 ON 이어야 합니다.",
            ]
        raise SystemExit("\n".join(msg))


def resolve_start(start, key):
    """출발지를 (lng, lat, label)로 변환. 'lat,lng' 직접 입력 또는 주소/장소명 검색."""
    s = start.strip()
    # "lat,lng" 형식 직접 입력 지원
    if "," in s:
        parts = [p.strip() for p in s.split(",")]
        if len(parts) == 2:
            try:
                lat, lng = float(parts[0]), float(parts[1])
                return lng, lat, f"입력좌표({lat},{lng})"
            except ValueError:
                pass
    # 1) 주소 검색
    try:
        data = _get(f"{KAKAO_LOCAL}/search/address.json", key, {"query": s})
        docs = data.get("documents", [])
        if docs:
            d = docs[0]
            return float(d["x"]), float(d["y"]), d.get("address_name", s)
    except Exception:
        pass
    # 2) 장소(키워드) 검색 — 마을회관 등 상호/시설명
    data = _get(f"{KAKAO_LOCAL}/search/keyword.json", key, {"query": s, "size": 1})
    docs = data.get("documents", [])
    if not docs:
        raise SystemExit(f"[오류] 출발지를 찾지 못했습니다: {s}\n  → 'lat,lng' 좌표로 직접 넣어보세요.")
    d = docs[0]
    return float(d["x"]), float(d["y"]), f'{d.get("place_name","")} ({d.get("address_name","")})'


def search_dentists(lng, lat, key, keyword="치과", radius=8000, max_count=45):
    """주변 치과를 직선거리순으로 수집 (최대 45곳)."""
    results = []
    seen = set()
    for page in range(1, 4):  # 카카오 키워드검색 최대 3페이지 × 15 = 45
        params = {
            "query": keyword,
            "x": f"{lng}",
            "y": f"{lat}",
            "radius": min(int(radius), 20000),  # 최대 20km
            "sort": "distance",
            "page": page,
            "size": 15,
        }
        data = _get(f"{KAKAO_LOCAL}/search/keyword.json", key, params)
        for d in data.get("documents", []):
            cat = d.get("category_name", "")
            name = d.get("place_name", "")
            # 치과만 필터 (병원 카테고리 중 치과)
            if "치과" not in cat and "치과" not in name:
                continue
            pid = d.get("id")
            if pid in seen:
                continue
            seen.add(pid)
            results.append({
                "name": name,
                "addr": d.get("road_address_name") or d.get("address_name", ""),
                "lng": float(d["x"]),
                "lat": float(d["y"]),
                "straight_m": int(d.get("distance") or 0),
                "phone": d.get("phone", ""),
            })
        if data.get("meta", {}).get("is_end", True):
            break
        time.sleep(0.15)  # 호출 간격
        if len(results) >= max_count:
            break
    return results[:max_count]


def driving_distance(o_lng, o_lat, d_lng, d_lat, key, engine="osrm"):
    """자동차 도로 거리(m)·시간(s) 반환. 실패 시 None.

    engine="osrm"  : 무료·키 불필요·승인 불필요 (OpenStreetMap 기반, 실시간 교통 미반영)
    engine="kakao" : 카카오내비 길찾기 (실시간 교통 반영, [카카오내비] 활성화 필요)
    """
    if engine == "kakao":
        params = {
            "origin": f"{o_lng},{o_lat}",
            "destination": f"{d_lng},{d_lat}",
            "priority": "RECOMMEND",
        }
        try:
            data = _get(KAKAO_NAVI, key, params)
            routes = data.get("routes", [])
            if not routes or routes[0].get("result_code") != 0:
                return None
            s = routes[0]["summary"]
            return int(s["distance"]), int(s["duration"])
        except SystemExit:
            return None
        except Exception:
            return None
    # OSRM (기본)
    url = f"{OSRM}/{o_lng},{o_lat};{d_lng},{d_lat}?overview=false"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dentist-rank/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        routes = data.get("routes", [])
        if not routes:
            return None
        return int(routes[0]["distance"]), int(routes[0]["duration"])
    except Exception:
        return None


def norm(s):
    return s.replace(" ", "").lower()


def main():
    ap = argparse.ArgumentParser(description="출발지 기준 가까운 치과 순위 + 특정 치과 등수")
    ap.add_argument("--start", required=True, help="출발지 주소/장소명 또는 'lat,lng'")
    ap.add_argument("--target", default="죽전에스치과", help="등수를 확인할 치과명 (기본: 죽전에스치과)")
    ap.add_argument("--keyword", default="치과", help="검색 키워드 (기본: 치과)")
    ap.add_argument("--radius", type=int, default=8000, help="검색 반경 m (기본 8000, 최대 20000)")
    ap.add_argument("--mode", choices=["driving", "straight"], default="driving",
                    help="driving=자동차 실제 거리(기본), straight=직선거리")
    ap.add_argument("--engine", choices=["osrm", "kakao"], default="osrm",
                    help="driving 거리 계산 엔진: osrm=무료·승인불필요(기본), kakao=카카오내비(승인필요)")
    ap.add_argument("--key", default=os.environ.get("KAKAO_REST_API_KEY"), help="카카오 REST 키")
    args = ap.parse_args()

    if not args.key:
        sys.exit("[오류] 카카오 REST 키가 없습니다. KAKAO_REST_API_KEY 환경변수 또는 --key 로 전달하세요.")

    lng, lat, label = resolve_start(args.start, args.key)
    print(f"📍 출발지: {label}  (lat={lat}, lng={lng})")

    cands = search_dentists(lng, lat, args.key, args.keyword, args.radius)
    if not cands:
        sys.exit(f"[안내] 반경 {args.radius}m 내 치과를 찾지 못했습니다. --radius 를 키워보세요.")
    print(f"🦷 반경 {args.radius}m 내 치과 {len(cands)}곳 수집 완료\n")

    if args.mode == "driving":
        eng = "카카오내비" if args.engine == "kakao" else "OSRM(무료)"
        print(f"🚗 자동차 거리 계산 중... (엔진: {eng})", file=sys.stderr)
        for c in cands:
            res = driving_distance(lng, lat, c["lng"], c["lat"], args.key, args.engine)
            if res:
                c["drive_m"], c["drive_s"] = res
            else:
                c["drive_m"], c["drive_s"] = None, None
            time.sleep(0.12)
        # 자동차 거리 있는 것 우선, 그다음 직선거리 (길찾기 실패분은 직선거리로 보정)
        cands.sort(key=lambda c: (c["drive_m"] if c["drive_m"] is not None else c["straight_m"] + 10**9))
        key_m = "drive_m"
    else:
        cands.sort(key=lambda c: c["straight_m"])
        key_m = "straight_m"

    # 출력
    print(f"{'순위':>3} {'치과명':<22} {'자동차거리/시간' if args.mode=='driving' else '직선거리':<16} 주소")
    print("-" * 90)
    target_rank = None
    tnorm = norm(args.target)
    for i, c in enumerate(cands, 1):
        if args.mode == "driving" and c.get("drive_m") is not None:
            dist = f"{c['drive_m']/1000:.1f}km / {round(c['drive_s']/60)}분"
        elif args.mode == "driving":
            dist = f"(길찾기실패) 직선 {c['straight_m']/1000:.1f}km"
        else:
            dist = f"{c['straight_m']/1000:.1f}km"
        mark = ""
        if tnorm and (tnorm in norm(c["name"]) or norm(c["name"]) in tnorm):
            mark = "  ⬅ 여기!"
            if target_rank is None:
                target_rank = i
        print(f"{i:>3} {c['name'][:22]:<22} {dist:<16} {c['addr']}{mark}")

    print("\n" + "=" * 90)
    if target_rank:
        print(f"✅ '{args.target}' 은(는) 반경 {args.radius}m 내 치과 {len(cands)}곳 중 "
              f"자동차 거리 기준 **{target_rank}등** 입니다.")
    else:
        print(f"⚠ '{args.target}' 은(는) 반경 {args.radius}m 내 목록에 없습니다 "
              f"(더 멀리 있을 수 있음 → --radius 를 키워서 재실행).")


if __name__ == "__main__":
    main()
