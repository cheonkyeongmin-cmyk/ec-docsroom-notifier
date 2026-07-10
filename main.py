#!/usr/bin/env python3
"""
EUR-Lex EN 50566 RSS 모니터 (RSS Feed 기반)
- EUR-Lex RSS 피드 모니터링
- 새 항목 감지시 ntfy.sh로 알림 전송

설치: pip install --break-system-packages feedparser requests

실행: python main.py
"""

import json
import hashlib
import requests
import feedparser
from pathlib import Path
from datetime import datetime, timezone

# ===== 설정 =====
NTFY_TOPIC = "peter-ec-alert-x7k2"  # ntfy 구독 주제
RSS_FEED_URL = "https://eur-lex.europa.eu/EN/display-feed.rss?myRssId=zqe4qoJ391MwdPmm03ZXOjYp%2B8pcE%2BhONbqwNoeM%2FRI%3D"
CACHE_FILE = Path("cache.json")


def fetch_feed():
    """RSS 피드 가져오기"""
    try:
        print(f"📍 RSS 피드 읽는 중...")
        
        feed = feedparser.parse(RSS_FEED_URL)
        
        if feed.bozo:
            print(f"⚠️ 피드 경고: {feed.bozo_exception}")
        
        results = []
        
        for entry in feed.entries:
            try:
                title = entry.get("title", "")
                url = entry.get("link", "")
                
                # 발행 날짜
                pub_date = ""
                if "published" in entry:
                    pub_date = entry.published[:10]  # YYYY-MM-DD
                elif "updated" in entry:
                    pub_date = entry.updated[:10]
                
                # 요약
                summary = entry.get("summary", "")[:100]  # 처음 100자
                
                results.append({
                    "title": title,
                    "url": url,
                    "date": pub_date,
                    "summary": summary,
                })
            except Exception as e:
                print(f"  ⚠️ 항목 파싱 오류: {e}")
                continue
        
        return results
    
    except Exception as e:
        print(f"❌ RSS 피드 오류: {e}")
        return None


def load_cache():
    """캐시 로드"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None


def save_cache(results):
    """캐시 저장"""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"캐시 저장 오류: {e}")


def detect_changes(old_results, new_results):
    """변경사항 감지"""
    if not old_results:
        return True, f"첫 실행 - {len(new_results)}개 항목 발견"

    old_urls = {r["url"] for r in old_results}
    new_urls = {r["url"] for r in new_results}

    added = new_urls - old_urls
    removed = old_urls - new_urls

    if added or removed:
        msg_parts = []
        if added:
            msg_parts.append(f"➕ 새 항목 ({len(added)}개)")
        if removed:
            msg_parts.append(f"➖ 제거됨 ({len(removed)}개)")
        
        return True, " / ".join(msg_parts)

    return False, "변경 없음"


def send_notification(title, message):
    """ntfy.sh로 알림 전송"""
    try:
        requests.post(
            "https://ntfy.sh",
            json={
                "topic": NTFY_TOPIC,
                "title": title,
                "message": message,
                "priority": 4,
                "tags": ["eu", "standard", "rss"],
            },
            timeout=10,
        )
        print("✅ 알림 전송 완료")
    except Exception as e:
        print(f"❌ 알림 전송 실패: {e}")


def format_results(results):
    """결과 포매팅"""
    if not results:
        return "항목 없음"

    lines = []
    for i, item in enumerate(results[:10], 1):
        lines.append(f"{i}. {item['title']}")
        if item['date']:
            lines.append(f"   📅 {item['date']}")
        if item['summary']:
            lines.append(f"   📝 {item['summary']}")
        lines.append(f"   🔗 {item['url'][:100]}")
        lines.append("")

    return "\n".join(lines)


def main():
    print(f"⏰ [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] 시작\n")

    # RSS 피드 읽기
    new_results = fetch_feed()

    if new_results is None:
        print("❌ RSS 피드 읽기 실패")
        return

    print(f"✅ {len(new_results)}개 항목 획득\n")

    # 캐시와 비교
    old_results = load_cache()
    has_changes, change_msg = detect_changes(old_results, new_results)

    print(f"📋 {change_msg}\n")

    if has_changes:
        # 캐시 업데이트
        save_cache(new_results)

        # 알림 전송
        message = (
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"🔗 EUR-Lex EN 50566\n\n"
            f"📝 {change_msg}\n\n"
            f"📋 최신 항목 (상위 5개):\n{format_results(new_results[:5])}"
        )

        send_notification(f"🔔 EN 50566 업데이트", message)

        print("=" * 60)
        print(message)
        print("=" * 60)
    else:
        print("(알림 미전송)")


if __name__ == "__main__":
    main()
