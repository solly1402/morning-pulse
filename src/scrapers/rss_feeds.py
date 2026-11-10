import logging
import re
from typing import Any, Dict, List

import feedparser
import requests
from bs4 import BeautifulSoup

from src.models import NewsItem

logger = logging.getLogger(__name__)

RSS_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

FOOTBALL_KEYWORDS = [
    "bóng đá",
    "hlv",
    "ngoại hạng anh",
    "premier league",
    "champions league",
    "la liga",
    "serie a",
    "bundesliga",
    "world cup",
    "euro",
    "cầu thủ",
    "bàn thắng",
    "chuyển nhượng",
    "man utd",
    "man city",
    "arsenal",
    "liverpool",
    "chelsea",
    "real madrid",
    "barca",
    "barcelona",
    "psg",
    "bayern",
    "messi",
    "ronaldo",
    "mbappe",
    "haaland",
    "tuyển việt nam",
    "v-league",
]


def _clean_summary(raw_html: str, max_len: int = 220) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text


def fetch_rss_category(cfg: Dict[str, Any], category: str, filter_football: bool = False) -> List[NewsItem]:
    """Đọc danh sách RSS feeds cho một chuyên mục (tech_news hoặc football)."""
    if not cfg.get("enabled", True):
        return []

    limit_per_feed = int(cfg.get("limit_per_feed", 3))
    feeds = cfg.get("feeds") or []
    items: List[NewsItem] = []

    for feed_info in feeds:
        name = feed_info.get("name", "RSS Feed")
        url = feed_info.get("url", "").strip()
        if not url:
            continue

        try:
            resp = requests.get(url, headers=RSS_HEADERS, timeout=15)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)

            count = 0
            for entry in parsed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                raw_desc = entry.get("summary") or entry.get("description") or ""
                summary = _clean_summary(raw_desc)

                # Nếu là nguồn thể thao tổng hợp (như VnExpress Thể Thao), ưu tiên lọc tin bóng đá
                if filter_football and "vnexpress" in url.lower():
                    combined_text = f"{title} {summary}".lower()
                    if not any(kw in combined_text for kw in FOOTBALL_KEYWORDS):
                        continue

                items.append(
                    NewsItem(
                        title=title,
                        url=link,
                        source=name,
                        category=category,
                        summary=summary or f"Tin mới từ {name}.",
                        extra_meta=name,
                    )
                )
                count += 1
                if count >= limit_per_feed:
                    break
        except Exception as exc:
            logger.warning("Lỗi khi đọc RSS %s (%s): %s", name, url, exc)

    logger.info("Đã lấy %d tin cho chuyên mục '%s'.", len(items), category)
    return items
