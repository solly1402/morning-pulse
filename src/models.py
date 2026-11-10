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
    score: Optional[str] = None  # Ví dụ: "⭐ 1,240 (+320 today)" hoặc "🔥 450 points"
    comments_url: Optional[str] = None
    extra_meta: Optional[str] = None  # Ngôn ngữ lập trình, subreddit, tên báo...


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
