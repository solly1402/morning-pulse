import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def load_config(config_path: Path | None = None) -> Dict[str, Any]:
    """Đọc cấu hình từ file config.yaml và kết hợp biến môi trường."""
    path = config_path or (BASE_DIR / "config.yaml")
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file cấu hình tại: {path}")

    with open(path, "r", encoding="utf-8") as f:
        config: Dict[str, Any] = yaml.safe_load(f) or {}

    # Bổ sung thông tin nhạy cảm từ biến môi trường
    config["secrets"] = {
        "gemini_api_key": os.getenv("GEMINI_API_KEY", "").strip(),
        "openai_api_key": os.getenv("OPENAI_API_KEY", "").strip(),
        "openai_base_url": os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        ).strip(),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip(),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        "discord_webhook_url": os.getenv("DISCORD_WEBHOOK_URL", "").strip(),
    }
    return config
