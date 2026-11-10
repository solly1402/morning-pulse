import logging
import re
import uuid
from collections import defaultdict
from typing import Any, Dict, List

import feedparser
import requests
from bs4 import BeautifulSoup

from src.models import NewsItem

logger = logging.getLogger(__name__)


def _get_reddit_headers() -> Dict[str, str]:
    uid = uuid.uuid4().hex[:8]
    return {
        "User-Agent": f"windows:morning-pulse-{uid}:v1.0.0 (by /u/dev_reader_{uid})",
        "Accept": "application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }


def _clean_html(raw_html: str, max_len: int = 220) -> str:
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"submitted by\s+/u/\S+.*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        return text[: max_len - 3].rstrip() + "..."
    return text


def _extract_external_url(raw_html: str, fallback_link: str) -> str:
    """Trích xuất link bài báo gốc trong nội dung RSS của Reddit nếu có."""
    if not raw_html:
        return fallback_link
    soup = BeautifulSoup(raw_html, "html.parser")
    for a_tag in soup.find_all("a", href=True):
        if "[link]" in a_tag.get_text(strip=True).lower():
            href = a_tag["href"].strip()
            if href.startswith("http"):
                return href
    return fallback_link


def fetch_reddit_posts(cfg: Dict[str, Any]) -> List[NewsItem]:
    """Lấy bài viết nổi bật từ danh sách Subreddit qua Multi-Reddit RSS (1 request duy nhất, tránh lỗi 429)."""
    if not cfg.get("enabled", True):
        return []

    limit_per_sub = int(cfg.get("limit_per_sub", 3))
    subreddits = [
        s.strip().lstrip("r/") for s in (cfg.get("subreddits") or ["programming", "technology"]) if s.strip()
    ]
    if not subreddits:
        return []

    combined_subs = "+".join(subreddits)
    total_fetch = max(25, len(subreddits) * (limit_per_sub + 4))
    url = f"https://www.reddit.com/r/{combined_subs}/hot/.rss?limit={total_fetch}"

    all_items: List[NewsItem] = []
    counts_per_sub: Dict[str, int] = defaultdict(int)

    try:
        resp = requests.get(url, headers=_get_reddit_headers(), timeout=15)
        if resp.status_code == 429:
            import time
            time.sleep(3)
            resp = requests.get(url, headers=_get_reddit_headers(), timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        for entry in feed.entries:
            title = entry.get("title", "").strip()
            reddit_link = entry.get("link", "").strip()
            if not title or not reddit_link:
                continue

            # Lấy tên Subreddit từ tag của Atom entry
            tags = entry.get("tags") or []
            sub_name = tags[0].get("term", "").strip() if tags else subreddits[0]
            sub_key = sub_name.lower()

            if counts_per_sub[sub_key] >= limit_per_sub:
                continue

            raw_summary = entry.get("summary", "")
            target_url = _extract_external_url(raw_summary, reddit_link)
            summary = _clean_html(raw_summary, max_len=200)

            category = (
                "football"
                if sub_key in {"soccer", "football", "premierleague", "championsleague"}
                else "reddit"
            )
            all_items.append(
                NewsItem(
                    title=title,
                    url=target_url,
                    source=f"r/{sub_name}",
                    category=category,
                    summary=summary or f"Chủ đề đang được thảo luận sôi nổi trên r/{sub_name}.",
                    comments_url=reddit_link,
                    extra_meta=f"r/{sub_name}",
                )
            )
            counts_per_sub[sub_key] += 1
    except Exception as exc:
        logger.warning("Không thể lấy dữ liệu từ Reddit (%s): %s", combined_subs, exc)

    logger.info("Đã lấy %d bài viết từ Reddit (%s).", len(all_items), ", ".join(f"r/{s}" for s in subreddits))
    return all_items
