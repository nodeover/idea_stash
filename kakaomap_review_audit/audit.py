# -*- coding: utf-8 -*-
"""카카오맵 리뷰 주작(별점 세탁) 감별기.

카카오맵 장소 패널이 실제로 호출하는 내부 API에서 리뷰 전량과 작성자
프로필을 수집한 뒤, 조작 신호를 지표화한다. 절대 기준으로 판단하지 않고
같은 동네 동종 업장을 대조군으로 함께 뽑아 상대 비교하는 것이 핵심이다.

사용법:
    python3 audit.py <장소ID 또는 카카오맵 URL> [-c 대조군ID ...] [-o out.json]
"""

import argparse
import json
import re
import statistics
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime

API = "https://place-api.map.kakao.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://place.map.kakao.com/",
    "Origin": "https://place.map.kakao.com",
    "Accept": "application/json",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "pf": "web",
}


def fetch(url, retries=4):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 204:
                    return None
                return json.loads(resp.read().decode())
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def resolve_place_id(target):
    """장소 ID, place.map.kakao.com URL, kko.to 단축 URL을 모두 받는다."""
    if target.isdigit():
        return target
    if "kko.to" in target or target.startswith("http"):
        req = urllib.request.Request(target, headers={"User-Agent": HEADERS["User-Agent"]})

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_args):
                return None

        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(req, timeout=20) as resp:
                target = resp.geturl()
        except urllib.error.HTTPError as err:
            target = err.headers.get("Location") or target
    found = re.search(r"(?:id=|place\.map\.kakao\.com/)(\d{6,})", target)
    if not found:
        raise SystemExit("장소 ID를 찾을 수 없습니다: %s" % target)
    return found.group(1)


def fetch_place(pid):
    return fetch("%s/places/panel3/%s" % (API, pid)) or {}


def fetch_reviews(pid, max_pages=200, pause=0.25):
    """카카오맵 리뷰를 최신순으로 끝까지 수집한다."""
    reviews, last_id = [], ""
    for page in range(max_pages):
        url = "%s/places/tab/reviews/kakaomap/%s?order=LATEST&only_photo_review=false" % (API, pid)
        if last_id:
            url += "&previous_last_review_id=%s" % last_id
        data = fetch(url)
        batch = data.get("reviews") if data else None
        if not batch:
            break
        reviews.extend(batch)
        last_id = batch[-1]["review_id"]
        if not data.get("has_next"):
            break
        time.sleep(pause)
    seen, unique = set(), []
    for r in reviews:
        if r["review_id"] in seen:
            continue
        seen.add(r["review_id"])
        unique.append(r)
    return unique


def enrich(reviews):
    for r in reviews:
        owner = r["meta"]["owner"]
        r["_at"] = datetime.strptime(r["registered_at"], "%Y-%m-%d %H:%M:%S")
        r["_text"] = (r.get("contents") or "").strip()
        r["_photos"] = r.get("photo_count") or 0
        r["_author_reviews"] = owner.get("review_count") or 0
        r["_author_avg"] = owner.get("average_score")
        r["_followers"] = owner.get("follower_count") or 0
    reviews.sort(key=lambda r: r["_at"])
    return reviews


def metrics(reviews):
    """대조군과 직접 비교할 수 있는 핵심 지표만 뽑는다."""
    n = len(reviews)
    if not n:
        return {}
    heavy = [r for r in reviews if r["_author_reviews"] >= 10]
    pct = lambda xs: len(xs) / n * 100
    return {
        "표본": n,
        "평균별점": round(sum(r["star_rating"] for r in reviews) / n, 2),
        "5점비율": round(pct([r for r in reviews if r["star_rating"] == 5]), 1),
        "3점이하비율": round(pct([r for r in reviews if r["star_rating"] <= 3]), 1),
        "사진첨부비율": round(pct([r for r in reviews if r["_photos"] > 0]), 1),
        "1회성계정비율": round(pct([r for r in reviews if r["_author_reviews"] <= 1]), 1),
        "작성자평점5.00비율": round(
            pct([r for r in reviews if r["_author_avg"] and abs(r["_author_avg"] - 5.0) < 1e-6]), 1
        ),
        "헤비유저표본": len(heavy),
        "헤비유저평균별점": round(sum(r["star_rating"] for r in heavy) / len(heavy), 2) if heavy else None,
    }


