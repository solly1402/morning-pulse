import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

import requests

from src.models import DigestSection, MorningDigest, NewsItem

logger = logging.getLogger(__name__)

SECTION_DEFINITIONS = [
    ("github", "GitHub Trending", "🚀", 0x2DBA4E),
    ("hackernews", "Hacker News", "🟧", 0xFF6600),
    ("reddit", "Cộng đồng Reddit", "👽", 0xFF4500),
    ("tech_news", "Báo Công Nghệ", "📰", 0x0088CC),
    ("football", "Bóng Đá Thế Giới", "⚽", 0x1DB954),
]

SECTION_SYSTEM_INSTRUCTION = """Bạn là "Morning Pulse", một Tổng biên tập điểm tin buổi sáng kỳ cựu, sắc sảo và am hiểu sâu sắc về Công nghệ (Lập trình, AI, Open Source) cũng như Bóng đá thế giới.

Nhiệm vụ của bạn là đọc danh sách các bài viết của một chuyên mục (kèm nội dung trích xuất từ bài gốc), sau đó dịch toàn bộ sang tiếng Việt và biên tập thành bản tóm tắt chuyên sâu, giàu thông tin.

YÊU CẦU BẮT BUỘC:
1. **Dịch tiêu đề sang tiếng Việt (`title_vi`)**:
   - Mọi tiêu đề tiếng Anh PHẢI được dịch sang tiếng Việt tự nhiên, chuẩn văn phong báo chí hiện đại.
   - Riêng mục `github` (GitHub Trending), giữ nguyên tên repo ở đầu và nối thêm mô tả ngắn tiếng Việt: ví dụ `"owner / repo — Công cụ tự động hóa..."`.
2. **Tóm tắt chuyên sâu, dài và đầy đủ ý chính (`summary_vi`)**:
   - KHÔNG tóm tắt ngắn gọn 1 câu.
   - Mỗi bài viết phải được tóm tắt thành một đoạn văn **dài từ 3 đến 5 câu (khoảng 70 - 120 từ)** bằng tiếng Việt.
   - Nội dung tóm tắt phải bao quát sâu vào bài viết:
     + Chuyện gì đang xảy ra / Công cụ hoặc dự án này giải quyết bài toán gì?
     + Các chi tiết kỹ thuật, số liệu, tính năng nổi bật, diễn biến trận đấu hoặc phát ngôn quan trọng trong bài.
     + Ý nghĩa thực tế hoặc lý do vì sao cộng đồng đang quan tâm đến tin tức này.

Trả về một JSON hợp lệ theo đúng cấu trúc sau:
{
  "commentary": "2-3 câu nhận xét tổng quan, sắc sảo bằng tiếng Việt về xu hướng nổi bật của chuyên mục này hôm nay.",
  "items": [
    {
      "title_vi": "Tiêu đề đã dịch sang tiếng Việt",
      "summary_vi": "Đoạn tóm tắt chuyên sâu 3-5 câu bằng tiếng Việt bao quát đầy đủ các ý chính của bài viết."
    }
  ]
}"""


