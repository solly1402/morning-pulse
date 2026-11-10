import json
import logging
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


def _build_prompt_payload(sections: List[DigestSection]) -> str:
    data = {}
    for sec in sections:
        data[sec.key] = [
            {
                "index": idx,
                "title": item.title,
                "source": item.source,
                "summary": item.summary,
                "score": item.score or "",
            }
            for idx, item in enumerate(sec.items)
        ]
    return json.dumps(data, ensure_ascii=False, indent=2)


SYSTEM_INSTRUCTION = """Bạn là "Morning Pulse", một biên tập viên điểm tin buổi sáng thông minh, sắc sảo và hài hước dành cho lập trình viên yêu công nghệ và bóng đá.
Nhiệm vụ của bạn là đọc dữ liệu tin tức thô (JSON) từ các nguồn GitHub Trending, Hacker News, Reddit, Báo Công Nghệ và Bóng Đá Thế Giới, sau đó trả về một JSON duy nhất (không bọc trong markdown code block nếu không cần thiết) theo đúng cấu trúc sau:
{
  "ai_overview": "Đoạn điểm tin tổng quan ngắn gọn (3-4 gạch đầu dòng súc tích bằng tiếng Việt) nêu bật những sự kiện đáng chú ý nhất sáng nay về cả Công nghệ và Bóng đá.",
  "sections": {
    "github": {
      "commentary": "1-2 câu nhận xét xu hướng các repo đang hot hôm nay.",
      "items": ["Tóm tắt tiếng Việt ngắn gọn (1 câu) cho từng repo theo đúng thứ tự index"]
    },
    "hackernews": {
      "commentary": "1-2 câu nhận xét chủ đề đang được bàn tán sôi nổi trên HN.",
      "items": ["Dịch/tóm tắt tiếng Việt ngắn gọn (1 câu) cho từng bài theo đúng thứ tự index"]
    },
    "reddit": {
      "commentary": "1-2 câu tóm tắt không khí thảo luận trên Reddit.",
      "items": ["Tóm tắt tiếng Việt ngắn gọn (1 câu) cho từng bài theo đúng thứ tự index"]
    },
    "tech_news": {
      "commentary": "1-2 câu điểm nhấn tin tức công nghệ hôm nay.",
      "items": ["Tóm tắt tiếng Việt ngắn gọn (1 câu) cho từng bài theo đúng thứ tự index"]
    },
    "football": {
      "commentary": "1-2 câu bình luận sôi động về kết quả/tin tức bóng đá thế giới đêm qua.",
      "items": ["Tóm tắt tiếng Việt ngắn gọn (1 câu) cho từng tin theo đúng thứ tự index"]
    }
  }
}
Lưu ý: Luôn trả lời bằng tiếng Việt tự nhiên, giữ nguyên tên riêng, tên repo hoặc thuật ngữ chuyên ngành khi cần."""


def _call_gemini_with_fallback(
    api_key: str,
    primary_model: str,
    fallback_models: List[str],
    temperature: float,
    payload_str: str,
) -> Dict[str, Any]:
    models_to_try = [primary_model] + [m for m in fallback_models if m != primary_model]
    last_exc: Exception | None = None

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        body = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": f"Dưới đây là dữ liệu tin tức sáng nay, hãy phân tích và trả về JSON:\n{payload_str}"
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
            },
        }
        try:
            logger.info("Đang tóm tắt bản tin bằng model Google Gemini: %s...", model)
            resp = requests.post(url, json=body, timeout=60)
            resp.raise_for_status()
            candidates = resp.json().get("candidates", [])
            text = candidates[0]["content"]["parts"][0]["text"]
            logger.info("✅ Tóm tắt thành công với model: %s", model)
            return json.loads(text)
        except Exception as exc:
            logger.warning("Model %s không khả dụng hoặc hết hạn mức (%s), thử model tiếp theo...", model, exc)
            last_exc = exc

    if last_exc:
        raise last_exc
    raise RuntimeError("Không có model Gemini nào khả dụng.")


def _call_openai(
    api_key: str, base_url: str, model: str, temperature: float, payload_str: str
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {
                "role": "user",
                "content": f"Dưới đây là dữ liệu tin tức sáng nay, hãy phân tích và trả về JSON:\n{payload_str}",
            },
        ],
    }
    resp = requests.post(url, headers=headers, json=body, timeout=45)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def build_morning_digest(
    raw_items: List[NewsItem], cfg: Dict[str, Any], date_obj: datetime | None = None
) -> MorningDigest:
    """Phân nhóm tin tức và tóm tắt bằng AI (hoặc fallback nếu chưa cấu hình API key)."""
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

    greeting = f"Chào buổi sáng! Đây là bản tin tổng hợp ngày **{display_date}** dành riêng cho bạn ☕"
    default_overview = (
        f"Tổng hợp nhanh **{len(raw_items)} tin tức & xu hướng** nổi bật nhất sáng nay từ "
        "GitHub Trending, Hacker News, Reddit, Báo Công Nghệ và Bóng Đá Thế Giới."
    )

    ai_cfg = cfg.get("ai", {})
    secrets = cfg.get("secrets", {})
    ai_enabled = ai_cfg.get("enabled", True)
    provider = ai_cfg.get("provider", "gemini").lower()
    temperature = float(ai_cfg.get("temperature", 0.4))

    ai_result: Dict[str, Any] | None = None
    if ai_enabled and sections:
        payload_str = _build_prompt_payload(sections)
        try:
            if provider == "gemini" and secrets.get("gemini_api_key"):
                fallback_models = ai_cfg.get(
                    "gemini_fallback_models",
                    ["gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash"],
                )
                ai_result = _call_gemini_with_fallback(
                    api_key=secrets["gemini_api_key"],
                    primary_model=ai_cfg.get("gemini_model", "gemini-3.1-pro-preview"),
                    fallback_models=fallback_models,
                    temperature=temperature,
                    payload_str=payload_str,
                )
            elif secrets.get("openai_api_key"):
                logger.info("Đang tóm tắt bản tin bằng OpenAI-compatible API...")
                ai_result = _call_openai(
                    api_key=secrets["openai_api_key"],
                    base_url=secrets.get("openai_base_url", "https://api.openai.com/v1"),
                    model=secrets.get("openai_model", "gpt-4o-mini"),
                    temperature=temperature,
                    payload_str=payload_str,
                )
            else:
                logger.info(
                    "Chưa cấu hình GEMINI_API_KEY hoặc OPENAI_API_KEY -> Sử dụng chế độ hiển thị trực tiếp."
                )
        except Exception as exc:
            logger.warning("AI Summarizer gặp lỗi, chuyển sang chế độ fallback: %s", exc)

    if ai_result:
        overview = ai_result.get("ai_overview") or default_overview
        sec_map = ai_result.get("sections") or {}
        for sec in sections:
            ai_sec = sec_map.get(sec.key) or {}
            sec.ai_commentary = ai_sec.get("commentary", "")
            ai_items = ai_sec.get("items") or []
            for idx, item in enumerate(sec.items):
                if idx < len(ai_items) and ai_items[idx]:
                    item.summary = str(ai_items[idx]).strip()
    else:
        overview = default_overview

    return MorningDigest(
        date_str=date_str,
        greeting=greeting,
        ai_overview=overview,
        sections=sections,
    )
