import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import List

from src.config import BASE_DIR, load_config
from src.models import NewsItem
from src.notifiers.discord import send_discord_digest
from src.notifiers.markdown_archive import save_markdown_digest
from src.notifiers.telegram import send_telegram_digest
from src.scrapers.github_trending import fetch_github_trending
from src.scrapers.hackernews import fetch_hacker_news
from src.scrapers.reddit import fetch_reddit_posts
from src.scrapers.rss_feeds import fetch_rss_category
from src.summarizer.ai_summarizer import build_morning_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("morning-pulse")


def collect_all_news(cfg: dict) -> List[NewsItem]:
    """Thu thập tin tức từ tất cả các nguồn được bật trong config.yaml."""
    sources_cfg = cfg.get("sources", {})
    all_items: List[NewsItem] = []

    logger.info("🔍 Bắt đầu thu thập dữ liệu tin tức buổi sáng...")

    # 1. GitHub Trending
    all_items.extend(fetch_github_trending(sources_cfg.get("github_trending", {})))

    # 2. Hacker News
    all_items.extend(fetch_hacker_news(sources_cfg.get("hacker_news", {})))

    # 3. Reddit (Tech, AI & r/soccer)
    all_items.extend(fetch_reddit_posts(sources_cfg.get("reddit", {})))

    # 4. Báo Công Nghệ (RSS)
    all_items.extend(
        fetch_rss_category(
            sources_cfg.get("tech_news", {}),
            category="tech_news",
            filter_football=False,
        )
    )

    # 5. Bóng Đá Thế Giới (RSS)
    all_items.extend(
        fetch_rss_category(
            sources_cfg.get("football", {}),
            category="football",
            filter_football=True,
        )
    )

    logger.info("✅ Hoàn tất thu thập: Tổng cộng %d tin tức.", len(all_items))
    return all_items


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Morning Pulse — Bot tổng hợp & tóm tắt tin tức mỗi sáng bằng AI."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ thu thập và lưu file Markdown, không gửi qua Telegram/Discord.",
    )
    args = parser.parse_args()

    # Đảm bảo console Windows hiển thị tiếng Việt và emoji chuẩn UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    cfg = load_config()
    vn_tz = timezone(timedelta(hours=7))
    now_vn = datetime.now(vn_tz)

    items = collect_all_news(cfg)
    if not items:
        logger.error("Không thu thập được tin tức nào. Kết thúc chương trình.")
        return 1

    digest = build_morning_digest(items, cfg, date_obj=now_vn)
    outputs_cfg = cfg.get("outputs", {})
    secrets = cfg.get("secrets", {})

    # 1. Lưu file Markdown lên kho lưu trữ Daily Digest
    md_cfg = outputs_cfg.get("markdown_archive", {})
    if md_cfg.get("enabled", True):
        md_path = save_markdown_digest(
            digest,
            base_dir=BASE_DIR,
            rel_dir=md_cfg.get("directory", "digests"),
        )
        logger.info("📄 Đã xuất bản trang Daily Digest: %s", md_path)

    if args.dry_run:
        logger.info("Chế độ --dry-run đang bật: Bỏ qua gửi Telegram & Discord.")
        return 0

    # 2. Gửi qua Telegram Bot
    if outputs_cfg.get("telegram", {}).get("enabled", True):
        send_telegram_digest(
            digest=digest,
            bot_token=secrets.get("telegram_bot_token", ""),
            chat_id=secrets.get("telegram_chat_id", ""),
        )

    # 3. Gửi qua Discord Webhook
    if outputs_cfg.get("discord", {}).get("enabled", True):
        send_discord_digest(
            digest=digest,
            webhook_url=secrets.get("discord_webhook_url", ""),
        )

    logger.info("🎉 Morning Pulse đã hoàn thành nhiệm vụ sáng nay!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
