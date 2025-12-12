# check_tab.py
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime, date as Date

def render_check_tab(
    *,
    TIDE736_PORTS: dict,
    WEATHER_POINTS: dict,
    SST_POINTS: dict,
    build_tide736_image_url,
    fetch_weather_hourly,
    filter_every_3_hours,
    weather_code_label,
    wind_dir_arrow,
    wind_speed_style,
    fetch_current_sea_surface_temp,
):
    st.title("🎣 釣行ログ管理アプリ")
    st.caption("釣行前チェック（潮位・天気・水温）")
    st.divider()

    # ==== タイドグラフ ====
    st.subheader("指定日のタイドグラフ")

    c1, c2 = st.columns(2)
    with c1:
        tide_date = st.date_input(
            "潮位を確認する日",
            value=datetime.now().date(),
            key="tide736_date",
        )
    with c2:
        spot_name = st.selectbox(
            "港（tide736の基準地点）",
            options=list(TIDE736_PORTS.keys()),
            index=0,
            key="tide736_spot",
        )

    spot = TIDE736_PORTS[spot_name]
    tide_img_url = build_tide736_image_url(
        target_date=tide_date,
        pc=spot["pc"],
        hc=spot["hc"],
        width=768,
        height=512,
    )

    st.image(tide_img_url, use_column_width=True)
    st.caption("※データ元：tide736.net（日本沿岸736港の潮汐表）")

    st.divider()

    # ==== 3時間天気 ====
    st.subheader("3時間ごとの天気・風（目安）")

    p = WEATHER_POINTS.get(spot_name)
    if p is None:
        st.info("この港の天気座標が未登録です。")
    else:
        try:
            df_hourly = fetch_weather_hourly(p["lat"], p["lon"], tide_date)
            df_3h = filter_every_3_hours(df_hourly)

            df_view = pd.DataFrame({
                "時刻": df_3h["time"].dt.strftime("%H:%M"),
                "天気": df_3h["weather_code"].apply(weather_code_label),
                "気温(℃)": df_3h["temp"],
                "降水(mm)": df_3h["rain"],
                "風速(m/s)": df_3h["wind_speed"],
                "風向": df_3h["wind_dir"].apply(wind_dir_arrow),
            })

            styled = (
                df_view.style
                .format({
                    "気温(℃)": "{:.1f}",
                    "降水(mm)": "{:.1f}",
                    "風速(m/s)": "{:.1f}",
                })
                .applymap(wind_speed_style, subset=["風速(m/s)"])
            )

            st.dataframe(
                styled,
                hide_index=True,
                use_container_width=True,
            )
            st.caption("※ Open-Meteo（予報モデル）。風速は10m高度の値です。")
        except Exception as e:
            st.warning(f"天気の取得に失敗しました: {e}")

    st.divider()

    # ==== 水温（現在） ====
    st.subheader("現在の水温（海面・推定値）")

    sst_point = SST_POINTS.get(spot_name, {"lat": 35.6, "lon": 139.9})
    try:
        sst = fetch_current_sea_surface_temp(sst_point["lat"], sst_point["lon"])
        if sst is not None:
            st.metric(f"{spot_name} 付近の海面水温", f"{sst:.1f} ℃")
        else:
            st.info("現在の水温データを取得できませんでした。")
    except Exception as e:
        st.warning(f"水温の取得に失敗しました: {e}")
