import logging
from typing import Any, Dict, List

import requests

from src.models import NewsItem

logger = logging.getLogger(__name__)


def fetch_hacker_news(cfg: Dict[str, Any]) -> List[NewsItem]:
    """Lấy các bài viết trang nhất từ Hacker News thông qua Algolia API."""
    if not cfg.get("enabled", True):
        return []

    limit = int(cfg.get("limit", 6))
    url = f"https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit + 4}"

    items: List[NewsItem] = []
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for hit in data.get("hits", []):
            title = hit.get("title")
            object_id = hit.get("objectID")
            if not title or not object_id:
                continue

            hn_link = f"https://news.ycombinator.com/item?id={object_id}"
            article_url = hit.get("url") or hn_link
            points = hit.get("points", 0)
            num_comments = hit.get("num_comments", 0)

            items.append(
                NewsItem(
                    title=title,
                    url=article_url,
                    source="Hacker News",
                    category="hackernews",
                    summary=f"Thảo luận sôi nổi trên Hacker News ({num_comments} bình luận).",
                    score=f"🔥 {points} pts • 💬 {num_comments}",
                    comments_url=hn_link,
                )
            )
            if len(items) >= limit:
                break
    except Exception as exc:
        logger.warning("Lỗi khi lấy dữ liệu Hacker News: %s", exc)

    logger.info("Đã lấy %d bài viết từ Hacker News.", len(items))
    return items
