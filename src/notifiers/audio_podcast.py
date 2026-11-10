import logging
import re
from pathlib import Path

from gtts import gTTS

from src.models import MorningDigest

logger = logging.getLogger(__name__)


def _clean_text_for_speech(text: str) -> str:
    """Làm sạch các ký hiệu Markdown, URL và emoji để giọng đọc AI mượt mà, tự nhiên nhất."""
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>|~•]", " ", text)
    text = re.sub(
        r"[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f]",
        " ",
        text,
    )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_radio_script(digest: MorningDigest) -> str:
    """Tạo kịch bản phát thanh buổi sáng tự nhiên như biên tập viên Radio đọc điểm tin."""
    parts = [
        f"Chào buổi sáng! Bạn đang lắng nghe bản tin phát thanh Morning Pulse ngày {digest.date_str}.",
    ]

    if digest.weather_summary:
        clean_w = _clean_text_for_speech(digest.weather_summary)
        parts.append(f"Trước tiên là thông tin thời tiết trong ngày: {clean_w}")

    if digest.top_highlights:
        parts.append("Mở đầu bản tin, hãy cùng điểm qua 3 sự kiện nóng nhất không thể bỏ lỡ sáng nay:")
        for idx, hl in enumerate(digest.top_highlights, 1):
            parts.append(f"Tin số {idx}: {_clean_text_for_speech(hl)}")

    if digest.ai_overview:
        parts.append("Tiếp theo là bức tranh toàn cảnh các chuyên mục:")
        parts.append(_clean_text_for_speech(digest.ai_overview))

    for sec in digest.sections:
        if sec.items:
            top_item = sec.items[0]
            title_clean = _clean_text_for_speech(top_item.title)
            first_line = top_item.summary.splitlines()[0] if top_item.summary else ""
            sum_clean = _clean_text_for_speech(first_line).replace("Cốt lõi:", "").strip()
            parts.append(f"Tại mục {sec.title}, nổi bật nhất là: {title_clean}. {sum_clean}")

    parts.append(
        "Đó là những nội dung đáng chú ý nhất trong bản tin phát thanh sáng nay. "
        "Mời bạn xem chi tiết từng bài viết ngay bên dưới. "
        "Chúc bạn một ngày mới tràn đầy năng lượng! Hẹn gặp lại vào 5 giờ 45 phút sáng mai."
    )
    return " ".join(parts)


def generate_morning_audio(digest: MorningDigest, base_dir: Path) -> Path | None:
    """Chuyển kịch bản điểm tin buổi sáng thành file âm thanh MP3 tiếng Việt."""
    try:
        audio_dir = base_dir / "digests" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        out_path = audio_dir / f"morning-pulse-{digest.date_str}.mp3"

        script_text = digest.radio_script or build_radio_script(digest)
        clean_script = _clean_text_for_speech(script_text)

        logger.info("🎧 Đang tạo file Audio phát thanh buổi sáng (MP3)...")
        tts = gTTS(text=clean_script, lang="vi", slow=False)
        tts.save(str(out_path))
        logger.info("✅ Đã tạo xong file Audio Podcast: %s", out_path)
        return out_path
    except Exception as exc:
        logger.warning("Không thể tạo file Audio phát thanh: %s", exc)
        return None
