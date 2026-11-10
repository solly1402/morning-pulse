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

Nhiệm vụ của bạn là đọc danh sách các bài viết của một chuyên mục (kèm nội dung trích xuất từ bài gốc và các bình luận cộng đồng nếu có), sau đó dịch toàn bộ sang tiếng Việt và biên tập thành bản tóm tắt chuyên sâu, cực kỳ cuốn hút.

YÊU CẦU BẮT BUỘC:
1. **Gắn Nhãn Cảm Xúc & Độ Nóng + Dịch tiêu đề sang tiếng Việt (`title_vi`)**:
   - Đầu mỗi `title_vi`, BẮT BUỘC gắn 1 nhãn độ nóng ngắn gọn trong ngoặc vuông phù hợp nhất với nội dung bài:
     + `[🔥 CHẤN ĐỘNG]`, `[🛠️ ĐÁNG THỬ]`, `[⚡ ĐỘT PHÁ]`, `[⚠️ CẢNH BÁO]`, `[💰 THƯƠNG VỤ]`, `[💬 TRANH CÃI]`, `[⚽ TÂM ĐIỂM]`, `[🚨 BIẾN CĂNG]`
   - Tiếp theo là tiêu đề đã dịch sang tiếng Việt tự nhiên, hấp dẫn (riêng mục `github` giữ tên repo: ví dụ `"[🛠️ ĐÁNG THỬ] owner / repo — Công cụ tự động hóa..."`).
2. **Tóm tắt chuyên sâu chia theo 3 ý rõ ràng (`summary_vi`)**:
   - Trình bày `summary_vi` thành **3 dòng gạch đầu dòng súc tích (tổng cộng khoảng 75 - 115 từ)**, phân tách nhau bằng ký tự xuống dòng `\n`:
     + `• 📌 Cốt lõi:` 1-2 câu nêu rõ chuyện gì đang xảy ra hoặc công cụ/dự án này giải quyết bài toán gì.
     + `• 🔍 Chi tiết:` 1-2 câu cung cấp số liệu cụ thể, tính năng kỹ thuật, diễn biến trận đấu hoặc nội dung đắt giá nhất trong bài.
     + `• 🗣️ Góc nhìn & Tranh luận:` 1-2 câu tóm tắt phản ứng của cộng đồng quốc tế (khen/chê, góc nhìn trái chiều từ phần bình luận Hacker News/Reddit nếu có) hoặc ý nghĩa thực tế của sự kiện.

Trả về một JSON hợp lệ theo đúng cấu trúc sau:
{
  "commentary": "1-2 câu nhận xét tổng quan, sắc sảo bằng tiếng Việt về xu hướng nổi bật nhất của chuyên mục này hôm nay.",
  "items": [
    {
      "title_vi": "[🔥 NHÃN] Tiêu đề đã dịch sang tiếng Việt",
      "summary_vi": "• 📌 Cốt lõi: ...\n• 🔍 Chi tiết: ...\n• 🗣️ Góc nhìn & Tranh luận: ..."
    }
  ]
}"""

LEARNING_SYSTEM_INSTRUCTION = """Bạn là người cố vấn công nghệ và ngôn ngữ buổi sáng của "Morning Pulse".
Dựa trên danh sách các tiêu đề tin tức Công nghệ & Bóng đá sáng nay, hãy tạo góc "Mỗi Sáng 1 Kiến Thức Đắt Giá & 3 Từ Vựng Chuyên Ngành" giúp người đọc vừa cập nhật tin tức vừa giỏi lên mỗi ngày trong 15 giây.

