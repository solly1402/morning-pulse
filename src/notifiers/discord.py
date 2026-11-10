import logging
import time
from typing import Any, Dict, List

import requests

from src.models import DigestSection, MorningDigest

logger = logging.getLogger(__name__)


def _build_section_embed(sec: DigestSection, date_str: str) -> Dict[str, Any]:
    desc_lines: List[str] = []
    if sec.ai_commentary:
        desc_lines.append(f"*{sec.ai_commentary}*\n")

    for idx, item in enumerate(sec.items, 1):
        meta = " • ".join(filter(None, [item.extra_meta, item.score]))
        meta_str = f" `[{meta}]`" if meta else ""
        line = f"**{idx}. [{item.title}]({item.url})**{meta_str}"
        if item.summary:
            short_sum = item.summary[:650] + "..." if len(item.summary) > 650 else item.summary
            line += f"\n> {short_sum}"
        desc_lines.append(line)

    description = "\n\n".join(desc_lines)
    if len(description) > 3800:
        description = description[:3795] + "..."

    return {
        "title": f"{sec.emoji} {sec.title}",
        "description": description,
        "color": sec.color,
        "footer": {"text": f"Morning Pulse • {date_str}"},
    }


def _embed_char_len(embed: Dict[str, Any]) -> int:
    return (
        len(embed.get("title", ""))
        + len(embed.get("description", ""))
        + len(embed.get("footer", {}).get("text", ""))
    )


def send_discord_digest(digest: MorningDigest, webhook_url: str) -> bool:
    """Gửi bản tin buổi sáng qua Discord Webhook dưới dạng Rich Embeds (tự chia batch < 5500 ký tự)."""
    if not webhook_url:
        logger.info("Bỏ qua Discord: Chưa cấu hình DISCORD_WEBHOOK_URL.")
        return False

    embeds = [_build_section_embed(sec, digest.date_str) for sec in digest.sections]
    content = (
        f"## ☀️ Morning Pulse — Bản tin sáng `{digest.date_str}`\n"
        f"{digest.ai_overview}"
    )
    if len(content) > 1950:
        content = content[:1945] + "..."

    # Discord giới hạn tổng số ký tự của tất cả embeds trong 1 request <= 6000 ký tự
    batches: List[List[Dict[str, Any]]] = []
    current_batch: List[Dict[str, Any]] = []
    current_chars = 0

    for emb in embeds:
        emb_len = _embed_char_len(emb)
        if current_batch and (current_chars + emb_len > 5000 or len(current_batch) >= 10):
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
        if idx == 0:
            payload["content"] = content

        try:
            resp = requests.post(webhook_url, json=payload, timeout=20)
            resp.raise_for_status()
            if idx < len(batches) - 1:
                time.sleep(0.5)
        except Exception as exc:
            logger.error("Lỗi khi gửi Discord Webhook (batch %d): %s", idx + 1, exc)
            success = False

    if success:
        logger.info("Đã gửi thành công bản tin qua Discord Webhook (%d tin nhắn).", len(batches))
    return success
