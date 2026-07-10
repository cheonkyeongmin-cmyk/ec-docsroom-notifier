#!/usr/bin/env python3
"""
EUR-Lex EN 50566 모니터링 스크립트
- EUR-Lex에서 EN 50566 검색
- 변경사항 감지시 ntfy.sh로 알림 전송

설치: pip install --break-system-packages requests beautifulsoup4 playwright
     python -m playwright install chromium

실행: python main.py
"""

import asyncio
import json
import hashlib
import requests
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# ===== 설정 =====
NTFY_TOPIC = "peter-ec-alert-x7k2"  # ntfy 구독 주제
SEARCH_QUERY = "EN 50566"  # 검색어
EUR_LEX_URL = "https://eur-lex.europa.eu/homepage.html?lang=en"
CACHE_FILE = Path("cache.json")


async def fetch_results():
    """EUR-Lex에서 검색 결과 가져오기"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            print(f"📍 페이지 로딩 중...")
            await page.goto(EUR_LEX_URL, wait_until="domcontentloaded", timeout=60000)
            
            # 페이지가 완전히 로드될 때까지 대기
            await page.wait_for_timeout(3000)

            # 검색 입력 필드 찾기 (다양한 선택자 시도)
            search_selectors = [
                'input[type="text"]',
                'input[id*="search"]',
                'input[placeholder*="search" i]',
                'input[name*="search"]',
                '#search-input',
                '.search-input input',
            ]
            
            search_input = None
            for selector in search_selectors:
                try:
                    search_input = await page.query_selector(selector)
                    if search_input:
                        print(f"✓ 검색 입력 필드 찾음: {selector}")
                        break
                except:
                    continue
            
            if not search_input:
                print("⚠️ 검색 입력 필드를 찾을 수 없음. 페이지 HTML 확인 중...")
                html = await page.content()
                if "search" in html.lower():
                    print("💡 'search' 관련 요소가 있지만 선택자를 찾지 못함")
                await browser.close()
                return None

            # 검색 입력
            print(f"🔍 검색: {SEARCH_QUERY}")
            await search_input.fill(SEARCH_QUERY)
            await page.wait_for_timeout(1000)

            # 검색 실행
            search_button = None
            button_selectors = [
                'button[type="submit"]',
                'button[id*="search"]',
                '.search-button',
                'button:has-text("Search")',
                'button:has-text("search")',
            ]
            
            for selector in button_selectors:
                try:
                    search_button = await page.query_selector(selector)
                    if search_button:
                        print(f"✓ 검색 버튼 찾음: {selector}")
                        break
                except:
                    continue
            
            if search_button:
                await search_button.click()
                await page.wait_for_load_state("networkidle", timeout=60000)
            else:
                # 버튼이 없으면 Enter 키로 검색
                print("💡 Enter 키로 검색 실행")
                await search_input.press("Enter")
                await page.wait_for_load_state("networkidle", timeout=60000)

            # 정렬 (있으면)
            sort_selectors = [
                'select[name*="sort"]',
                'select[id*="sort"]',
                'select[name*="order"]',
                '.sort-select',
            ]
            
            for selector in sort_selectors:
                try:
                    sort_select = await page.query_selector(selector)
                    if sort_select:
                        print(f"📊 날짜순 정렬 중...")
                        await sort_select.select_option("date")
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue

            content = await page.content()
            
            # 디버깅: 스크린샷 저장 (선택사항)
            try:
                await page.screenshot(path="debug_screenshot.png")
                print("📸 디버그 스크린샷 저장: debug_screenshot.png")
            except:
                pass
            
            await browser.close()

            # 결과 파싱
            soup = BeautifulSoup(content, "html.parser")
            results = []

            result_containers = (
                soup.find_all("div", class_="search-result")
                or soup.find_all("tr", class_="result")
                or soup.find_all("div", class_="result")
                or soup.find_all("article")
            )

            for container in result_containers:
                try:
                    title_link = container.find("a", class_="title") or container.find("a")
                    if not title_link:
                        continue

                    title = title_link.get_text(strip=True)
                    url = title_link.get("href", "")

                    if url and not url.startswith("http"):
                        url = "https://eur-lex.europa.eu" + (url if url.startswith("/") else "/" + url)

                    date_elem = (
                        container.find("span", class_="date")
                        or container.find("td", class_="date")
                        or container.find("time")
                    )
                    date_text = date_elem.get_text(strip=True) if date_elem else ""

                    results.append({"title": title, "url": url, "date": date_text})
                except:
                    continue

            results.sort(key=lambda x: x.get("date", ""), reverse=True)
            return results

    except Exception as e:
        print(f"❌ 오류: {e}")
        print("💡 해결 방법:")
        print("  1. EUR-Lex 웹사이트를 직접 방문해서 구조 확인")
        print("  2. 브라우저 검사도구로 검색 입력 필드의 id/name 확인")
        print("  3. main.py의 search_selectors 리스트에 해당 선택자 추가")
        print("  4. 디버그 스크린샷 확인: debug_screenshot.png")
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
        if item["url"]:
            lines.append(f"   🔗 {item['url']}")
        lines.append("")

    return "\n".join(lines)


async def main():
    print(f"⏰ [{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}] 시작\n")

    # 새 결과 가져오기
    new_results = await fetch_results()

    if new_results is None:
        print("❌ 검색 실패")
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
    asyncio.run(main())