def suspicion_score(m):
    """0~100. 높을수록 별점이 인위적으로 부풀려졌을 가능성이 크다.

    각 항목은 정상 업장에서 관측되는 범위를 기준선으로 잡고,
    초과분만 가중 합산한다.
    """
    if not m:
        return 0, []
    flags = []
    score = 0
    rules = [
        ("1회성계정비율", 15, 0.55, "리뷰가 1개뿐인 계정 비중"),
        ("사진첨부비율", 60, 0.45, "사진 첨부 비율"),
        ("5점비율", 65, 0.40, "5점 비율"),
        ("작성자평점5.00비율", 35, 0.25, "작성자 평생 평점이 정확히 5.00인 비중"),
    ]
    for key, baseline, weight, label in rules:
        value = m.get(key)
        if value is None:
            continue
        excess = max(0.0, value - baseline)
        score += excess * weight
        if excess > 0:
            flags.append("%s %.1f%% (정상 상한 %d%%)" % (label, value, baseline))
    gap = None
    if m.get("헤비유저평균별점") is not None:
        gap = round(m["평균별점"] - m["헤비유저평균별점"], 2)
        if gap > 0.2:
            score += gap * 40
            flags.append("표시 평점이 헤비유저 평점보다 %.2f점 높음" % gap)
    return min(100, round(score)), flags


def report(name, reviews, place):
    n = len(reviews)
    m = metrics(reviews)
    score, flags = suspicion_score(m)

    print("=" * 66)
    print("장소: %s" % name)
    addr = ((place.get("summary") or {}).get("address") or {}).get("disp")
    if addr:
        print("주소: %s" % addr)
    score_set = (place.get("kakaomap_review") or {}).get("score_set") or {}
    if score_set:
        print("카카오맵 표시 평점: %s (%s건)" % (score_set.get("average_score"), score_set.get("review_count")))
    print("수집 리뷰: %d건  (%s ~ %s)" % (n, reviews[0]["_at"].date(), reviews[-1]["_at"].date()))
    print("=" * 66)

    print("\n[1] 별점 분포")
    dist = Counter(r["star_rating"] for r in reviews)
    for star in range(5, 0, -1):
        cnt = dist.get(star, 0)
        print("  %d점 %5d  %5.1f%% %s" % (star, cnt, cnt / n * 100, "#" * int(cnt / n * 50)))

    print("\n[2] 작성자 신뢰도 — 리뷰 수 구간별 별점")
    print("  이 구간 사이의 점수 낙차가 조작의 가장 직접적인 증거다.")
    buckets = [(0, 1, "1개(1회성)"), (2, 2, "2개"), (3, 5, "3-5개"),
               (6, 9, "6-9개"), (10, 29, "10-29개"), (30, 10 ** 9, "30개+")]
    for lo, hi, label in buckets:
        grp = [r for r in reviews if lo <= r["_author_reviews"] <= hi]
        if not grp:
            continue
        avg = sum(r["star_rating"] for r in grp) / len(grp)
        p5 = sum(1 for r in grp if r["star_rating"] == 5) / len(grp) * 100
        low = sum(1 for r in grp if r["star_rating"] <= 3) / len(grp) * 100
        print("  %-10s n=%5d  평균 %.2f  5점 %5.1f%%  3점이하 %4.1f%%" % (label, len(grp), avg, p5, low))

    print("\n[3] 작성 시각 분포 — 매장에서 즉석 작성했는지 본다")
    by_hour = Counter(r["_at"].hour for r in reviews)
    peak = max(by_hour.values())
    meal = sum(by_hour.get(h, 0) for h in (11, 12, 13, 14, 17, 18, 19, 20))
    for hour in range(24):
        cnt = by_hour.get(hour, 0)
        if cnt:
            print("  %02d시 %5d %s" % (hour, cnt, "#" * int(cnt / peak * 40)))
    print("  → 식사시간대(11-14,17-20시) 집중도: %.1f%%" % (meal / n * 100))

    print("\n[4] 본문 패턴")
    lengths = [len(r["_text"]) for r in reviews if r["_text"]]
    if lengths:
        print("  글 없이 별점만: %.1f%%" % (sum(1 for r in reviews if not r["_text"]) / n * 100))
        print("  본문 길이 중앙값: %d자, 10자 이하 단문: %.1f%%"
              % (statistics.median(lengths), sum(1 for x in lengths if x <= 10) / len(lengths) * 100))
    dup = Counter(r["_text"] for r in reviews if r["_text"])
    repeats = [(t, c) for t, c in dup.items() if c >= 3]
    print("  똑같은 문구 3회 이상 반복: %d종" % len(repeats))
    for text, cnt in sorted(repeats, key=lambda x: -x[1])[:5]:
        print("    %3d회  %r" % (cnt, text[:40]))

    print("\n[5] 리뷰 이벤트 자백 리뷰")
    print("  다른 손님이 직접 이벤트를 언급한 리뷰는 가장 강력한 증거다.")
    tell = [r for r in reviews
            if re.search(r"(리뷰|후기)\s*이벤트", r["_text"]) or "조작" in r["_text"]]
    print("  %d건 발견" % len(tell))
    for r in tell[:8]:
        print("    [%d점 %s] %s" % (r["star_rating"], r["_at"].date(), r["_text"][:70].replace("\n", " ")))

    print("\n[6] 저평점 리뷰 (3점 이하) — 실제 불만 지점")
    for r in [r for r in reviews if r["star_rating"] <= 3][-10:]:
        print("    [%d점 %s] %s" % (r["star_rating"], r["_at"].date(), r["_text"][:70].replace("\n", " ")))

    print("\n[7] 종합")
    for key, value in m.items():
        print("  %-18s %s" % (key, value))
    print("\n  주작 지수: %d / 100" % score)
    for flag in flags:
        print("   - %s" % flag)
    if m.get("헤비유저평균별점") is not None:
        print("\n  보정 추정 평점(리뷰 10개 이상 작성자 기준): %.2f점" % m["헤비유저평균별점"])
    return m, score


