import html
import logging
import re
from typing import List

import requests

from src.models import DigestSection, MorningDigest

logger = logging.getLogger(__name__)

MAX_TELEGRAM_LEN = 3800
NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def _num_badge(idx: int) -> str:
    if 1 <= idx <= len(NUM_EMOJIS):
        return NUM_EMOJIS[idx - 1]
    return f"#{idx}"


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


def _format_summary_html(summary: str) -> str:
    escaped = html.escape(summary)
    escaped = re.sub(
        r"(•\s*📌\s*Cốt lõi:|•\s*🔍\s*Chi tiết:|•\s*💡\s*Đáng chú ý:)",
        r"<b>\1</b>",
        escaped,
    )
    return f"<blockquote>{escaped}</blockquote>"


def _format_section_html(sec: DigestSection) -> str:
    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        f"{sec.emoji} <b>{html.escape(sec.title.upper())}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if sec.ai_commentary:
        lines.append(f"💡 <i>{html.escape(sec.ai_commentary)}</i>")
    lines.append("")

    for idx, item in enumerate(sec.items, 1):
        badge = _num_badge(idx)
        title_escaped = html.escape(item.title)
        url_escaped = html.escape(item.url, quote=True)
        meta_parts = []
        if item.extra_meta:
            meta_parts.append(f"<code>{html.escape(item.extra_meta)}</code>")
        elif item.source:
            meta_parts.append(f"<code>{html.escape(item.source)}</code>")
        if item.score:
            meta_parts.append(f"<code>{html.escape(item.score)}</code>")
        if item.comments_url and item.comments_url != item.url:
            comm_escaped = html.escape(item.comments_url, quote=True)
            meta_parts.append(f"<a href=\"{comm_escaped}\">💬 Thảo luận</a>")

        lines.append(f"{badge} <a href=\"{url_escaped}\"><b>{title_escaped}</b></a>")
        if meta_parts:
            lines.append("🏷️ " + " • ".join(meta_parts))
        if item.summary:
            lines.append(_format_summary_html(item.summary))
        lines.append("")

    return "\n".join(lines).strip()


def _build_closing_html(digest: MorningDigest, first_msg_id: int | None = None) -> str:
    total_items = sum(len(s.items) for s in digest.sections)
    date_esc = html.escape(digest.date_str)
    lines = [
        "<pre>╔════════════════════════════════════╗\n"
        f"║  🏁 KẾT THÚC BẢN TIN {date_esc}  ║\n"
        "╚════════════════════════════════════╝</pre>",
        f"✅ <b>Đã cập nhật xong {total_items} tin tức sáng {date_esc}!</b>",
        f"📚 <a href=\"https://github.com/solly1402/morning-pulse/blob/main/digests/{date_esc}.md\">Xem lưu trữ đầy đủ trên GitHub</a>",
        "📌 <i>Mẹo: Bấm vào thanh <b>Tin nhắn đã ghim (Pinned Message)</b> ở góc trên cùng màn hình để nhảy thẳng về đầu bản tin sáng nay mà không cần lướt tìm!</i>",
        "☕ <i>Chúc bạn một ngày làm việc hiệu quả! Hẹn gặp lại vào 05:45 sáng mai.</i>",
        "██████████████████████████████",
    ]
    return "\n".join(lines)


def send_telegram_digest(digest: MorningDigest, bot_token: str, chat_id: str) -> bool:
    """Gửi bản tin buổi sáng qua Telegram Bot, tự động ghim tin mở đầu và gửi vạch kết thúc ngày."""
    if not bot_token:
        logger.info("Bỏ qua Telegram: Chưa cấu hình TELEGRAM_BOT_TOKEN.")
        return False

    effective_chat_id = chat_id or _discover_chat_id(bot_token)
    if not effective_chat_id:
        logger.warning(
            "⚠️ Chưa tìm thấy TELEGRAM_CHAT_ID. Bạn hãy mở link t.me/solly1402_bot trên Telegram và bấm 'Start' nhé!"
        )
        return False

    overview_html = html.escape(digest.ai_overview)
    overview_html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", overview_html)

    header_lines = [
        "<pre>╔════════════════════════════════════╗\n"
        f"║   ☀️ BẮT ĐẦU BẢN TIN {html.escape(digest.date_str)}   ║\n"
        "╚════════════════════════════════════╝</pre>",
        "📌 <b>TÂM ĐIỂM SÁNG NAY</b>",
        f"<blockquote>{overview_html}</blockquote>",
    ]
    header_block = "\n".join(header_lines)

    blocks: List[str] = [header_block]
    for sec in digest.sections:
        blocks.append(_format_section_html(sec))

    messages: List[str] = []
    for block in blocks:
        if len(block) <= MAX_TELEGRAM_LEN:
            messages.append(block)
        else:
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
            if sub_msg:
                messages.append(sub_msg)

    # Thêm vạch phân chia kết thúc ngày làm tin nhắn chốt sổ cuối cùng
    messages.append(_build_closing_html(digest))

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    pin_url = f"https://api.telegram.org/bot{bot_token}/pinChatMessage"
    success = True
    first_message_id: int | None = None

    for idx, msg in enumerate(messages):
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
                if idx == 0:
                    first_message_id = resp.json().get("result", {}).get("message_id")
                sent = True
                break
            except Exception as exc:
                if attempt == 2:
                    logger.error("Lỗi khi gửi tin nhắn Telegram: %s", exc)
        if not sent:
            success = False

    # Tự động Ghim (Pin) tin nhắn đầu tiên của ngày hôm nay để người dùng bấm 1 chạm nhảy lên đầu ngày mới
    if first_message_id:
        try:
            requests.post(
                pin_url,
                json={
                    "chat_id": effective_chat_id,
                    "message_id": first_message_id,
                    "disable_notification": True,
                },
                timeout=15,
            )
            logger.info("📌 Đã tự động ghim (Pin) tin nhắn mở đầu bản tin hôm nay trên Telegram.")
        except Exception as exc:
            logger.debug("Không thể ghim tin nhắn Telegram: %s", exc)

    if success:
        logger.info("Đã gửi thành công bản tin + vạch phân chia cuối ngày qua Telegram (%d tin nhắn).", len(messages))
    return success
