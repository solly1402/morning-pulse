import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from src.models import NewsItem

logger = logging.getLogger(__name__)


def filter_and_record_seen_items(
    items: List[NewsItem],
    history_path: Path,
    today_str: str,
    retention_days: int = 7,
) -> List[NewsItem]:
    """Lọc bỏ các bài viết đã xuất hiện trong các ngày trước đó (giữ lại nếu chạy lại trong cùng ngày)."""
    history_path.parent.mkdir(parents=True, exist_ok=True)
    seen_map: Dict[str, str] = {}

    if history_path.exists():
        try:
            seen_map = json.loads(history_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Không thể đọc file lịch sử chống trùng lặp (%s): %s", history_path, exc)

    # Dọn dẹp các link cũ quá retention_days ngày
    try:
        today_dt = datetime.strptime(today_str, "%Y-%m-%d")
        cutoff_str = (today_dt - timedelta(days=retention_days)).strftime("%Y-%m-%d")
        seen_map = {url: dt_str for url, dt_str in seen_map.items() if dt_str >= cutoff_str}
    except Exception:
        pass

    filtered: List[NewsItem] = []
    skipped_count = 0

    for item in items:
        norm_url = item.url.strip().rstrip("/")
        prev_date = seen_map.get(norm_url)
        # Nếu bài viết đã gửi ở những ngày trước (khác ngày hôm nay) -> bỏ qua
        if prev_date and prev_date != today_str:
            skipped_count += 1
            continue

        filtered.append(item)
        seen_map[norm_url] = today_str

    try:
        history_path.write_text(
            json.dumps(seen_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.warning("Không thể lưu file lịch sử chống trùng lặp: %s", exc)

    if skipped_count > 0:
        logger.info("🧹 Đã lọc bỏ %d tin cũ từng xuất hiện trong %d ngày qua.", skipped_count, retention_days)
    else:
        logger.info("✨ Toàn bộ %d tin tức đều là tin mới trong ngày!", len(filtered))

    return filtered