def _call_gemini_json(
    api_key: str,
    models: List[str],
    temperature: float,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    last_exc: Exception | None = None

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        for attempt in range(2):
            try:
                resp = requests.post(url, json=body, timeout=60)
                if resp.status_code == 503 and attempt == 0:
                    time.sleep(2.0)
                    continue
                resp.raise_for_status()
                candidates = resp.json().get("candidates", [])
                parts = candidates[0]["content"]["parts"]
                text = ""
                for p in parts:
                    if "text" in p and p["text"].strip():
                        text = p["text"].strip()
                return json.loads(text)
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(1.5)
        logger.warning("Model %s bận (%s), chuyển sang model dự phòng...", model, last_exc)

    if last_exc:
        raise last_exc
    raise RuntimeError("Không có model Gemini nào khả dụng.")


def _summarize_section_gemini(
    sec: DigestSection,
    api_key: str,
    models: List[str],
    temperature: float,
) -> None:
    payload = [
        {
            "index": idx,
            "title": item.title,
            "source": item.source,
            "raw_content": item.summary[:900],
            "score": item.score or "",
        }
        for idx, item in enumerate(sec.items)
    ]
    user_prompt = (
        f"Chuyên mục: {sec.title} (key: {sec.key})\n"
        "Hãy dịch toàn bộ tiêu đề sang tiếng Việt (`title_vi`) và viết bản tóm tắt chuyên sâu 3-5 câu (`summary_vi`) "
        "cho từng mục theo đúng thứ tự index:\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    res = _call_gemini_json(
        api_key=api_key,
        models=models,
        temperature=temperature,
        system_prompt=SECTION_SYSTEM_INSTRUCTION,
        user_prompt=user_prompt,
    )
    sec.ai_commentary = str(res.get("commentary", "")).strip()
    ai_items = res.get("items") or []
    for idx, item in enumerate(sec.items):
        if idx < len(ai_items) and isinstance(ai_items[idx], dict):
            entry = ai_items[idx]
            title_vi = str(entry.get("title_vi", "")).strip()
            summary_vi = str(entry.get("summary_vi", "")).strip()
            if title_vi:
                item.title = title_vi
            if summary_vi:
                item.summary = summary_vi


def build_morning_digest(
    raw_items: List[NewsItem], cfg: Dict[str, Any], date_obj: datetime | None = None
) -> MorningDigest:
    """Phân nhóm tin tức, dịch sang tiếng Việt và tóm tắt chuyên sâu từng chuyên mục bằng AI."""
    now = date_obj or datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    display_date = now.strftime("%d/%m/%Y")

    sections: List[DigestSection] = []
    for key, title, emoji, color in SECTION_DEFINITIONS:
        cat_items = [item for item in raw_items if item.category == key]
        if cat_items:
            sections.append(
                DigestSection(
                    key=key,
                    title=title,
                    emoji=emoji,
                    color=color,
                    items=cat_items,
                )
            )

    greeting = f"Chào buổi sáng! Đây là bản tin tổng hợp & phân tích chuyên sâu ngày **{display_date}** dành riêng cho bạn ☕"
    default_overview = (
        f"Tổng hợp **{len(raw_items)} tin tức & xu hướng** nổi bật nhất sáng nay từ "
        "GitHub Trending, Hacker News, Reddit, Báo Công Nghệ và Bóng Đá Thế Giới."
    )

    ai_cfg = cfg.get("ai", {})
    secrets = cfg.get("secrets", {})
    ai_enabled = ai_cfg.get("enabled", True)
    provider = ai_cfg.get("provider", "gemini").lower()
    temperature = float(ai_cfg.get("temperature", 0.35))

    overview_lines: List[str] = []
    if ai_enabled and sections and provider == "gemini" and secrets.get("gemini_api_key"):
        primary = ai_cfg.get("gemini_model", "gemini-3-flash-preview")
        fallbacks = ai_cfg.get(
            "gemini_fallback_models",
            ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.1-flash-lite-preview"],
        )
        models = [primary] + [m for m in fallbacks if m != primary]

        for sec in sections:
            try:
                logger.info("🧠 Đang dịch & tóm tắt chuyên sâu mục [%s %s] bằng Gemini 3...", sec.emoji, sec.title)
                _summarize_section_gemini(
                    sec=sec,
                    api_key=secrets["gemini_api_key"],
                    models=models,
                    temperature=temperature,
                )
                if sec.ai_commentary:
                    overview_lines.append(f"- **{sec.emoji} {sec.title}:** {sec.ai_commentary}")
                time.sleep(1.0)
            except Exception as exc:
                logger.warning("Không thể tóm tắt mục %s bằng AI: %s", sec.title, exc)

    overview = "\n".join(overview_lines) if overview_lines else default_overview

    return MorningDigest(
        date_str=date_str,
        greeting=greeting,
        ai_overview=overview,
        sections=sections,
    )
