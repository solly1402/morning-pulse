import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from src.scrapers.lunar_vn import format_vietnamese_date_and_lunar

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
    {"name": "Biên Hoà, Đồng Nai", "lat": 10.9447, "lon": 106.8243},
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

# Danh sách CLB bóng đá mặc định cho "Radar Đội Bóng Ruột" (có thể tùy chỉnh trong config.yaml)
DEFAULT_FAVORITE_TEAMS = [
    {"name": "Manchester United", "league": "eng.1", "team_id": "360", "emoji": "👹"},
    {"name": "Real Madrid", "league": "esp.1", "team_id": "86", "emoji": "👑"},
]


def _fetch_city_aqi(lat: float, lon: float) -> tuple[int, float, str]:
    """Lấy chỉ số chất lượng không khí (US AQI) và bụi mịn PM2.5 từ Open-Meteo Air Quality API."""
    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}&current=us_aqi,pm2_5"
    )
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            curr = resp.json().get("current", {})
            aqi = int(round(curr.get("us_aqi") or 0))
            pm25 = round(float(curr.get("pm2_5") or 0.0), 1)
            if aqi <= 50:
                badge = f"🟢 AQI `{aqi}` (Trong lành)"
            elif aqi <= 100:
                badge = f"🟡 AQI `{aqi}` (TB)"
            elif aqi <= 150:
                badge = f"🟠 AQI `{aqi}` (Kém - Nên đeo khẩu trang)"
            else:
                badge = f"🔴 AQI `{aqi}` (Ô nhiễm)"
            return aqi, pm25, badge
    except Exception:
        pass
    return 0, 0.0, ""


def fetch_weather_summary(cities: List[Dict[str, Any]] | None = None) -> str:
    """Lấy Lịch Âm Việt Nam + Dự báo thời tiết + Chỉ số bụi mịn AQI cho Biên Hoà, TP.HCM, Hà Nội."""
    vn_tz = timezone(timedelta(hours=7))
    now_vn = datetime.now(vn_tz)

    target_cities = cities or DEFAULT_CITIES
    lines: List[str] = [format_vietnamese_date_and_lunar(now_vn)]
    max_rain_prob = 0
    max_aqi = 0

    for city in target_cities:
        name = city.get("name", "Biên Hoà, Đồng Nai")
        lat = city.get("lat", 10.9447)
        lon = city.get("lon", 106.8243)
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

            aqi_val, _, aqi_badge = _fetch_city_aqi(lat, lon)
            max_rain_prob = max(max_rain_prob, rain_prob)
            max_aqi = max(max_aqi, aqi_val)

            desc = WMO_WEATHER_CODES.get(w_code, "🌤️ Thời tiết ổn định")
            aqi_str = f" | 😷 {aqi_badge}" if aqi_badge else ""
            lines.append(
                f"• **{name}:** {desc} | 🌡️ `{t_min}°C – {t_max}°C` | ☔ Mưa: `{rain_prob}%` | ☀️ UV: `{uv_max}`{aqi_str}"
            )
        except Exception as exc:
            logger.debug("Lỗi lấy thời tiết cho %s: %s", name, exc)

    tips = []
    if max_rain_prob >= 60:
        tips.append("Khả năng mưa cao, nhớ mang theo áo mưa/ô")
    elif max_rain_prob >= 35:
        tips.append("Chiều tối có thể mưa rào nhẹ, nên thủ sẵn áo mưa")
    if max_aqi > 100:
        tips.append("bụi mịn khá cao, nhớ đeo khẩu trang khi ra đường")

    if tips:
        lines.append(f"💡 *Nhắc nhẹ: {'; '.join(tips)} nhé!*")

    return "\n".join(lines)


def fetch_market_ticker() -> str:
    """Lấy nhanh tỷ giá USD/VND, Giá Vàng Thế Giới (XAU/PAXG) và Bitcoin (BTC), Ethereum (ETH) sáng nay."""
    parts: List[str] = []

    try:
        resp_fx = requests.get("https://open.er-api.com/v6/latest/USD", timeout=8)
        if resp_fx.status_code == 200:
            vnd_rate = resp_fx.json().get("rates", {}).get("VND")
            if vnd_rate:
                parts.append(f"💵 **USD/VND:** `{int(round(vnd_rate)):,} ₫`")
    except Exception as exc:
        logger.debug("Không thể lấy tỷ giá USD/VND: %s", exc)

    label_map = {
        "PAXGUSDT": ("🪙 **Vàng (XAU):**", "$", "/oz"),
        "BTCUSDT": ("₿ **BTC:**", "$", ""),
        "ETHUSDT": ("Ξ **ETH:**", "$", ""),
    }
    try:
        resp_crypto = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbols": '["PAXGUSDT","BTCUSDT","ETHUSDT"]'},
            timeout=8,
        )
        if resp_crypto.status_code == 200:
            data_map = {item["symbol"]: item for item in resp_crypto.json()}
            for sym in ("PAXGUSDT", "BTCUSDT", "ETHUSDT"):
                info = data_map.get(sym)
                if not info:
                    continue
                label, prefix, unit = label_map[sym]
                price = float(info.get("lastPrice", 0))
                chg = float(info.get("priceChangePercent", 0))
                arrow = "📈" if chg >= 0 else "📉"
                sign = "+" if chg >= 0 else ""
                parts.append(f"{label} `{prefix}{int(round(price)):,}{unit}` ({arrow} `{sign}{chg:.1f}%`)")
    except Exception as exc:
        logger.debug("Không thể lấy dữ liệu thị trường: %s", exc)

    if not parts:
        return ""
    return "• " + "  |  ".join(parts)


