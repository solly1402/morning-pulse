import html
import logging
from typing import List

import requests

from src.models import DigestSection, MorningDigest

logger = logging.getLogger(__name__)

MAX_TELEGRAM_LEN = 3800


def _format_section_html(sec: DigestSection) -> str:
    lines = [f"<b>{sec.emoji} {html.escape(sec.title.upper())}</b>"]
    if sec.ai_commentary:
        lines.append(f"<i>💡 {html.escape(sec.ai_commentary)}</i>")
    lines.append("")

    for idx, item in enumerate(sec.items, 1):
        title_escaped = html.escape(item.title)
        url_escaped = html.escape(item.url, quote=True)
        meta_parts = []
        if item.extra_meta:
            meta_parts.append(html.escape(item.extra_meta))
        if item.score:
            meta_parts.append(html.escape(item.score))
        meta_str = f" (<code>{' | '.join(meta_parts)}</code>)" if meta_parts else ""

        line = f"{idx}. <a href=\"{url_escaped}\"><b>{title_escaped}</b></a>{meta_str}"
        if item.summary:
            line += f"\n   └ {html.escape(item.summary)}"
        lines.append(line)

    return "\n".join(lines)


def send_telegram_digest(digest: MorningDigest, bot_token: str, chat_id: str) -> bool:
    """Gửi bản tin buổi sáng qua Telegram Bot (sử dụng HTML parse mode và tự chia nhỏ tin nhắn)."""
    if not bot_token or not chat_id:
        logger.info("Bỏ qua Telegram: Chưa cấu hình TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.")
        return False

    header_lines = [
        f"☀️ <b>MORNING PULSE — {html.escape(digest.date_str)}</b>",
        "",
        f"<b>📌 Tâm điểm sáng nay:</b>\n{html.escape(digest.ai_overview)}",
    ]
    header_block = "\n".join(header_lines)

    blocks: List[str] = [header_block]
    for sec in digest.sections:
        blocks.append(_format_section_html(sec))

    # Gom các block thành các tin nhắn <= MAX_TELEGRAM_LEN ký tự
    messages: List[str] = []
    current_msg = ""
    for block in blocks:
        candidate = f"{current_msg}\n\n{'─' * 18}\n\n{block}" if current_msg else block
        if len(candidate) <= MAX_TELEGRAM_LEN:
            current_msg = candidate
        else:
            if current_msg:
                messages.append(current_msg)
            current_msg = block[:MAX_TELEGRAM_LEN]
    if current_msg:
        messages.append(current_msg)

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    success = True
    for msg in messages:
        try:
            resp = requests.post(
                api_url,
                json={
                    "chat_id": chat_id,
                    "text": msg,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=20,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.error("Lỗi khi gửi tin nhắn Telegram: %s", exc)
            success = False

    if success:
        logger.info("Đã gửi thành công bản tin qua Telegram (%d tin nhắn).", len(messages))
    return success
