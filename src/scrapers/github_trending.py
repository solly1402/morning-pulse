import logging
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from src.models import NewsItem

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_github_trending(cfg: Dict[str, Any]) -> List[NewsItem]:
    """Cào danh sách các repository đang thịnh hành trên GitHub Trending."""
    if not cfg.get("enabled", True):
        return []

    since = cfg.get("since", "daily")
    spoken_lang = cfg.get("spoken_language", "")
    limit = int(cfg.get("limit", 6))
    prog_langs = cfg.get("programming_languages") or [""]

    items: List[NewsItem] = []
    seen_urls = set()

    for lang in prog_langs:
        lang_path = f"/{lang.strip()}" if lang and lang.strip() else ""
        url = f"https://github.com/trending{lang_path}?since={since}"
        if spoken_lang:
            url += f"&spoken_language_code={spoken_lang}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            for row in soup.select("article.Box-row"):
                h2 = row.select_one("h2 a")
                if not h2:
                    continue

                repo_rel = h2.get("href", "").strip("/")
                if not repo_rel:
                    continue

                repo_url = f"https://github.com/{repo_rel}"
                if repo_url in seen_urls:
                    continue
                seen_urls.add(repo_url)

                desc_el = row.select_one("p")
                description = desc_el.get_text(strip=True) if desc_el else "Không có mô tả."

                lang_el = row.select_one('[itemprop="programmingLanguage"]')
                repo_lang = lang_el.get_text(strip=True) if lang_el else "Unknown"

                # Lấy tổng số star
                star_link = row.select_one('a[href$="/stargazers"]')
                total_stars = star_link.get_text(strip=True) if star_link else "0"

                # Lấy số star tăng trong ngày
                today_el = row.select_one("span.d-inline-block.float-sm-right")
                stars_today = today_el.get_text(strip=True) if today_el else ""

                score_parts = [f"⭐ {total_stars}"]
                if stars_today:
                    score_parts.append(f"📈 {stars_today}")

                items.append(
                    NewsItem(
                        title=repo_rel.replace("/", " / "),
                        url=repo_url,
                        source="GitHub Trending",
                        category="github",
                        summary=description,
                        score=" • ".join(score_parts),
                        extra_meta=repo_lang,
                    )
                )

                if len(items) >= limit:
                    break
        except Exception as exc:
            logger.warning("Lỗi khi lấy GitHub Trending (%s): %s", url, exc)

        if len(items) >= limit:
            break

    logger.info("Đã lấy %d repo từ GitHub Trending.", len(items))
    return items[:limit]
