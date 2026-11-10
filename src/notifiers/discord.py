import logging
import re
import time
from typing import Any, Dict, List

import requests

from src.models import DigestSection, MorningDigest, NewsItem

logger = logging.getLogger(__name__)

NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
DIVIDER = "⎯" * 20
MAX_ITEMS_PER_CARD = 3
MAX_CARD_CHARS = 3400


def _num_badge(idx: int) -> str:
    if 1 <= idx <= len(NUM_EMOJIS):
        return NUM_EMOJIS[idx - 1]
    return f"**#{idx}**"


def _format_summary_quote(summary: str) -> str:
    """Định dạng phần tóm tắt thành các dòng trích dẫn (blockquote) có in đậm nhãn để dễ đọc lướt."""
    if not summary:
        return ""
    # Làm nổi bật các nhãn đầu dòng nếu có
    formatted = re.sub(
        r"(•\s*📌\s*Cốt lõi:|•\s*🔍\s*Chi tiết:|•\s*💡\s*Đáng chú ý:)",
        r"**\1**",
        summary,
    )
    lines = [line.strip() for line in formatted.splitlines() if line.strip()]
    return "\n".join(f"> {line}" for line in lines)


def _format_item_block(idx: int, item: NewsItem) -> str:
    badge = _num_badge(idx)
    block_lines: List[str] = [f"### {badge} [{item.title}]({item.url})"]

    meta_parts: List[str] = []
    if item.extra_meta:
        meta_parts.append(f"`{item.extra_meta}`")
    elif item.source:
        meta_parts.append(f"`{item.source}`")
    if item.score:
        meta_parts.append(f"`{item.score}`")
    if item.comments_url and item.comments_url != item.url:
        meta_parts.append(f"[💬 Thảo luận]({item.comments_url})")

    if meta_parts:
        block_lines.append("🏷️ " + " • ".join(meta_parts))

    if item.summary:
        block_lines.append(_format_summary_quote(item.summary))

    return "\n".join(block_lines)


def _build_section_embeds(sec: DigestSection, date_str: str) -> List[Dict[str, Any]]:
    """Chia một chuyên mục thành nhiều thẻ Embed nhỏ (tối đa 3 tin/thẻ) để KHÔNG BAO GIỜ bị cắt chữ."""
    item_blocks: List[str] = [
        _format_item_block(idx, item) for idx, item in enumerate(sec.items, 1)
    ]

    pages: List[List[str]] = []
    current_page: List[str] = []
    current_len = len(sec.ai_commentary) + 50

    for block in item_blocks:
        sep_len = len(DIVIDER) + 4 if current_page else 0
        if current_page and (
            len(current_page) >= MAX_ITEMS_PER_CARD
            or current_len + sep_len + len(block) > MAX_CARD_CHARS
        ):
            pages.append(current_page)
            current_page = [block]
            current_len = len(block)
        else:
            current_page.append(block)
            current_len += sep_len + len(block)

    if current_page:
        pages.append(current_page)

    total_pages = len(pages)
    embeds: List[Dict[str, Any]] = []

    for page_idx, page_blocks in enumerate(pages, 1):
        desc_parts: List[str] = []
        if page_idx == 1 and sec.ai_commentary:
            desc_parts.append(f"💡 ***Góc nhìn AI:** {sec.ai_commentary}*")
            desc_parts.append(DIVIDER)

        desc_parts.append(f"\n\n{DIVIDER}\n\n".join(page_blocks))
        description = "\n\n".join(desc_parts)

        page_suffix = f" ({page_idx}/{total_pages})" if total_pages > 1 else ""
        embeds.append(
            {
                "title": f"{sec.emoji} {sec.title.upper()}{page_suffix}",
                "description": description,
                "color": sec.color,
                "footer": {
                    "text": f"☕ Morning Pulse • {sec.title}{page_suffix} • {date_str}"
                },
            }
        )

    return embeds


def _build_overview_embed(digest: MorningDigest) -> Dict[str, Any]:
    """Tạo thẻ Embed mở đầu (Hero Card) chứa toàn bộ điểm tin tổng quan không sợ giới hạn 2000 ký tự."""
    return {
        "title": f"☀️ MORNING PULSE — BẢN TIN SÁNG {digest.date_str}",
        "description": (
            f"{digest.greeting}\n\n"
            f"### 📌 TÂM ĐIỂM SÁNG NAY\n"
            f"{digest.ai_overview}"
        ),
        "color": 0xF59E0B,  # Màu vàng nắng buổi sáng
        "footer": {"text": f"☕ Morning Pulse Daily Digest • {digest.date_str}"},
    }


def _embed_char_len(embed: Dict[str, Any]) -> int:
    return (
        len(embed.get("title", ""))
        + len(embed.get("description", ""))
        + len(embed.get("footer", {}).get("text", ""))
    )


def send_discord_digest(digest: MorningDigest, webhook_url: str) -> bool:
    """Gửi bản tin buổi sáng qua Discord Webhook với bố cục tạp chí (Magazine Cards) không bị cắt chữ."""
    if not webhook_url:
        logger.info("Bỏ qua Discord: Chưa cấu hình DISCORD_WEBHOOK_URL.")
        return False

    all_embeds: List[Dict[str, Any]] = [_build_overview_embed(digest)]
    for sec in digest.sections:
        all_embeds.extend(_build_section_embeds(sec, digest.date_str))

    # Gửi từng thẻ hoặc gom tối đa 4800 ký tự/lần để đảm bảo Discord hiển thị mượt và đúng thứ tự
    batches: List[List[Dict[str, Any]]] = []
    current_batch: List[Dict[str, Any]] = []
    current_chars = 0

    for emb in all_embeds:
        emb_len = _embed_char_len(emb)
        if current_batch and (current_chars + emb_len > 4800 or len(current_batch) >= 3):
            batches.append(current_batch)
            current_batch = [emb]
            current_chars = emb_len
        else:
            current_batch.append(emb)
            current_chars += emb_len
    if current_batch:
        batches.append(current_batch)

    success = True
    for idx, batch in enumerate(batches):
        payload: Dict[str, Any] = {
            "username": "Morning Pulse ☕",
            "embeds": batch,
        }
        try:
            resp = requests.post(webhook_url, json=payload, timeout=25)
            resp.raise_for_status()
            if idx < len(batches) - 1:
                time.sleep(0.6)
        except Exception as exc:
            logger.error("Lỗi khi gửi Discord Webhook (batch %d): %s", idx + 1, exc)
            success = False

    if success:
        logger.info(
            "Đã gửi thành công bản tin qua Discord Webhook (%d thẻ trong %d tin nhắn, không cắt chữ).",
            len(all_embeds),
            len(batches),
        )
    return success
