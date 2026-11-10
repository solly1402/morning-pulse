from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NewsItem:
    """Đại diện cho một mẫu tin tức hoặc repository thu thập được."""

    title: str
    url: str
    source: str
    category: str  # "github", "hackernews", "reddit", "tech_news", "football"
    summary: str = ""
    score: Optional[str] = None
    comments_url: Optional[str] = None
    extra_meta: Optional[str] = None
    image_url: Optional[str] = None  # Ảnh bìa (og:image) để hiển thị trực quan trên Discord


@dataclass
class DigestSection:
    """Một chuyên mục trong bản tin buổi sáng."""

    key: str
    title: str
    emoji: str
    color: int  # Mã màu thập phân dùng cho Discord Embed
    items: List[NewsItem] = field(default_factory=list)
    ai_commentary: str = ""


@dataclass
class MorningDigest:
    """Toàn bộ bản tin buổi sáng sau khi tổng hợp và tóm tắt."""

    date_str: str
    greeting: str
    ai_overview: str
    sections: List[DigestSection] = field(default_factory=list)
    top_highlights: List[str] = field(default_factory=list)  # Top 3 tin không thể bỏ lỡ (đọc lướt 30s)
    weather_summary: str = ""  # Dự báo thời tiết trong ngày
    market_ticker: str = ""  # Nhịp đập thị trường (USD/VND, Vàng, BTC, ETH)
    football_fixtures: str = ""  # Lịch thi đấu & kết quả các trận cầu tâm điểm hôm nay
    concept_of_the_day: str = ""  # Mỗi sáng 1 kiến thức đắt giá (System Design / AI / Tech)
    daily_vocab: List[str] = field(default_factory=list)  # 3 thuật ngữ tiếng Anh chuyên ngành trong ngày
