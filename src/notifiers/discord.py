import json
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
                "_section_key": sec.key if page_idx == 1 else "",
            }
        )

    return embeds


def _build_overview_embed(
    digest: MorningDigest, toc_links: List[str] | None = None
) -> Dict[str, Any]:
    """Tạo thẻ Embed mở đầu (Hero Card) chứa Thời tiết, Lịch bóng đá, Top 3 Đọc lướt 30s & Mục lục nhảy nhanh."""
    parts: List[str] = [digest.greeting]

    if toc_links:
        parts.append("### 🧭 MỤC LỤC NHẢY NHANH (Bấm để cuộn tới chuyên mục)\n" + "  •  ".join(toc_links))

    if digest.weather_summary or digest.football_fixtures:
        assistant_lines: List[str] = ["### 🌤️ TRỢ LÝ ĐẦU NGÀY"]
        if digest.weather_summary:
            assistant_lines.append(digest.weather_summary)
        if digest.football_fixtures:
            assistant_lines.append("**⚽ Lịch & Kết quả các trận cầu tâm điểm:**\n" + digest.football_fixtures)
        parts.append("\n".join(assistant_lines))

    if digest.top_highlights:
        hl_lines = ["### 🏆 ĐỌC LƯỚT 30 GIÂY — TOP 3 TIN KHÔNG THỂ BỎ LỠ"]
        for idx, hl in enumerate(digest.top_highlights, 1):
            hl_lines.append(f"{_num_badge(idx)} {hl}")
        parts.append("\n".join(hl_lines))

    parts.append(f"### 📌 TÂM ĐIỂM TOÀN CẢNH\n{digest.ai_overview}")

    desc = f"\n\n{DIVIDER}\n\n".join(parts)
    if len(desc) > 4000:
        desc = desc[:3995] + "..."

    return {
        "title": f"☀️ BẮT ĐẦU BẢN TIN SÁNG — {digest.date_str}",
        "description": desc,
        "color": 0xF59E0B,
        "footer": {"text": f"🌅 Điểm bắt đầu bản tin ngày {digest.date_str} • Bấm Play file MP3 phía trên để nghe phát thanh!"},
    }


def _build_closing_divider_payload(
    digest: MorningDigest,
    jump_url: str | None = None,
    toc_links: List[str] | None = None,
) -> Dict[str, Any]:
    """Tạo vạch phân cách cuối ngày nổi bật kèm Mục lục nhảy nhanh và nút nhảy lên đầu bản tin."""
    total_items = sum(len(s.items) for s in digest.sections)
    banner_text = (
        "```\n"
        "╔══════════════════════════════════════════════════════════╗\n"
        f"║   🏁 KẾT THÚC BẢN TIN NGÀY {digest.date_str} • HẾT TIN HÔM NAY   ║\n"
        "╚══════════════════════════════════════════════════════════╝\n"
        "```"
    )
    jump_line = (
        f"⬆️ **Điều hướng nhanh:** [**Nhấn vào đây để nhảy thẳng lên đầu bản tin hôm nay ({digest.date_str})**]({jump_url})\n"
        if jump_url
        else ""
    )
    toc_line = (
        f"🧭 **Nhảy tới chuyên mục:** {'  •  '.join(toc_links)}\n"
        if toc_links
        else ""
    )
    closing_embed = {
        "title": f"✅ ĐÃ CẬP NHẬT XONG BẢN TIN NGÀY {digest.date_str}",
        "description": (
            f"{jump_line}"
            f"{toc_line}"
            f"📊 **Tổng kết:** Đã điểm qua **{total_items} tin tức mới** thuộc **{len(digest.sections)} chuyên mục**.\n"
            f"📚 **Lưu trữ trên GitHub:** [Xem bản đầy đủ ngày {digest.date_str}](https://github.com/solly1402/morning-pulse/blob/main/digests/{digest.date_str}.md)\n"
            "☕ *Chúc bạn một ngày làm việc tràn đầy năng lượng! Hẹn gặp lại vào **05:45 sáng mai**.*"
        ),
        "color": 0x6366F1,
        "footer": {
            "text": f"🔒 Vạch ngăn cách ngày {digest.date_str} — Các tin phía trên vạch này thuộc bản tin sáng {digest.date_str}"
        },
    }
    return {
        "username": "Morning Pulse ☕",
        "content": banner_text,
        "embeds": [closing_embed],
    }


