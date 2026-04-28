import requests
from datetime import datetime, timezone

DOCSROOM_URL = "https://ec.europa.eu/docsroom/documents/59955"
NTFY_TOPIC   = "peter-ec-alert-x7k2"


def fetch_docsroom():
    res = requests.get(DOCSROOM_URL, headers={"Accept": "application/json"}, allow_redirects=True)
    res.raise_for_status()
    return res.json()


def parse_info(data: dict) -> dict:
    last_update_ms = data.get("lastUpdateDate")
    last_update = (
        datetime.fromtimestamp(last_update_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if last_update_ms else "알 수 없음"
    )

    excel_links = []
    for att in data.get("attachments", []):
        for link in att.get("links", []):
            if link.get("rel") == "native":
                excel_links.append({
                    "filename": att.get("fileName", ""),
                    "url": link["href"],
                })

    return {
        "title": data.get("title", ""),
        "last_update": last_update,
        "excel_links": excel_links,
    }


def send_notification(info: dict):
    if info["excel_links"]:
        link_lines = "\n".join(
            f"• {item['filename']}\n  {item['url']}"
            for item in info["excel_links"]
        )
    else:
        link_lines = "Excel 링크 없음"

    message = (
        f"📅 마지막 업데이트: {info['last_update']}\n\n"
        f"📥 다운로드 링크:\n{link_lines}"
    )

    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "🇪🇺 EC Docsroom 업데이트 확인",
            "Priority": "default",
            "Tags": "eu,document,radio",
        },
    )
    print("알림 전송 완료")
    print(message)


if __name__ == "__main__":
    data = fetch_docsroom()
    info = parse_info(data)
    send_notification(info)
