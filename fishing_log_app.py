# fishing_log_app.py
from __future__ import annotations

from datetime import datetime, date as Date
import urllib.parse

import pandas as pd
import requests
import streamlit as st

from analysis_tab import show_analysis
from db_utils_gsheets import fetch_all, insert_row
from check_tab import render_check_tab
from edit_tab import render_edit_tab

# 天気の取得ポイント
WEATHER_POINTS = {
    "芝浦":  {"lat": 35.640, "lon": 139.763},
    "羽田":  {"lat": 35.545, "lon": 139.781},
    "銚子":  {"lat": 35.740, "lon": 140.830},
    "鴨川":  {"lat": 35.110, "lon": 140.100},
    "岩井袋": {"lat": 35.060, "lon": 139.820},
    "横須賀": {"lat": 35.280, "lon": 139.670},
    "江の島": {"lat": 35.300, "lon": 139.480},
    "気仙沼": {"lat": 38.900, "lon": 141.570},
    "石巻":  {"lat": 38.430, "lon": 141.300},
}

TIDE736_PORTS = {
    "芝浦": {"pc": 13, "hc": 2},
    "羽田": {"pc": 13, "hc": 3},
    "銚子": {"pc": 12, "hc": 2},
    "鴨川": {"pc": 12, "hc": 6},
    "岩井袋": {"pc": 12, "hc": 10},
    "横須賀": {"pc": 14, "hc": 7},
    "江の島": {"pc": 14, "hc": 19},
    "気仙沼": {"pc": 4, "hc": 1},
    "石巻": {"pc": 4, "hc": 6},
}

SST_POINTS = {
    "芝浦":  {"lat": 35.640, "lon": 139.763},
    "羽田":  {"lat": 35.545, "lon": 139.781},
    "銚子":  {"lat": 35.700, "lon": 140.850},
    "鴨川":  {"lat": 35.100, "lon": 140.100},
    "岩井袋": {"lat": 35.070, "lon": 139.820},
    "横須賀": {"lat": 35.280, "lon": 139.670},
    "江の島": {"lat": 35.300, "lon": 139.480},
    "気仙沼": {"lat": 38.900, "lon": 141.570},
    "石巻":  {"lat": 38.430, "lon": 141.300},
}

@st.cache_data(ttl=1800, show_spinner=False)  # 30分キャッシュ
def filter_every_3_hours(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["time"].dt.hour % 3 == 0].reset_index(drop=True)

def wind_dir_arrow(deg: float) -> str:
    if deg is None:
        return "—"
    arrows = ["↑","↗","→","↘","↓","↙","←","↖"]
    return arrows[int((deg + 22.5) // 45) % 8]

def weather_code_label(code: int | None) -> str:
    if code is None:
        return "—"
    mapping = {
        0:  "☀️ 晴れ",
        1:  "🌤️ ほぼ晴れ",
        2:  "⛅ 薄曇り",
        3:  "☁️ 曇り",
        45: "🌫️ 霧",
        48: "🌫️ 霧",
        51: "🌦️ 弱い霧雨",
        53: "🌦️ 霧雨",
        55: "🌦️ 強い霧雨",
        61: "🌧️ 弱い雨",
        63: "🌧️ 雨",
        65: "🌧️ 強い雨",
        71: "🌨️ 弱い雪",
        73: "🌨️ 雪",
        75: "🌨️ 強い雪",
        80: "🌧️ にわか雨",
        81: "🌧️ にわか雨",
        82: "🌧️ 激しいにわか雨",
    }
    return mapping.get(int(code), f"❓({code})")

def wind_speed_style(val):
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v >= 10:
        return "color: #d00000; font-weight: bold;"
    elif v >= 5:
        return "color: #e6a700; font-weight: bold;"
    else:
        return ""

def fetch_weather_hourly(lat: float, lon: float, target_date: Date) -> pd.DataFrame:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "Asia/Tokyo",
        "start_date": target_date.strftime("%Y-%m-%d"),
        "end_date": target_date.strftime("%Y-%m-%d"),
        "hourly": (
            "temperature_2m,"
            "precipitation,"
            "wind_speed_10m,"
            "wind_direction_10m,"
            "weather_code"
        ),
    }
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()["hourly"]
    return pd.DataFrame({
        "time": pd.to_datetime(data["time"]),
        "temp": data["temperature_2m"],
        "rain": data["precipitation"],
        "wind_speed": data["wind_speed_10m"],
        "wind_dir": data["wind_direction_10m"],
        "weather_code": data["weather_code"],
    })

def fetch_current_sea_surface_temp(lat: float, lon: float) -> float | None:
    url = "https://marine-api.open-meteo.com/v1/marine"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "sea_surface_temperature",
        "timezone": "Asia/Tokyo",
        "cell_selection": "sea",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    current = data.get("current", {})
    sst = current.get("sea_surface_temperature")
    if sst is None:
        return None
    return float(sst)

@st.cache_data(show_spinner=False)
def fetch_tide736_day(pc: int, hc: int, target_date: Date):
    params = {
        "pc": pc,
        "hc": hc,
        "yr": target_date.year,
        "mn": target_date.month,
        "dy": target_date.day,
        "rg": "day",
    }
    resp = requests.get("https://api.tide736.net/get_tide.php", params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 1:
        raise ValueError(f"tide736 API error: {data.get('message')}")

    key = target_date.strftime("%Y-%m-%d")
    chart = data["tide"]["chart"][key]
    return chart["tide"]

def get_tide_height_for_time(pc: int, hc: int, target_date: Date, t: datetime.time):
    tide_list = fetch_tide736_day(pc, hc, target_date)
    target_min = t.hour * 60 + t.minute
    best = None
    best_diff = 10**9

    for item in tide_list:
        hh, mm = map(int, item["time"].split(":"))
        m = hh * 60 + mm
        diff = abs(m - target_min)
        if diff < best_diff:
            best_diff = diff
            best = item

    if best is None:
        raise ValueError("tide data not found")
    return float(best["cm"]), best["time"]

def build_tide736_image_url(
    target_date: Date,
    pc: int,
    hc: int,
    width: int = 768,
    height: int = 320,
) -> str:
    base = "https://api.tide736.net/tide_image.php"
    params = {
        "pc": pc,
        "hc": hc,
        "yr": target_date.year,
        "mn": target_date.month,
        "dy": target_date.day,
        "rg": "day",
        "w": width,
        "h": height,
        "lc": "blue",
        "gcs": "cyan",
        "gcf": "blue",
        "ld": "on",
        "ttd": "on",
        "tsmd": "on",
    }
    return base + "?" + urllib.parse.urlencode(params)


# ===== UI 起動 =====
st.set_page_config(page_title="釣行ログ管理", page_icon="🎣", layout="centered")

tab_check, tab_edit, tab_analysis = st.tabs(["🌊 釣行前チェック", "📝 データ編集", "📈 分析"])

with tab_check:
    render_check_tab(
        TIDE736_PORTS=TIDE736_PORTS,
        WEATHER_POINTS=WEATHER_POINTS,
        SST_POINTS=SST_POINTS,
        build_tide736_image_url=build_tide736_image_url,
        fetch_weather_hourly=fetch_weather_hourly,
        filter_every_3_hours=filter_every_3_hours,
        weather_code_label=weather_code_label,
        wind_dir_arrow=wind_dir_arrow,
        wind_speed_style=wind_speed_style,
        fetch_current_sea_surface_temp=fetch_current_sea_surface_temp,
    )

with tab_edit:
    render_edit_tab()

with tab_analysis:
    show_analysis()