def send_discord_digest(digest: MorningDigest, webhook_url: str) -> bool:
    """Gửi bản tin buổi sáng qua Discord kèm Audio MP3, Mục lục nhảy nhanh và Vạch phân chia cuối ngày."""
    if not webhook_url:
        logger.info("Bỏ qua Discord: Chưa cấu hình DISCORD_WEBHOOK_URL.")
        return False

    guild_id: str | None = None
    channel_id: str | None = None
    try:
        wh_info = requests.get(webhook_url, timeout=10).json()
        guild_id = wh_info.get("guild_id")
        channel_id = wh_info.get("channel_id")
    except Exception:
        pass

    success = True
    first_msg_id: str | None = None
    jump_url: str | None = None
    section_jump_links: List[str] = []

    # 1. Gửi thẻ Mở đầu (Hero Overview Card) + Đính kèm file Audio MP3 phát thanh buổi sáng
    overview_embed = _build_overview_embed(digest)
    hero_payload = {
        "username": "Morning Pulse ☕",
        "content": f"🌅 **`══════════ ☀️ BẮT ĐẦU BẢN TIN SÁNG {digest.date_str} ☀️ ══════════`**\n🎧 *Bấm **Play ▶** bên dưới để nghe phát thanh điểm tin buổi sáng trong lúc pha cà phê nhé!*",
        "embeds": [overview_embed],
    }

    try:
        post_url = f"{webhook_url}?wait=true"
        if digest.audio_path and digest.audio_path.exists():
            with open(digest.audio_path, "rb") as audio_file:
                resp = requests.post(
                    post_url,
                    data={"payload_json": json.dumps(hero_payload)},
                    files={"file": (digest.audio_path.name, audio_file, "audio/mpeg")},
                    timeout=35,
                )
        else:
            resp = requests.post(post_url, json=hero_payload, timeout=25)
        resp.raise_for_status()
        msg_data = resp.json()
        first_msg_id = msg_data.get("id")
        channel_id = msg_data.get("channel_id") or channel_id
        if guild_id and channel_id and first_msg_id:
            jump_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{first_msg_id}"
        time.sleep(0.6)
    except Exception as exc:
        logger.error("Lỗi khi gửi thẻ mở đầu Discord: %s", exc)
        success = False

    # 2. Gửi lần lượt từng chuyên mục và ghi nhận link nhảy tới đầu mỗi chuyên mục
    sec_meta_map = {s.key: (s.emoji, s.title) for s in digest.sections}
    for sec in digest.sections:
        sec_embeds = _build_section_embeds(sec, digest.date_str)
        # Chia mỗi lần gửi tối đa 2 thẻ của cùng 1 chuyên mục để dưới 4800 ký tự
        for i in range(0, len(sec_embeds), 2):
            chunk = sec_embeds[i : i + 2]
            clean_chunk = [{k: v for k, v in emb.items() if not k.startswith("_")} for emb in chunk]
            try:
                resp = requests.post(
                    f"{webhook_url}?wait=true",
                    json={"username": "Morning Pulse ☕", "embeds": clean_chunk},
                    timeout=25,
                )
                resp.raise_for_status()
                if i == 0 and guild_id and channel_id:
                    sec_msg_id = resp.json().get("id")
                    if sec_msg_id:
                        emoji, title = sec_meta_map[sec.key]
                        sec_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{sec_msg_id}"
                        section_jump_links.append(f"[{emoji} {title}]({sec_url})")
                time.sleep(0.6)
            except Exception as exc:
                logger.error("Lỗi khi gửi chuyên mục %s lên Discord: %s", sec.title, exc)
                success = False

    # 3. Cập nhật (PATCH) lại thẻ Mở đầu để gắn thanh Mục Lục Nhảy Nhanh (Table of Contents)
    if first_msg_id and section_jump_links:
        try:
            updated_overview = _build_overview_embed(digest, toc_links=section_jump_links)
            requests.patch(
                f"{webhook_url}/messages/{first_msg_id}",
                json={"embeds": [updated_overview]},
                timeout=15,
            )
        except Exception as exc:
            logger.debug("Không thể cập nhật Mục lục vào thẻ mở đầu Discord: %s", exc)

    # 4. Gửi vạch phân chia kết thúc bản tin trong ngày ở tin nhắn cuối cùng
    try:
        closing_payload = _build_closing_divider_payload(
            digest, jump_url=jump_url, toc_links=section_jump_links
        )
        resp = requests.post(webhook_url, json=closing_payload, timeout=25)
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Lỗi khi gửi vạch phân chia cuối ngày trên Discord: %s", exc)
        success = False

    if success:
        logger.info("Đã gửi thành công bản tin + Audio MP3 + Mục lục nhảy nhanh qua Discord Webhook.")
    return success
