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
    """Chuyển đổi các cú pháp Markdown cơ bản (**bold**, *italic*, `code`, [text](url)) sang HTML cho Telegram."""
    escaped = html.escape(text)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2"><b>\1</b></a>',
        escaped,
    )
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


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


def _build_header_html(digest: MorningDigest) -> str:
    header_lines = [
        "<pre>╔════════════════════════════════════╗\n"
        f"║   ☀️ BẮT ĐẦU BẢN TIN {html.escape(digest.date_str)}   ║\n"
        "╚════════════════════════════════════╝</pre>",
    ]

    if digest.weather_summary or digest.football_fixtures:
        header_lines.append("🌤️ <b>TRỢ LÝ ĐẦU NGÀY</b>")
        assistant_parts: List[str] = []
        if digest.weather_summary:
            assistant_parts.append(_md_to_telegram_html(digest.weather_summary))
        if digest.football_fixtures:
            assistant_parts.append("<b>⚽ Lịch & Kết quả bóng đá tâm điểm:</b>\n" + _md_to_telegram_html(digest.football_fixtures))
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


def _build_closing_html(digest: MorningDigest) -> str:
    total_items = sum(len(s.items) for s in digest.sections)
    date_esc = html.escape(digest.date_str)
    lines = [
        "<pre>╔════════════════════════════════════╗\n"
        f"║  🏁 KẾT THÚC BẢN TIN {date_esc}  ║\n"
        "╚════════════════════════════════════╝</pre>",
        f"✅ <b>Đã cập nhật xong {total_items} tin tức sáng {date_esc}!</b>",
        f"📚 <a href=\"https://github.com/solly1402/morning-pulse/blob/main/digests/{date_esc}.md\">Xem lưu trữ đầy đủ trên GitHub</a>",
        "📌 <i>Mẹo: Bấm vào thanh <b>Tin nhắn đã ghim (Pinned Message)</b> ở góc trên cùng màn hình để nhảy thẳng về đầu bản tin sáng nay (kèm file Audio phát thanh) mà không cần lướt tìm!</i>",
        "☕ <i>Chúc bạn một ngày làm việc hiệu quả! Hẹn gặp lại vào 05:45 sáng mai.</i>",
        "██████████████████████████████",
    ]
    return "\n".join(lines)


def send_telegram_digest(digest: MorningDigest, bot_token: str, chat_id: str) -> bool:
    """Gửi bản tin buổi sáng qua Telegram Bot, đính kèm Audio Podcast MP3, ghim tin mở đầu và gửi vạch kết thúc ngày."""
    if not bot_token:
        logger.info("Bỏ qua Telegram: Chưa cấu hình TELEGRAM_BOT_TOKEN.")
        return False

    effective_chat_id = chat_id or _discover_chat_id(bot_token)
    if not effective_chat_id:
        logger.warning(
            "⚠️ Chưa tìm thấy TELEGRAM_CHAT_ID. Bạn hãy mở link t.me/solly1402_bot trên Telegram và bấm 'Start' nhé!"
        )
        return False

    header_block = _build_header_html(digest)

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

    messages.append(_build_closing_html(digest))

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    audio_url = f"https://api.telegram.org/bot{bot_token}/sendAudio"
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

        # Ngay sau tin nhắn Mở đầu (idx == 0), gửi file Audio MP3 phát thanh buổi sáng
        if idx == 0 and digest.audio_path and digest.audio_path.exists():
            try:
                with open(digest.audio_path, "rb") as af:
                    requests.post(
                        audio_url,
                        data={
                            "chat_id": effective_chat_id,
                            "title": f"Bản Tin Phát Thanh Sáng {digest.date_str}",
                            "performer": "Morning Pulse AI Radio ☕",
                            "caption": f"🎧 <b>Bản tin phát thanh buổi sáng ({digest.date_str})</b> — Bấm Play để nghe điểm tin trong 2 phút!",
                            "parse_mode": "HTML",
                        },
                        files={"audio": (digest.audio_path.name, af, "audio/mpeg")},
                        timeout=45,
                    )
                logger.info("🎧 Đã gửi file Audio phát thanh qua Telegram.")
            except Exception as exc:
                logger.warning("Không thể gửi file Audio qua Telegram: %s", exc)

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
        logger.info("Đã gửi thành công bản tin + Audio + vạch phân chia cuối ngày qua Telegram.")
    return success
