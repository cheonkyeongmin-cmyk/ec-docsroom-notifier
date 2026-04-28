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
        if last_update_ms else "unknown"
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
            f"- {item['filename']}\n  {item['url']}"
            for item in info["excel_links"]
        )
    else:
        link_lines = "No Excel links found"

    message = (
        f"Last updated: {info['last_update']}\n\n"
        f"Download:\n{link_lines}"
    )

    requests.post(
        "https://ntfy.sh",
        json={
            "topic": NTFY_TOPIC,
            "title": "EC Docsroom Update Check",
            "message": message,
            "priority": 3,
            "tags": ["eu", "document"],
        },
    )
    print("Notification sent")
    print(message)


if __name__ == "__main__":
    data = fetch_docsroom()
    info = parse_info(data)
    send_notification(info)