Trả về một JSON hợp lệ theo đúng cấu trúc sau:
{
  "concept_of_the_day": "Chọn 1 khái niệm Kỹ thuật / System Design / Kiến trúc AI xuất hiện hoặc liên quan mật thiết tới tin tức sáng nay. Trình bày ngắn gọn 3-4 câu: Tên khái niệm (in đậm) -> Giải thích nguyên lý cực kỳ dễ hiểu bằng ví dụ thực tế -> Tại sao lập trình viên nên biết điều này.",
  "daily_vocab": [
    "🇬🇧 **Thuật ngữ 1 (Tech/Engineering)** *(loại từ)*: Nghĩa tiếng Việt ngắn gọn — *Ví dụ câu ngắn gắn với ngữ cảnh công nghệ.*",
    "🇬🇧 **Thuật ngữ 2 (AI/Software)** *(loại từ)*: Nghĩa tiếng Việt ngắn gọn — *Ví dụ câu ngắn gắn với ngữ cảnh lập trình.*",
    "🇬🇧 **Thuật ngữ 3 (Football/Sports Idiom)** *(loại từ)*: Nghĩa tiếng Việt ngắn gọn — *Ví dụ câu ngắn gắn với ngữ cảnh bóng đá quốc tế.*"
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
            "raw_content_and_comments": item.summary[:1050],
            "score": item.score or "",
        }
        for idx, item in enumerate(sec.items)
    ]
    user_prompt = (
        f"Chuyên mục: {sec.title} (key: {sec.key})\n"
        "Hãy gắn nhãn độ nóng + dịch tiêu đề sang tiếng Việt (`title_vi`) và viết bản tóm tắt chuyên sâu 3 ý "
        "(`• 📌 Cốt lõi:`, `• 🔍 Chi tiết:`, `• 🗣️ Góc nhìn & Tranh luận:`) trong `summary_vi` cho từng mục theo đúng thứ tự index:\n"
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


def _generate_daily_learning(
    sections: List[DigestSection],
    api_key: str,
    models: List[str],
    temperature: float,
) -> tuple[str, List[str]]:
    headlines = [
        f"[{sec.title}] {it.title}: {it.summary[:180]}"
        for sec in sections
        for it in sec.items[:2]
    ]
    user_prompt = (
        "Dưới đây là các chủ đề tin tức nổi bật sáng nay:\n"
        + "\n".join(headlines)
        + "\n\nHãy tạo 1 Kiến thức kỹ thuật đắt giá trong ngày (`concept_of_the_day`) và 3 Từ vựng tiếng Anh chuyên ngành (`daily_vocab`) theo đúng JSON mẫu."
    )
    res = _call_gemini_json(
        api_key=api_key,
        models=models,
        temperature=temperature,
        system_prompt=LEARNING_SYSTEM_INSTRUCTION,
        user_prompt=user_prompt,
    )
    concept = str(res.get("concept_of_the_day", "")).strip()
    vocab = [str(v).strip() for v in (res.get("daily_vocab") or []) if str(v).strip()]
    return concept, vocab


def build_morning_digest(
    raw_items: List[NewsItem], cfg: Dict[str, Any], date_obj: datetime | None = None
) -> MorningDigest:
    """Phân nhóm tin tức, dịch sang tiếng Việt, gắn nhãn độ nóng, tóm tắt comment và tạo góc Micro-Learning."""
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
    concept_of_the_day = ""
    daily_vocab: List[str] = []

    if ai_enabled and sections and provider == "gemini" and secrets.get("gemini_api_key"):
        primary = ai_cfg.get("gemini_model", "gemini-3-flash-preview")
        fallbacks = ai_cfg.get(
            "gemini_fallback_models",
            ["gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.1-flash-lite-preview"],
        )
        models = [primary] + [m for m in fallbacks if m != primary]

        for sec in sections:
            try:
                logger.info("🧠 Đang dịch, gắn nhãn & tóm tắt comment mục [%s %s] bằng Gemini 3...", sec.emoji, sec.title)
                _summarize_section_gemini(
                    sec=sec,
                    api_key=secrets["gemini_api_key"],
                    models=models,
                    temperature=temperature,
                )
                if sec.ai_commentary:
                    overview_lines.append(f"• **{sec.emoji} {sec.title}:** {sec.ai_commentary}")
                time.sleep(1.0)
            except Exception as exc:
                logger.warning("Không thể tóm tắt mục %s bằng AI: %s", sec.title, exc)

        try:
            logger.info("💡 Đang tạo góc 'Mỗi Sáng 1 Kiến Thức Đắt Giá & 3 Từ Vựng Chuyên Ngành'...")
            concept_of_the_day, daily_vocab = _generate_daily_learning(
                sections=sections,
                api_key=secrets["gemini_api_key"],
                models=models,
                temperature=temperature,
            )
        except Exception as exc:
            logger.warning("Không thể tạo góc Micro-Learning: %s", exc)

    overview = "\n\n".join(overview_lines) if overview_lines else default_overview

    # Tự động trích xuất "Top 3 Tin Không Thể Bỏ Lỡ" để đọc lướt 30 giây
    top_highlights: List[str] = []
    priority_order = [
        ("github", "🚀 Mã nguồn mở"),
        ("tech_news", "📰 Công nghệ"),
        ("football", "⚽ Bóng đá"),
        ("hackernews", "🟧 Hacker News"),
        ("reddit", "👽 Reddit"),
    ]
    sec_by_key = {s.key: s for s in sections}
    for key, label in priority_order:
        sec = sec_by_key.get(key)
        if sec and sec.items:
            top_item = sec.items[0]
            first_bullet = top_item.summary.splitlines()[0] if top_item.summary else ""
            first_bullet = first_bullet.replace("• 📌 Cốt lõi:", "").replace("•", "").strip()
            top_highlights.append(
                f"**[{label}] [{top_item.title}]({top_item.url})** — {first_bullet}"
            )
            if len(top_highlights) >= 3:
                break

    return MorningDigest(
        date_str=date_str,
        greeting=greeting,
        ai_overview=overview,
        sections=sections,
        top_highlights=top_highlights,
        concept_of_the_day=concept_of_the_day,
        daily_vocab=daily_vocab,
    )
