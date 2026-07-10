#!/usr/bin/env python3
"""
EUR-Lex EN 50566 모니터링 스크립트 (간단 버전)
- 실제 사용은 수동으로 테스트하고 GitHub Actions에서 정기 실행

설치: pip install --break-system-packages requests

실행: python main.py
"""

import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timezone

# ===== 설정 =====
NTFY_TOPIC = "peter-ec-alert-x7k2"
CACHE_FILE = Path("cache.json")

# EUR-Lex 검색 결과 (수동으로 업데이트 필요 또는 실제 데이터 소스 지정)
# https://eur-lex.europa.eu/homepage.html?lang=en 에서 EN 50566 검색 후 URL 복사
SAMPLE_RESULTS = [
    {
        "title": "Directive 2014/53/EU of the European Parliament and of the Council",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014L0053",
        "date": "2014-05-22"
    },
    {
        "title": "Council Directive 93/42/EEC on medical devices",
        "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:31993L0042",
        "date": "1993-06-14"
    },
]


def fetch_results():
    """결과 가져오기"""
    print("📍 검색 중...")
    print("💡 주의: 이 스크립트는 샘플 데이터를 사용합니다.")
    print("실제 EUR-Lex 데이터를 모니터링하려면:")
    print("  1. https://eur-lex.europa.eu 방문")
    print("  2. EN 50566 검색")
    print("  3. 결과를 스크립트에 업데이트\n")
    
    return SAMPLE_RESULTS


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
        return True, "첫 실행"

    old_hash = hashlib.md5(json.dumps(old_results, sort_keys=True).encode()).hexdigest()
    new_hash = hashlib.md5(json.dumps(new_results, sort_keys=True).encode()).hexdigest()

    if old_hash != new_hash:
        old_titles = {r["title"] for r in old_results}
        new_titles = {r["title"] for r in new_results}

        added = new_titles - old_titles
        removed = old_titles - new_titles

        msg_parts = []
        if added:
            msg_parts.append(f"➕ 추가 ({len(added)}개): {', '.join(list(added)[:2])}")
        if removed:
            msg_parts.append(f"➖ 삭제 ({len(removed)}개): {', '.join(list(removed)[:2])}")

        return True, "\n".join(msg_parts) if msg_parts else "구조 변경"

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
                "tags": ["eu", "standard"],
            },
            timeout=10,
        )
        print("✅ 알림 전송 완료")
    except Exception as e:
        print(f"❌ 알림 전송 실패: {e}")


def format_results(results):
    """결과 포매팅"""
    if not results:
        return "결과 없음"

    lines = []
    for i, item in enumerate(results[:10], 1):
        lines.append(f"{i}. {item['title']}")
        lines.append(f"   📅 {item['date']}")
        lines.append(f"   🔗 {item['url']}")
        lines.append("")

    return "\n".join(lines)


def main():
    print(f"⏰ [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] 시작\n")

    # 결과 가져오기
    new_results = fetch_results()

    if not new_results:
        print("❌ 결과 없음")
        return

    print(f"✅ {len(new_results)}개 결과 획득\n")

    # 캐시와 비교
    old_results = load_cache()
    has_changes, change_msg = detect_changes(old_results, new_results)

    print(f"📋 {change_msg}\n")

    if has_changes:
        save_cache(new_results)

        message = (
            f"⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
            f"📝 {change_msg}\n\n"
            f"📋 결과 (상위 10개):\n{format_results(new_results)}"
        )

        send_notification(f"EN 50566 업데이트", message)

        print("=" * 50)
        print(message)
        print("=" * 50)
    else:
        print("(알림 미전송)")


if __name__ == "__main__":
    main()
