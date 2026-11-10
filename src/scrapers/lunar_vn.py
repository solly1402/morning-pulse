"""Thuật toán tính Lịch Âm Việt Nam (GMT+7) theo công thức thiên văn của TS. Hồ Ngọc Đức."""

import math
from datetime import datetime, timedelta

CAN = ["Giáp", "Ất", "Bính", "Đinh", "Mậu", "Kỷ", "Canh", "Tân", "Nhâm", "Quý"]
CHI = ["Tý", "Sửu", "Dần", "Mão", "Thìn", "Tỵ", "Ngọ", "Mùi", "Thân", "Dậu", "Tuất", "Hợi"]
WEEKDAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]


def _jd_from_date(dd: int, mm: int, yy: int) -> int:
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:
        jd = dd + (153 * m + 2) // 5 + 365 * y + y // 4 - 32083
    return jd


def _new_moon(k: int) -> int:
    t = k / 1236.85
    t2 = t * t
    t3 = t2 * t
    dr = math.pi / 180.0
    jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * t2 - 0.000000155 * t3
    jd1 += 0.00033 * math.sin((166.56 + 132.87 * t - 0.009173 * t2) * dr)
    m = 359.2242 + 29.10535608 * k - 0.0000333 * t2 - 0.00000347 * t3
    mpr = 306.0253 + 385.81691806 * k + 0.0107306 * t2 + 0.00001236 * t3
    f = 21.2964 + 390.67050646 * k - 0.0016528 * t2 - 0.00000239 * t3
    c1 = (0.1734 - 0.000393 * t) * math.sin(m * dr) + 0.0021 * math.sin(2 * dr * m)
    c1 = c1 - 0.4068 * math.sin(mpr * dr) + 0.0161 * math.sin(dr * 2 * mpr)
    c1 -= 0.0004 * math.sin(dr * 3 * mpr)
    c1 = c1 + 0.0104 * math.sin(dr * 2 * f) - 0.0051 * math.sin(dr * (m + mpr))
    c1 = c1 - 0.0074 * math.sin(dr * (m - mpr)) + 0.0004 * math.sin(dr * (2 * f + m))
    c1 = c1 - 0.0004 * math.sin(dr * (2 * f - m)) - 0.0006 * math.sin(dr * (2 * f + mpr))
    c1 += 0.0010 * math.sin(dr * (2 * f - mpr)) + 0.0005 * math.sin(dr * (2 * mpr + m))
    if t < -11:
        deltat = 0.001 + 0.000839 * t + 0.0002261 * t2 - 0.00000845 * t3 - 0.000000081 * t * t3
    else:
        deltat = -0.000278 + 0.000265 * t + 0.000262 * t2
    jd_new = jd1 + c1 - deltat
    return int(jd_new + 0.5 + 7.0 / 24.0)


def _sun_longitude(jdn: int) -> int:
    t = (jdn - 2451545.5 - 7.0 / 24.0) / 36525.0
    t2 = t * t
    dr = math.pi / 180.0
    m = 357.52910 + 35999.05030 * t - 0.0001559 * t2 - 0.00000048 * t * t2
    l0 = 280.46645 + 36000.76983 * t + 0.0003032 * t2
    dl = (1.914600 - 0.004817 * t - 0.000014 * t2) * math.sin(dr * m)
    dl += (0.019993 - 0.000101 * t) * math.sin(dr * 2 * m) + 0.000290 * math.sin(dr * 3 * m)
    l_true = (l0 + dl) * dr
    l_true -= math.pi * 2 * int(l_true / (math.pi * 2))
    return int(l_true / math.pi * 6)


def _get_lunar_month11(yy: int) -> int:
    off = _jd_from_date(31, 12, yy) - 2415021
    k = int(off / 29.530588853)
    nm = _new_moon(k)
    sun_long = _sun_longitude(nm)
    if sun_long >= 9:
        nm = _new_moon(k - 1)
    return nm


def _get_leap_month_offset(a11: int) -> int:
    k = int((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    last = 0
    i = 1
    arc = _sun_longitude(_new_moon(k + i))
    while True:
        last = arc
        i += 1
        arc = _sun_longitude(_new_moon(k + i))
        if not (arc != last and i < 14):
            break
    return i - 1


def solar_to_lunar_vn(dd: int, mm: int, yy: int) -> tuple[int, int, int, bool]:
    """Đổi ngày Dương lịch sang Âm lịch Việt Nam (GMT+7). Trả về (ngày, tháng, năm, nhuận)."""
    day_number = _jd_from_date(dd, mm, yy)
    k = int((day_number - 2415021.076998695) / 29.530588853)
    month_start = _new_moon(k + 1)
    if month_start > day_number:
        month_start = _new_moon(k)
    a11 = _get_lunar_month11(yy)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = _get_lunar_month11(yy - 1)
    else:
        lunar_year = yy + 1
        b11 = _get_lunar_month11(yy + 1)
    lunar_day = day_number - month_start + 1
    diff = int((month_start - a11) / 29)
    lunar_leap = False
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_month_diff = _get_leap_month_offset(a11)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = True
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return lunar_day, lunar_month, lunar_year, lunar_leap


def format_vietnamese_date_and_lunar(now_vn: datetime) -> str:
    """Tạo dòng thông tin Thứ/Ngày Dương lịch kèm Âm lịch Việt Nam & nhắc ngày Rằm/Mùng 1/Cuối tuần."""
    wd_name = WEEKDAYS_VI[now_vn.weekday()]
    l_day, l_month, l_year, is_leap = solar_to_lunar_vn(now_vn.day, now_vn.month, now_vn.year)
    can_chi_year = f"{CAN[(l_year + 6) % 10]} {CHI[(l_year + 8) % 12]}"
    leap_str = " (Nhuận)" if is_leap else ""

    notes = []
    if l_day == 1:
        notes.append("🌕 **Hôm nay là Mùng 1 đầu tháng Âm lịch!**")
    elif l_day == 15:
        notes.append("🌕 **Hôm nay là ngày Rằm (15 Âm lịch)!**")
    else:
        # Kiểm tra ngày mai có phải Mùng 1 hoặc Rằm không
        tmr = now_vn + timedelta(days=1)
        t_day, _, _, _ = solar_to_lunar_vn(tmr.day, tmr.month, tmr.year)
        if t_day == 1:
            notes.append("🔔 *Nhắc nhẹ: Ngày mai là Mùng 1 Âm lịch!*")
        elif t_day == 15:
            notes.append("🔔 *Nhắc nhẹ: Ngày mai là ngày Rằm (15 Âm lịch)!*")

    if now_vn.weekday() == 4:
        notes.append("🎉 *Thứ Sáu rồi, cố lên bạn ơi!*")
    elif now_vn.weekday() in (5, 6):
        notes.append("☕ *Cuối tuần thư giãn!*")

    note_suffix = "  •  " + " ".join(notes) if notes else ""
    return (
        f"• 📅 **Hôm nay:** {wd_name}, `{now_vn.strftime('%d/%m/%Y')}` "
        f"— **Âm lịch:** Ngày `{l_day:02d}/{l_month:02d}` năm {can_chi_year}{leap_str}{note_suffix}"
    )
