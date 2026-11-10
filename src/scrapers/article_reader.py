import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
from urllib.parse import urljoin

import feedparser
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


def _extract_article_snippet_and_image(url: str, max_chars: int = 1100) -> Tuple[str, str]:
    """Truy cập vào trang bài báo hoặc GitHub repo để trích xuất nội dung chi tiết + ảnh bìa (og:image)."""
    if not url or not url.startswith("http"):
        return "", ""
    if any(ext in url.lower() for ext in (".pdf", ".mp4", "youtube.com", "youtu.be")):
        return "", ""
    if any(ext in url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
        return "", url

    try:
        resp = requests.get(url, headers=READER_HEADERS, timeout=7, allow_redirects=True)
        if resp.status_code != 200:
            return "", ""
        content_type = resp.headers.get("Content-Type", "").lower()
        if "html" not in content_type and "xml" not in content_type:
            return "", ""

        soup = BeautifulSoup(resp.text[:150_000], "html.parser")

        # 1. Trích xuất ảnh minh họa (og:image hoặc twitter:image)
        image_url = ""
        og_img = (
            soup.find("meta", attrs={"property": "og:image"})
            or soup.find("meta", attrs={"name": "twitter:image"})
            or soup.find("meta", attrs={"property": "twitter:image"})
        )
        if og_img and og_img.get("content"):
            raw_img = og_img["content"].strip()
            if raw_img.startswith("//"):
                image_url = "https:" + raw_img
            elif raw_img.startswith("/"):
                image_url = urljoin(url, raw_img)
            elif raw_img.startswith("http"):
                image_url = raw_img

        # Xóa các thẻ gây nhiễu trước khi lấy văn bản
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        parts: List[str] = []

        # 2. Lấy meta description
        meta_desc = (
            soup.find("meta", attrs={"property": "og:description"})
            or soup.find("meta", attrs={"name": "description"})
        )
        if meta_desc and meta_desc.get("content"):
            desc_text = re.sub(r"\s+", " ", meta_desc["content"]).strip()
            if len(desc_text) > 30:
                parts.append(desc_text)

        # 3. Lấy đoạn văn nội dung bài viết
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
            combined = combined[: max_chars - 3].rstrip() + "..."
        return combined, image_url
    except Exception:
        return "", ""


def _fetch_hn_top_comments(comments_url: str, max_comments: int = 3) -> str:
    """Lấy các bình luận nhiều tương tác nhất trên Hacker News để phục vụ Góc Hóng Biến Comment."""
    if not comments_url or "id=" not in comments_url:
        return ""
    item_id = comments_url.split("id=")[-1].strip()
    try:
        resp = requests.get(f"https://hn.algolia.com/api/v1/items/{item_id}", timeout=6)
        if resp.status_code != 200:
            return ""
        children = resp.json().get("children") or []
        comments: List[str] = []
        for child in children[:6]:
            raw_text = child.get("text") or ""
            if not raw_text:
                continue
            clean_c = BeautifulSoup(raw_text, "html.parser").get_text(" ", strip=True)
            clean_c = re.sub(r"\s+", " ", clean_c).strip()
            if len(clean_c) > 40:
                comments.append(clean_c[:220])
            if len(comments) >= max_comments:
                break
        return " // ".join(comments)
    except Exception:
        return ""


def _fetch_reddit_top_comments(comments_url: str, max_comments: int = 3) -> str:
    """Lấy bình luận nổi bật từ bài thảo luận Reddit qua RSS."""
    if not comments_url or "reddit.com" not in comments_url:
        return ""
    rss_url = comments_url.rstrip("/") + "/.rss?limit=6"
    try:
        resp = requests.get(
            rss_url,
            headers={"User-Agent": "windows:morning-pulse-reader:v1.0.2 (by /u/dev_reader)"},
            timeout=6,
        )
        if resp.status_code != 200:
            return ""
        feed = feedparser.parse(resp.content)
        comments: List[str] = []
        # Entry đầu tiên là bài gốc, các entry tiếp theo là comment
        for entry in feed.entries[1 : max_comments + 2]:
            raw = entry.get("summary") or ""
            clean_c = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
            clean_c = re.sub(r"\s+", " ", clean_c).strip()
            if len(clean_c) > 35:
                comments.append(clean_c[:220])
            if len(comments) >= max_comments:
                break
        return " // ".join(comments)
    except Exception:
        return ""


def enrich_items_with_article_content(items: List[NewsItem], max_workers: int = 10) -> None:
    """Đọc song song nội dung bài viết + ảnh bìa og:image + bình luận cộng đồng (HN/Reddit)."""
    logger.info("📖 Đang đọc sâu bài viết, lấy ảnh minh họa & bình luận cộng đồng (%d tin)...", len(items))

    def _process(item: NewsItem) -> None:
        snippet, img_url = _extract_article_snippet_and_image(item.url, max_chars=1000)
        if img_url:
            item.image_url = img_url

        if snippet:
            if item.summary and item.summary not in snippet:
                item.summary = f"{item.summary} | Nội dung bài viết: {snippet}"
            else:
                item.summary = snippet

        # Lấy thêm bình luận nổi bật của cộng đồng quốc tế
        comm_text = ""
        if item.category == "hackernews" and item.comments_url:
            comm_text = _fetch_hn_top_comments(item.comments_url)
        elif item.comments_url and "reddit.com" in item.comments_url:
            comm_text = _fetch_reddit_top_comments(item.comments_url)

        if comm_text:
            item.summary = f"{item.summary} | Bình luận nổi bật của cộng đồng: {comm_text}"

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_process, it) for it in items]
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception:
                pass
