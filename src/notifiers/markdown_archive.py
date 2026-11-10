import logging
import re
from pathlib import Path
from typing import List

from src.models import MorningDigest

logger = logging.getLogger(__name__)


def _format_md_summary(summary: str) -> str:
    formatted = re.sub(
        r"(•\s*📌\s*Cốt lõi:|•\s*🔍\s*Chi tiết:|•\s*💡\s*Đáng chú ý:)",
        r"**\1**",
        summary,
    )
    lines = [line.strip() for line in formatted.splitlines() if line.strip()]
    return "\n".join(f"> {line}" for line in lines)


def render_digest_markdown(digest: MorningDigest) -> str:
    """Chuyển đổi đối tượng MorningDigest sang định dạng Markdown chuẩn GitHub."""
    lines: List[str] = [
        f"# ☕ Morning Pulse — Bản Tin Sáng `{digest.date_str}`",
        "",
        f"> {digest.greeting}",
        "",
    ]

    if digest.audio_path and digest.audio_path.exists():
        lines.extend(
            [
                f"🎧 **[Nghe Bản Tin Phát Thanh Buổi Sáng (MP3)](./audio/{digest.audio_path.name})**",
                "",
            ]
        )

    if digest.weather_summary or digest.football_fixtures:
        lines.extend(["## 🌤️ Trợ Lý Đầu Ngày", ""])
        if digest.weather_summary:
            lines.extend([digest.weather_summary, ""])
        if digest.football_fixtures:
            lines.extend(["### ⚽ Lịch & Kết quả các trận cầu tâm điểm", "", digest.football_fixtures, ""])
        lines.extend(["---", ""])

    if digest.top_highlights:
        lines.extend(["## 🏆 Đọc Lướt 30 Giây — Top 3 Tin Không Thể Bỏ Lỡ", ""])
        for idx, hl in enumerate(digest.top_highlights, 1):
            lines.append(f"{idx}. {hl}")
        lines.extend(["", "---", ""])

    lines.extend(
        [
            "## 📌 Điểm Tin Toàn Cảnh",
            "",
            digest.ai_overview,
            "",
            "---",
            "",
        ]
    )

    for sec in digest.sections:
        lines.append(f"## {sec.emoji} {sec.title}")
        lines.append("")
        if sec.ai_commentary:
            lines.append(f"> 💡 **Góc nhìn AI:** *{sec.ai_commentary}*")
            lines.append("")

        for idx, item in enumerate(sec.items, 1):
            meta_badges: List[str] = []
            if item.extra_meta:
                meta_badges.append(f"`{item.extra_meta}`")
            if item.score:
                meta_badges.append(f"`{item.score}`")
            if item.comments_url and item.comments_url != item.url:
                meta_badges.append(f"[💬 Thảo luận]({item.comments_url})")

            meta_str = " · ".join(meta_badges)
            header = f"### {idx}. [{item.title}]({item.url})"
            lines.append(header)
            if meta_str:
                lines.append(f"🏷️ {meta_str}")
                lines.append("")
            if item.summary:
                lines.append(_format_md_summary(item.summary))
            lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("*Bản tin được tạo tự động bởi **Morning Pulse**.*")
    return "\n".join(lines)


def save_markdown_digest(digest: MorningDigest, base_dir: Path, rel_dir: str = "digests") -> Path:
    """Lưu bản tin ra file digests/YYYY-MM-DD.md và cập nhật mục lục digests/README.md."""
    out_dir = base_dir / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    file_path = out_dir / f"{digest.date_str}.md"
    md_content = render_digest_markdown(digest)
    file_path.write_text(md_content, encoding="utf-8")

    digest_files = sorted(
        [p for p in out_dir.glob("????-??-??.md") if p.is_file()],
        key=lambda p: p.name,
        reverse=True,
    )

    index_lines = [
        "# 📚 Kho Lưu Trữ Bản Tin Hàng Ngày (Daily Digests)",
        "",
        "Danh sách các bản tin buổi sáng được tổng hợp tự động theo từng ngày:",
        "",
    ]
    for p in digest_files:
        date_label = p.stem
        audio_candidate = out_dir / "audio" / f"morning-pulse-{date_label}.mp3"
        audio_badge = f" · [🎧 Audio MP3](./audio/morning-pulse-{date_label}.mp3)" if audio_candidate.exists() else ""
        index_lines.append(f"- 📅 **[{date_label}](./{p.name})**{audio_badge}")

    index_path = out_dir / "README.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    logger.info("Đã lưu bản tin Markdown tại: %s", file_path)
    return file_path
