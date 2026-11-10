import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

WMO_WEATHER_CODES = {
    0: "☀️ Trời quang đãng, nắng đẹp",
    1: "🌤️ Trời ít mây, nắng nhẹ",
    2: "⛅ Có mây rải rác",
    3: "☁️ Trời nhiều mây",
    45: "🌫️ Có sương mù nhẹ",
    48: "🌫️ Sương mù dày",
    51: "🌦️ Mưa phùn nhẹ",
    53: "🌦️ Mưa phùn rải rác",
    55: "🌧️ Mưa phùn nặng hạt",
    61: "🌦️ Có mưa nhỏ",
    63: "🌧️ Mưa vừa",
    65: "🌧️ Mưa to",
    80: "🌦️ Mưa rào rải rác",
    81: "🌧️ Mưa rào vừa đến to",
    82: "⛈️ Mưa rào rất to",
    95: "⛈️ Có dông lốc",
    96: "⛈️ Dông kèm mưa lớn",
    99: "⛈️ Dông bão mạnh",
}

DEFAULT_CITIES = [
    {"name": "TP.HCM", "lat": 10.8231, "lon": 106.6297},
    {"name": "Hà Nội", "lat": 21.0285, "lon": 105.8542},
]

FOOTBALL_LEAGUES = [
    ("Ngoại Hạng Anh", "eng.1"),
    ("Champions League", "uefa.champions"),
    ("La Liga", "esp.1"),
    ("Serie A", "ita.1"),
    ("Bundesliga", "ger.1"),
    ("Europa League", "uefa.europa"),
]


def fetch_weather_summary(cities: List[Dict[str, Any]] | None = None) -> str:
    """Lấy dự báo thời tiết trong ngày từ Open-Meteo API (Miễn phí, không cần API key)."""
    target_cities = cities or DEFAULT_CITIES
    lines: List[str] = []
    max_rain_prob = 0

    for city in target_cities:
        name = city.get("name", "TP.HCM")
        lat = city.get("lat", 10.8231)
        lon = city.get("lon", 106.6297)
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max"
            "&timezone=Asia%2FHo_Chi_Minh&forecast_days=1"
        )
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            daily = resp.json().get("daily", {})
            w_code = (daily.get("weathercode") or [0])[0]
            t_min = round((daily.get("temperature_2m_min") or [25])[0])
            t_max = round((daily.get("temperature_2m_max") or [32])[0])
            rain_prob = int((daily.get("precipitation_probability_max") or [0])[0] or 0)
            uv_max = round((daily.get("uv_index_max") or [6])[0], 1)

            max_rain_prob = max(max_rain_prob, rain_prob)
            desc = WMO_WEATHER_CODES.get(w_code, "🌤️ Thời tiết ổn định")
            lines.append(
                f"• **{name}:** {desc} | 🌡️ `{t_min}°C – {t_max}°C` | ☔ Mưa: `{rain_prob}%` | ☀️ UV: `{uv_max}`"
            )
        except Exception as exc:
            logger.debug("Lỗi lấy thời tiết cho %s: %s", name, exc)

    if not lines:
        return ""

    if max_rain_prob >= 60:
        lines.append("💡 *Nhắc nhẹ: Khả năng mưa hôm nay khá cao, bạn nhớ mang theo áo mưa hoặc ô khi ra ngoài nhé!*")
    elif max_rain_prob >= 35:
        lines.append("💡 *Nhắc nhẹ: Chiều tối có thể có mưa rào nhẹ rải rác, nên thủ sẵn áo mưa trong cốp xe.*")
    else:
        lines.append("💡 *Nhắc nhẹ: Thời tiết hôm nay khá thuận lợi cho việc di chuyển và làm việc ngoài trời!*")

    return "\n".join(lines)


def fetch_upcoming_football_matches(max_matches: int = 6) -> str:
    """Lấy lịch thi đấu và kết quả các trận cầu tâm điểm hôm nay/đêm nay theo giờ Việt Nam (GMT+7)."""
    vn_tz = timezone(timedelta(hours=7))
    now_vn = datetime.now(vn_tz)
    date_param = now_vn.strftime("%Y%m%d")
    tomorrow_param = (now_vn + timedelta(days=1)).strftime("%Y%m%d")

    matches: List[str] = []
    for league_name, league_code in FOOTBALL_LEAGUES:
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
            f"?dates={date_param}-{tomorrow_param}"
        )
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            events = resp.json().get("events") or []
            for ev in events[:3]:
                comp = (ev.get("competitions") or [{}])[0]
                competitors = comp.get("competitors") or []
                if len(competitors) < 2:
                    continue

                home = competitors[0].get("team", {}).get("shortDisplayName") or competitors[0].get("team", {}).get("displayName", "")
                away = competitors[1].get("team", {}).get("shortDisplayName") or competitors[1].get("team", {}).get("displayName", "")
                status_obj = ev.get("status", {}).get("type", {})
                state = status_obj.get("state", "pre")

                date_iso = ev.get("date", "")
                kickoff_str = ""
                if date_iso:
                    try:
                        dt_utc = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                        dt_vn = dt_utc.astimezone(vn_tz)
                        kickoff_str = dt_vn.strftime("%H:%M (%d/%m)")
                    except Exception:
                        kickoff_str = ""

                if state == "post":
                    h_score = competitors[0].get("score", "0")
                    a_score = competitors[1].get("score", "0")
                    matches.append(f"• 🏆 `{league_name}`: **{home} {h_score} - {a_score} {away}** *(Đã kết thúc)*")
                elif state == "in":
                    h_score = competitors[0].get("score", "0")
                    a_score = competitors[1].get("score", "0")
                    matches.append(f"• 🔴 `{league_name}`: **{home} {h_score} - {a_score} {away}** *(Đang diễn ra)*")
                else:
                    time_badge = f"⏰ `{kickoff_str}`" if kickoff_str else "Sắp diễn ra"
                    matches.append(f"• ⚽ `{league_name}`: **{home} vs {away}** — {time_badge}")

                if len(matches) >= max_matches:
                    break
        except Exception as exc:
            logger.debug("Không thể lấy lịch thi đấu %s: %s", league_name, exc)
        if len(matches) >= max_matches:
            break

    if not matches:
        return "• ⚽ *Hôm nay các giải VĐQG châu Âu đang tạm nghỉ giữa tuần/nhường chỗ cho loạt trận tiếp theo.*"
    return "\n".join(matches)
