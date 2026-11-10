import html
import logging
from typing import List

import requests

from src.models import DigestSection, MorningDigest

logger = logging.getLogger(__name__)

MAX_TELEGRAM_LEN = 3800


def _discover_chat_id(bot_token: str) -> str:
    """Tự động dò tìm Chat ID từ người dùng vừa nhắn /start cho Bot."""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("result", [])
        for update in reversed(results):
            msg = update.get("message") or update.get("my_chat_member") or {}
            chat = msg.get("chat") or {}
            chat_id = chat.get("id")
            if chat_id:
                logger.info("🔍 Đã tự động tìm thấy Telegram Chat ID: %s", chat_id)
                return str(chat_id)
    except Exception as exc:
        logger.debug("Không thể tự động dò Telegram Chat ID: %s", exc)
    return ""


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
        lines.append("")

    return "\n".join(lines).strip()


def send_telegram_digest(digest: MorningDigest, bot_token: str, chat_id: str) -> bool:
    """Gửi bản tin buổi sáng qua Telegram Bot (tự động dò Chat ID nếu chưa cấu hình)."""
    if not bot_token:
        logger.info("Bỏ qua Telegram: Chưa cấu hình TELEGRAM_BOT_TOKEN.")
        return False

    effective_chat_id = chat_id or _discover_chat_id(bot_token)
    if not effective_chat_id:
        logger.warning(
            "⚠️ Chưa tìm thấy TELEGRAM_CHAT_ID. Bạn hãy mở link t.me/solly1402_bot trên Telegram và bấm nút 'Start' (hoặc nhắn 'hi') để kích hoạt nhận tin nhé!"
        )
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
            # Nếu 1 block đơn lẻ quá dài (> MAX_TELEGRAM_LEN), chia nhỏ theo từng mục tin
            if len(block) > MAX_TELEGRAM_LEN:
                chunks = block.split("\n\n")
                sub_msg = ""
                for ch in chunks:
                    cand_sub = f"{sub_msg}\n\n{ch}" if sub_msg else ch
                    if len(cand_sub) <= MAX_TELEGRAM_LEN:
                        sub_msg = cand_sub
                    else:
                        if sub_msg:
                            messages.append(sub_msg)
                        sub_msg = ch[:MAX_TELEGRAM_LEN]
                current_msg = sub_msg
            else:
                current_msg = block
    if current_msg:
        messages.append(current_msg)

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    success = True
    for msg in messages:
        sent = False
        for attempt in range(3):
            try:
                resp = requests.post(
                    api_url,
                    json={
                        "chat_id": effective_chat_id,
                        "text": msg,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=35,
                )
                resp.raise_for_status()
                sent = True
                break
            except Exception as exc:
                if attempt == 2:
                    logger.error("Lỗi khi gửi tin nhắn Telegram: %s", exc)
        if not sent:
            success = False

    if success:
        logger.info("Đã gửi thành công bản tin qua Telegram (%d tin nhắn).", len(messages))
    return success
