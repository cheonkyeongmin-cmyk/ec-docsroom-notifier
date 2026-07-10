#!/usr/bin/env python3
"""
EUR-Lex EN 50566 RSS 모니터 (파일 기반 비교)
- RSS 피드를 파일로 저장하고 이전 버전과 비교
- 변경사항만 알림으로 전송

설치: pip install --break-system-packages feedparser requests

실행: python main.py
"""

import json
import requests
import feedparser
from pathlib import Path
from datetime import datetime, timezone

# ===== 설정 =====
NTFY_TOPIC = "peter-ec-alert-x7k2"  # ntfy 구독 주제
RSS_FEED_URL = "https://eur-lex.europa.eu/EN/display-feed.rss?myRssId=zqe4qoJ391MwdPmm03ZXOjYp%2B8pcE%2BhONbqwNoeM%2FRI%3D"
FEED_FILE = Path("feed.json")  # 현재 RSS 항목 저장
PREVIOUS_FILE = Path("feed_previous.json")  # 이전 RSS 항목 (비교용)


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


def load_previous_feed():
    """이전 RSS 항목 로드 (비교용)"""
    if PREVIOUS_FILE.exists():
        try:
            with open(PREVIOUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None


def save_current_feed(results):
    """현재 RSS 항목을 파일에 저장"""
    try:
        with open(FEED_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ feed.json 저장 오류: {e}")


def backup_to_previous():
    """현재 파일을 이전 버전으로 백업"""
    try:
        if FEED_FILE.exists():
            with open(FEED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            with open(PREVIOUS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ 백업 오류: {e}")


def detect_changes(previous_results, current_results):
    """변경사항 감지"""
    if not previous_results:
        return True, f"첫 실행", [], [], current_results

    # URL 기준으로 비교
    previous_urls = {r["url"]: r for r in previous_results}
    current_urls = {r["url"]: r for r in current_results}

    # 새로 추가된 항목
    added = []
    for url, item in current_urls.items():
        if url not in previous_urls:
            added.append(item)

    # 제거된 항목
    removed = []
    for url, item in previous_urls.items():
        if url not in current_urls:
            removed.append(item)

    # 변경된 항목 (제목, 날짜, 요약이 바뀐 경우)
    updated = []
    for url, current_item in current_urls.items():
        if url in previous_urls:
            previous_item = previous_urls[url]
            if (current_item["title"] != previous_item["title"] or
                current_item["date"] != previous_item["date"] or
                current_item["summary"] != previous_item["summary"]):
                updated.append(current_item)

    # 변경사항 메시지
    changes = []
    if added:
        changes.append(f"➕ 새 항목 ({len(added)}개)")
    if removed:
        changes.append(f"➖ 제거됨 ({len(removed)}개)")
    if updated:
        changes.append(f"✏️ 변경됨 ({len(updated)}개)")

    change_msg = " / ".join(changes) if changes else "변경 없음"
    has_changes = bool(changes)

    return has_changes, change_msg, added, removed, updated


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


def format_items(items, title):
    """항목 포매팅"""
    if not items:
        return ""
    
    lines = [f"\n{title}:"]
    for i, item in enumerate(items[:5], 1):  # 상위 5개만
        lines.append(f"{i}. {item['title']}")
        if item['date']:
            lines.append(f"   📅 {item['date']}")
        if item['summary']:
            lines.append(f"   📝 {item['summary']}")
        lines.append(f"   🔗 {item['url'][:80]}")
        lines.append("")
    
    return "\n".join(lines)


def main():
    print(f"⏰ [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] 시작\n")

    # RSS 피드 읽기
    current_results = fetch_feed()

    if current_results is None:
        print("❌ RSS 피드 읽기 실패")
        return

    print(f"✅ {len(current_results)}개 항목 획득\n")

    # 이전 버전 로드 및 비교
    previous_results = load_previous_feed()
    has_changes, change_msg, added, removed, updated = detect_changes(previous_results, current_results)

    if has_changes:
        print(f"📋 {change_msg}\n")

        # 알림 전송
        message = (
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"🔗 EUR-Lex EN 50566\n\n"
            f"📝 {change_msg}\n"
            f"{format_items(added, '➕ 새 항목')}"
            f"{format_items(removed, '➖ 제거됨')}"
            f"{format_items(updated, '✏️ 변경됨')}"
        )

        send_notification(f"🔔 EN 50566 업데이트", message)

        print("=" * 60)
        print(message)
        print("=" * 60)
    else:
        print(f"✅ No update")

    # 현재 결과를 파일에 저장 (다음 실행을 위한 비교용)
    print(f"\n💾 결과 저장 중...")
    backup_to_previous()  # 이전 파일 백업
    save_current_feed(current_results)  # 현재 결과 저장
    print(f"✓ feed.json 업데이트 완료")


if __name__ == "__main__":
    main()
