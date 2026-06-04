"""기존 DB의 토스 기사 url을 원문(linkUrl)으로 백필하는 1회성 마이그레이션.

토스 수집기는 한동안 기사 url을 토스 페이지(https://www.tossinvest.com/news/<id>)로
저장했다. 이 스크립트는 그런 항목을 골라 토스 상세 API에서 원문 url을 받아 **url 컬럼만**
교체한다. **id(중복 제거 키)는 토스 기준으로 그대로 둔다** — 재수집·기존 데이터와 호환.

저장소는 Storage가 .env로 자동 선택한다(TURSO_* 있으면 Turso, 없으면 로컬 sqlite).

실행:  .venv\\Scripts\\python.exe scripts\\backfill_toss_linkurl.py
"""
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.getcwd())  # 번들 스크립트에서 'src' 패키지 import 가능하게

import httpx

from src.storage import Storage
from src.collectors.woori import TOSS_NEWS_URL, fetch_link_url

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.tossinvest.com/",
    "Accept": "application/json",
}


def main() -> None:
    st = Storage()
    print("저장소:", "Turso(원격)" if st.is_remote else "로컬 sqlite")
    items = st.query(max_age_days=0)  # 전체
    toss = [it for it in items if (it.url or "").startswith(TOSS_NEWS_URL)]
    print(f"토스 기사 {len(toss)}건 / 전체 {len(items)}건")
    if not toss:
        print("백필할 항목 없음.")
        return

    updates: list[tuple] = []
    with httpx.Client(timeout=15) as client:
        def resolve(it):
            nid = (it.url or "").rsplit("/", 1)[-1]
            return it.id, fetch_link_url(client, nid, HEADERS)
        with ThreadPoolExecutor(max_workers=8) as ex:
            for rid, link in ex.map(resolve, toss):
                if link:
                    updates.append((link, rid))  # (새 url, id)

    print(f"원문 확보 {len(updates)}건 → url 업데이트")
    if updates:
        st.conn.executemany("UPDATE news_items SET url=? WHERE id=?", updates)
        st.conn.commit()
    skipped = len(toss) - len(updates)
    print(f"완료: 업데이트 {len(updates)}건, 원문 미확보(토스 url 유지) {skipped}건")


if __name__ == "__main__":
    main()
