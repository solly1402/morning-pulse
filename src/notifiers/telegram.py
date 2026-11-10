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


def _md_to_telegram_html(text: str) -> str:
    """Chuyển đổi các cú pháp Markdown (kể cả tiêu đề có [TAG] bên trong link) sang HTML an toàn cho Telegram."""
    escaped = html.escape(text)
    # 1. Xử lý in đậm **...** và in nghiêng *...* và `code` trước
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^\*\n]+?)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", escaped)
    # 2. Xử lý link Markdown [text có thể chứa [TAG]](url)
    escaped = re.sub(
        r"\[((?:\[[^\]]*\]|[^\]])+)\]\((https?://[^\)\s]+)\)",
        r'<a href="\2">\1</a>',
        escaped,
    )
    return escaped


def _format_summary_html(summary: str) -> str:
    # Loại bỏ dòng trống kép bên trong summary để giữ nguyên khối blockquote
    clean_lines = [line.strip() for line in summary.splitlines() if line.strip()]
    escaped = html.escape("\n".join(clean_lines))
    escaped = re.sub(
        r"(•\s*📌\s*Cốt lõi:|•\s*🔍\s*Chi tiết:|•\s*🗣️\s*Góc nhìn &amp; Tranh luận:|•\s*💡\s*Đáng chú ý:)",
        r"<b>\1</b>",
        escaped,
    )
    return f"<blockquote>{escaped}</blockquote>"


def _build_section_messages(sec: DigestSection) -> List[str]:
    """Chia chuyên mục thành các tin nhắn Telegram hoàn chỉnh, không bao giờ cắt ngang thẻ HTML."""
    header_lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        f"{sec.emoji} <b>{html.escape(sec.title.upper())}</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if sec.ai_commentary:
        header_lines.append(f"💡 <i>{html.escape(sec.ai_commentary)}</i>")
    header_str = "\n".join(header_lines)

    item_blocks: List[str] = []
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

        b_lines = [f"{badge} <a href=\"{url_escaped}\"><b>{title_escaped}</b></a>"]
        if meta_parts:
            b_lines.append("🏷️ " + " • ".join(meta_parts))
        if item.summary:
            b_lines.append(_format_summary_html(item.summary))
        item_blocks.append("\n".join(b_lines))

    messages: List[str] = []
    current_msg = header_str
    for ib in item_blocks:
        candidate = f"{current_msg}\n\n{ib}"
        if len(candidate) <= MAX_TELEGRAM_LEN:
            current_msg = candidate
        else:
            messages.append(current_msg)
            current_msg = f"<b>{sec.emoji} {html.escape(sec.title.upper())} (tiếp)</b>\n\n{ib}"
    if current_msg:
        messages.append(current_msg)

    return messages


def _build_header_html(digest: MorningDigest) -> str:
    header_lines = [
        "<pre>╔════════════════════════════════════╗\n"
        f"║   ☀️ BẮT ĐẦU BẢN TIN {html.escape(digest.date_str)}   ║\n"
        "╚════════════════════════════════════╝</pre>",
    ]

    if digest.weather_summary or digest.market_ticker or digest.football_fixtures:
        header_lines.append("🌤️ <b>TRỢ LÝ ĐẦU NGÀY &amp; THỊ TRƯỜNG</b>")
        assistant_parts: List[str] = []
        if digest.weather_summary:
            assistant_parts.append(_md_to_telegram_html(digest.weather_summary))
        if digest.market_ticker:
            assistant_parts.append("<b>💰 Nhịp đập thị trường:</b>\n" + _md_to_telegram_html(digest.market_ticker))
        if digest.football_fixtures:
            assistant_parts.append(_md_to_telegram_html(digest.football_fixtures))
        header_lines.append("<blockquote>" + "\n\n".join(assistant_parts) + "</blockquote>")
        header_lines.append("")

    if digest.top_highlights:
        header_lines.append("🏆 <b>ĐỌC LƯỚT 30 GIÂY — TOP 3 TIN KHÔNG THỂ BỎ LỠ</b>")
        hl_parts = [f"{_num_badge(i)} {_md_to_telegram_html(hl)}" for i, hl in enumerate(digest.top_highlights, 1)]
        header_lines.append("<blockquote>" + "\n\n".join(hl_parts) + "</blockquote>")
        header_lines.append("")

    overview_html = _md_to_telegram_html(digest.ai_overview)
    header_lines.append("📌 <b>TÂM ĐIỂM TOÀN CẢNH</b>")
    header_lines.append(f"<blockquote>{overview_html}</blockquote>")

    return "\n".join(header_lines)


def _build_learning_html(digest: MorningDigest) -> str:
    if not digest.concept_of_the_day and not digest.daily_vocab:
        return ""

    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "🧠 <b>GÓC NÂNG TẦM MỖI SÁNG</b>",
        "━━━━━━━━━━━━━━━━━━━━",
    ]
    if digest.concept_of_the_day:
        lines.append("💡 <b>Mỗi sáng 1 Kiến thức đắt giá:</b>")
        lines.append(f"<blockquote>{_md_to_telegram_html(digest.concept_of_the_day)}</blockquote>")
        lines.append("")

    if digest.daily_vocab:
        lines.append("🇬🇧 <b>3 Thuật ngữ Tiếng Anh chuyên ngành trong ngày:</b>")
        vocab_html = "\n\n".join(f"• {_md_to_telegram_html(v)}" for v in digest.daily_vocab)
        lines.append(f"<blockquote>{vocab_html}</blockquote>")

    return "\n".join(lines).strip()


def _build_closing_html(digest: MorningDigest) -> str:
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
    """Gửi bản tin buổi sáng qua Telegram Bot, ghim tin mở đầu, kèm Góc học tập và gửi vạch kết thúc ngày."""
    if not bot_token:
        logger.info("Bỏ qua Telegram: Chưa cấu hình TELEGRAM_BOT_TOKEN.")
        return False

    effective_chat_id = chat_id or _discover_chat_id(bot_token)
    if not effective_chat_id:
        logger.warning(
            "⚠️ Chưa tìm thấy TELEGRAM_CHAT_ID. Bạn hãy mở link t.me/solly1402_bot trên Telegram và bấm 'Start' nhé!"
        )
        return False

    messages: List[str] = [_build_header_html(digest)]
    for sec in digest.sections:
        messages.extend(_build_section_messages(sec))

    learning_block = _build_learning_html(digest)
    if learning_block:
        messages.append(learning_block)

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
                    logger.error("Lỗi khi gửi tin nhắn Telegram (msg %d): %s", idx + 1, exc)
        if not sent:
            success = False

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
        logger.info("Đã gửi thành công bản tin + Góc nâng tầm + vạch phân chia cuối ngày qua Telegram (%d tin nhắn).", len(messages))
    return success
