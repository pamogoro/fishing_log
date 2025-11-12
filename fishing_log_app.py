# fishing_log_app.py
# import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from analysis_tab import show_analysis
from db_utils_gsheets import fetch_all, insert_row, update_row, delete_row

def _coerce_types_for_sort(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["date_dt"] = pd.to_datetime(d["date"], errors="coerce")
    d["time_dt"] = pd.to_datetime(d["time"], format="%H:%M", errors="coerce")
    d["size_num"] = pd.to_numeric(d["size"], errors="coerce")
    return d

def _sort_logs(df: pd.DataFrame) -> pd.DataFrame:
    d = _coerce_types_for_sort(df)

    # --- 初期値（初回ロード時は「日付・新しい順・サブなし」） ---
    if "sort_key_col" not in st.session_state:
        st.session_state.sort_key_col = "日付"
    if "sort_order" not in st.session_state:
        st.session_state.sort_order = "新しい順"
    if "sort_sub_key" not in st.session_state:
        st.session_state.sort_sub_key = "（なし）"

    st.markdown("### 一覧のソート")
    c1, c2, c3 = st.columns(3)

    with c1:
        key_col = st.selectbox(
            "ソート対象",
            ["日付", "サイズ"],
            index=["日付","サイズ"].index(st.session_state.sort_key_col),
            key="sort_key_col",
            help="並び替えたい項目を選んでください"
        )
    with c2:
        if key_col == "日付":
            order_options = ["新しい順", "古い順"]
        else:
            order_options = ["大きい順", "小さい順"]
        order = st.radio(
            "順序", order_options,
            index=order_options.index(st.session_state.sort_order if st.session_state.sort_order in order_options else order_options[0]),
            key="sort_order",
            horizontal=True
        )
    with c3:
        sub_options = ["（なし）", "時間", "サイズ", "日付"]
        sub_key = st.selectbox(
            "サブソート", sub_options,
            index=sub_options.index(st.session_state.sort_sub_key),
            key="sort_sub_key",
            help="同値のときの並び順（任意）"
        )

    # メインキー / 並び方向
    if key_col == "日付":
        key = "date_dt"
        ascending = (order == "古い順")   # 新しい順=降順
    else:
        key = "size_num"
        ascending = (order == "小さい順") # 大きい順=降順

    # サブキー
    sub_map = {"（なし）": [], "時間": ["time_dt"], "サイズ": ["size_num"], "日付": ["date_dt"]}
    by_cols = [key] + sub_map[sub_key]
    asc_list = [ascending] + ([True] * len(sub_map[sub_key]))  # サブは昇順で自然に

    d_sorted = d.sort_values(by=by_cols, ascending=asc_list, na_position="last").copy()

    display_cols = ["id","date","time","area","tide_type","tide_height","temperature",
                    "wind_direction","lure","action","size"]
    return d_sorted[display_cols]

st.set_page_config(page_title="釣行ログ管理", page_icon="🎣", layout="centered")

tab1, tab2 = st.tabs(["🎣 釣行データ", "📈 分析"])

with tab1:
    # ---------- 初期化 ----------
    # init_db()
    if "edit_row" not in st.session_state:
        st.session_state.edit_row = None  # dict or None

    st.title("🎣 釣行ログ管理アプリ")
    st.caption("スマホからも入力OK・SQLiteで手軽に保存")

    st.divider()
    st.caption("📝 新しい釣行データを入力してください")

    # ---------- 新規登録フォーム ----------
    with st.form("log_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            date = st.date_input("日付", datetime.now())
            time = st.time_input("時間", value=None)  # ← 追加
            area = st.text_input("エリア（例：水の広場公園）")
            temperature = st.number_input("気温 (℃)", step=0.1, format="%.1f")
            size = st.number_input("サイズ (cm)", step=1, min_value=0)
        with c2:
            tide_type = st.selectbox("潮回り", ["大潮", "中潮", "小潮", "若潮", "長潮"])
            tide_height = st.number_input("潮位 (cm)", step=1, min_value=0)  # ← 追加
            wind_direction = st.text_input("風向（例：北北東）")
            lure = st.text_input("ルアー（例：バクリースピン6）")
            action = st.text_input("アクション（例：スローリトリーブ）")

        # time は st.time_input(...) の戻り値（datetime.time or None）
        time_str = time.strftime("%H:%M") if time else "00:00"

        submitted = st.form_submit_button("登録")
        if submitted:
            insert_row(
                date.strftime("%Y-%m-%d"),
                time_str,
                area.strip(),
                tide_type,
                float(tide_height) if tide_height is not None else None,
                float(temperature) if temperature is not None else None,
                wind_direction.strip(),
                lure.strip(),
                action.strip(),
                float(size) if size is not None else None
            )
            st.success("✅ 登録が完了しました")
            st.rerun()

    st.divider()
    st.subheader("登録済みデータ")

    # ---------- 編集フォーム（必要時だけ表示） ----------
    if st.session_state.edit_row:
        row = st.session_state.edit_row
        st.markdown(f"**✏️ 編集モード（ID: {row['id']}）**")

        with st.form("edit_form"):
            c1, c2 = st.columns(2)
            with c1:
                def_time = None
                if row.get("time"):
                    try:
                        def_time = datetime.strptime(row["time"], "%H:%M").time()
                    except ValueError:
                        pass
                time_e = st.time_input("時間", value=def_time, key=f"time_e_{row['id']}")
                # time = st.time_input("時間", value=datetime.now().time())  # ← 追加
                area_e = st.text_input("エリア", row["area"] or "")
                tide_list = ["大潮", "中潮", "小潮", "若潮", "長潮"]
                idx = tide_list.index(row["tide_type"]) if row["tide_type"] in tide_list else 1
                tide_type_e = st.selectbox("潮回り", tide_list, index=idx)
                temperature_e = st.number_input(
                    "気温 (℃)", value=float(row["temperature"]) if row["temperature"] is not None else 0.0,
                    step=0.1, format="%.1f"
                )

            with c2:
                tide_height = st.number_input("潮位 (cm)", step=1, min_value=0)  # ← 追加
                wind_direction_e = st.text_input("風向", row["wind_direction"] or "")
                lure_e = st.text_input("ルアー", row["lure"] or "")
                action_e = st.text_input("アクション", row["action"] or "")
                size_e = st.number_input(
                        "サイズ (cm)",
                        value=int(row["size"]) if row["size"] is not None else 0,
                        step=1,
                        min_value=0
                    )

            col_ok, col_cancel = st.columns(2)
            update = col_ok.form_submit_button("更新")
            cancel = col_cancel.form_submit_button("キャンセル")

            # （右側カラム）
            tide_height_e = st.number_input(
                "潮位 (cm)",
                value=float(row["tide_height"]) if row["tide_height"] is not None else 0.0,
                step=1.0
            )

            if update:
                time_str = time_e.strftime("%H:%M") if time_e else "00:00"
                
                update_row(
                int(row["id"]),
                area_e.strip(),
                tide_type_e,
                float(temperature_e),
                wind_direction_e.strip(),
                lure_e.strip(),
                action_e.strip(),
                float(size_e),
                float(tide_height_e) if tide_height_e is not None else None,
                time=time_str
            )
                st.success("✏️ 更新が完了しました")
                st.session_state.edit_row = None
                st.rerun()


            if cancel:
                st.info("✋ 編集をキャンセルしました")
                st.session_state.edit_row = None
                st.rerun()

    # ---------- 一覧表示 & 行ごとの操作 ----------
    df = fetch_all()
    df_sorted = _sort_logs(df)
    st.dataframe(df_sorted, use_container_width=True)

    if df.empty:
        st.info("まだデータがありません。上のフォームから登録してください。")
    else:
        for _, r in df.iterrows():
            # 列構成：データ表示（広め）＋ 編集ボタン＋ 削除ボタン
            c1, c2, c3 = st.columns([8, 1, 1])
            with c1:
                st.markdown(
                    f"📅 **{r['date']}** {r['time'] or ''}　"
                    f"🎣 **{r['area']}**　🌊 {r['tide_type']} "
                    f"({r['tide_height'] if r['tide_height'] is not None else '-'}cm)　"
                    f"🌡️ {r['temperature'] if r['temperature'] is not None else '-'}℃　"
                    f"🍃 {r['wind_direction'] or '-'}　"
                    f"🪝 {r['lure'] or '-'}／{r['action'] or '-'}　"
                    f"📏 {int(r['size']) if r['size'] is not None else '-'}cm"
                )
            with c2:
                if st.button("✏️", key=f"edit_{r['id']}"):
                    st.session_state.edit_row = dict(r)
                    st.rerun()
            with c3:
                if st.button("🗑️", key=f"del_{r['id']}"):
                    delete_row(int(r["id"]))
                    st.warning("🗑️ 削除が完了しました")
                    st.rerun()
            st.divider()

with tab2:
    show_analysis()