def _fetch_team_recent_form(league: str, team_id: str, count: int = 5) -> str:
    """Lấy kết quả 5 trận đã đấu gần nhất và chuyển thành chuỗi icon 🟢 (Thắng), 🟡 (Hòa), 🔴 (Thua)."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team_id}/schedule"
    try:
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return ""
        events = resp.json().get("events") or []
        completed_icons: List[str] = []

        for ev in events:
            comp = (ev.get("competitions") or [{}])[0]
            status_type = comp.get("status", {}).get("type", {})
            if status_type.get("state") != "post" and not status_type.get("completed"):
                continue

            competitors = comp.get("competitors") or []
            if len(competitors) < 2:
                continue

            my_team = None
            opp_team = None
            for c in competitors:
                if str(c.get("id") or c.get("team", {}).get("id")) == str(team_id):
                    my_team = c
                else:
                    opp_team = c

            if not my_team or not opp_team:
                continue

            my_score_obj = my_team.get("score", {})
            opp_score_obj = opp_team.get("score", {})
            my_score = int(float(my_score_obj.get("value", 0) if isinstance(my_score_obj, dict) else (my_score_obj or 0)))
            opp_score = int(float(opp_score_obj.get("value", 0) if isinstance(opp_score_obj, dict) else (opp_score_obj or 0)))

            if my_team.get("winner") is True or my_score > opp_score:
                completed_icons.append("🟢")
            elif my_score == opp_score:
                completed_icons.append("🟡")
            else:
                completed_icons.append("🔴")

        if not completed_icons:
            return ""
        recent = completed_icons[-count:]
        return " ".join(recent)
    except Exception as exc:
        logger.debug("Không thể lấy phong độ 5 trận của team %s: %s", team_id, exc)
        return ""


def fetch_favorite_clubs_radar(teams_cfg: List[Dict[str, Any]] | None = None) -> str:
    """Radar theo dõi thứ hạng, phong độ 5 trận gần nhất (🟢/🟡/🔴) và lịch thi đấu sắp tới của CLB yêu thích."""
    vn_tz = timezone(timedelta(hours=7))
    target_teams = teams_cfg or DEFAULT_FAVORITE_TEAMS
    lines: List[str] = []

    for t in target_teams:
        name = t.get("name", "Man Utd")
        league = t.get("league", "eng.1")
        team_id = str(t.get("team_id", "360"))
        emoji = t.get("emoji", "⚽")

        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/teams/{team_id}"
            resp = requests.get(url, timeout=8)
            if resp.status_code != 200:
                continue
            team_data = resp.json().get("team", {})
            standing_summary = team_data.get("standingSummary") or ""
            form_icons = _fetch_team_recent_form(league, team_id, count=5)

            next_events = team_data.get("nextEvent") or []
            next_match_str = "Đang chờ lịch vòng tiếp theo"
            if next_events:
                ev = next_events[0]
                short_name = ev.get("shortName", "")
                date_iso = ev.get("date", "")
                kickoff_vn = ""
                if date_iso:
                    try:
                        dt_utc = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                        dt_vn = dt_utc.astimezone(vn_tz)
                        kickoff_vn = dt_vn.strftime("%H:%M ngày %d/%m")
                    except Exception:
                        pass
                next_match_str = f"`{short_name}` ({kickoff_vn})" if kickoff_vn else f"`{short_name}`"

            rank_part = f"📊 `{standing_summary}`" if standing_summary else ""
            form_part = f" | 🔥 5 trận gần nhất: {form_icons}" if form_icons else ""
            lines.append(
                f"• {emoji} **{name}:** {rank_part}{form_part} — ⏭️ Trận tới: {next_match_str}"
            )
        except Exception as exc:
            logger.debug("Không thể lấy Radar đội bóng %s: %s", name, exc)

    return "\n".join(lines)


def fetch_upcoming_football_matches(
    max_matches: int = 5,
    favorite_teams: List[Dict[str, Any]] | None = None,
) -> str:
    """Kết hợp Radar Đội Bóng Ruột + Lịch thi đấu các trận cầu tâm điểm hôm nay theo giờ Việt Nam (GMT+7)."""
    vn_tz = timezone(timedelta(hours=7))
    now_vn = datetime.now(vn_tz)
    date_param = now_vn.strftime("%Y%m%d")
    tomorrow_param = (now_vn + timedelta(days=1)).strftime("%Y%m%d")

    output_blocks: List[str] = []

    # 1. Radar Đội bóng ruột
    club_radar = fetch_favorite_clubs_radar(favorite_teams)
    if club_radar:
        output_blocks.append("⭐ **Radar Đội Bóng Yêu Thích:**\n" + club_radar)

    # 2. Các trận đấu diễn ra trong 24h tới
    matches: List[str] = []
    for league_name, league_code in FOOTBALL_LEAGUES:
        url = (
            f"https://site.api.espn.com/apis/site/v2/sports/soccer/{league_code}/scoreboard"
            f"?dates={date_param}-{tomorrow_param}"
        )
        try:
            resp = requests.get(url, timeout=8)
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

    if matches:
        output_blocks.append("🗓️ **Lịch & Kết quả trong ngày:**\n" + "\n".join(matches))

    return "\n\n".join(output_blocks)
