import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import requests
from bs4 import BeautifulSoup

from src.models import NewsItem

logger = logging.getLogger(__name__)

READER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}


def _extract_article_snippet(url: str, max_chars: int = 1200) -> str:
    """Truy cập vào trang bài báo hoặc GitHub repo để trích xuất nội dung chi tiết phục vụ tóm tắt sâu."""
    if not url or not url.startswith("http"):
        return ""
    if any(ext in url.lower() for ext in (".pdf", ".jpg", ".png", ".gif", ".mp4", "youtube.com", "youtu.be")):
        return ""

    try:
        resp = requests.get(url, headers=READER_HEADERS, timeout=7, allow_redirects=True)
        if resp.status_code != 200:
            return ""
        content_type = resp.headers.get("Content-Type", "").lower()
        if "html" not in content_type and "xml" not in content_type:
            return ""

        soup = BeautifulSoup(resp.text[:150_000], "html.parser")

        # Xóa các thẻ script, style, nav, footer, header gây nhiễu
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        parts: List[str] = []

        # 1. Lấy meta description / og:description nếu có
        meta_desc = (
            soup.find("meta", attrs={"property": "og:description"})
            or soup.find("meta", attrs={"name": "description"})
        )
        if meta_desc and meta_desc.get("content"):
            desc_text = re.sub(r"\s+", " ", meta_desc["content"]).strip()
            if len(desc_text) > 30:
                parts.append(desc_text)

        # 2. Nếu là trang GitHub repo, lấy phần README markdown-body
        if "github.com/" in url:
            readme_el = soup.select_one("article.markdown-body")
            if readme_el:
                paragraphs = [
                    re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
                    for p in readme_el.find_all(["p", "li"], limit=12)
                ]
                valid_p = [p for p in paragraphs if len(p) > 40]
                parts.extend(valid_p[:6])
        else:
            # 3. Trang báo / blog thông thường: lấy các đoạn văn <p> trong <article> hoặc <main>
            container = soup.find("article") or soup.find("main") or soup.body
            if container:
                paragraphs = [
                    re.sub(r"\s+", " ", p.get_text(" ", strip=True)).strip()
                    for p in container.find_all("p", limit=15)
                ]
                valid_p = [p for p in paragraphs if len(p) > 50]
                parts.extend(valid_p[:6])

        combined = " ".join(parts)
        combined = re.sub(r"\s+", " ", combined).strip()
        if len(combined) > max_chars:
            return combined[: max_chars - 3].rstrip() + "..."
        return combined
    except Exception:
        return ""


def enrich_items_with_article_content(items: List[NewsItem], max_workers: int = 10) -> None:
    """Đọc song song nội dung chi tiết của các bài viết để AI có đủ dữ liệu tóm tắt sâu."""
    logger.info("📖 Đang đọc sâu nội dung chi tiết của %d bài viết...", len(items))

    def _process(item: NewsItem) -> None:
        snippet = _extract_article_snippet(item.url, max_chars=1200)
        if snippet:
            if item.summary and item.summary not in snippet:
                item.summary = f"{item.summary} | Nội dung bài viết: {snippet}"
            else:
                item.summary = snippet

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process, it) for it in items]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception:
                pass