def main():
    parser = argparse.ArgumentParser(description="카카오맵 리뷰 주작 감별기")
    parser.add_argument("place", help="장소 ID 또는 카카오맵 URL")
    parser.add_argument("-c", "--control", nargs="*", default=[],
                        help="대조군 장소 ID (같은 동네 동종 업장)")
    parser.add_argument("-o", "--out", help="수집 원본과 지표를 저장할 JSON 경로")
    args = parser.parse_args()

    pid = resolve_place_id(args.place)
    place = fetch_place(pid)
    name = ((place.get("summary") or {}).get("name")) or pid
    reviews = enrich(fetch_reviews(pid))
    if not reviews:
        raise SystemExit("리뷰를 가져오지 못했습니다.")
    target_metrics, score = report(name, reviews, place)

    control_rows = {}
    if args.control:
        print("\n" + "=" * 66)
        print("대조군 비교 (같은 동네 동종 업장)")
        print("=" * 66)
        header = "%-20s %6s %6s %7s %9s %11s" % ("업장", "표본", "평균", "5점%", "사진%", "1회성계정%")
        print(header)
        row = lambda nm, m: "%-20s %6d %6.2f %7.1f %9.1f %11.1f" % (
            nm[:20], m["표본"], m["평균별점"], m["5점비율"], m["사진첨부비율"], m["1회성계정비율"])
        print(row("▶ " + name, target_metrics))
        for cid in args.control:
            try:
                c_place = fetch_place(cid)
                c_name = ((c_place.get("summary") or {}).get("name")) or cid
                c_reviews = enrich(fetch_reviews(cid, max_pages=15))
                if not c_reviews:
                    continue
                c_metrics = metrics(c_reviews)
                control_rows[c_name] = c_metrics
                print(row(c_name, c_metrics))
            except Exception as exc:
                print("  %s 수집 실패: %s" % (cid, exc), file=sys.stderr)

    if args.out:
        with open(args.out, "w") as fp:
            json.dump({"place_id": pid, "name": name, "metrics": target_metrics,
                       "suspicion_score": score, "controls": control_rows,
                       "reviews": [{k: v for k, v in r.items() if not k.startswith("_")}
                                   for r in reviews]},
                      fp, ensure_ascii=False)
        print("\n저장: %s" % args.out)


if __name__ == "__main__":
    main()
