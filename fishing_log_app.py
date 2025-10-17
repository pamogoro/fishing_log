# fishing_log_app.py
import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from analysis_tab import show_analysis

st.set_page_config(page_title="釣行ログ管理", page_icon="🎣", layout="centered")

DB_PATH = "fishing_log.db"

# ---------- DBユーティリティ ----------
def get_conn():
    # 操作ごとに新規接続（ロック回避 & Streamlit再実行に強い）
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fishing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            area TEXT,
            tide_type TEXT,
            temperature REAL,
            wind_direction TEXT,
            lure TEXT,
            action TEXT,
            size REAL,
            time TEXT,
            tide_height REAL
        )
        """)
        conn.commit()

def fetch_all():
    with get_conn() as conn:
        return pd.read_sql("SELECT * FROM fishing_log ORDER BY date DESC, id DESC", conn)

def insert_row(date, time, area, tide_type, tide_height, temperature, wind_direction, lure, action, size):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO fishing_log
            (date, time, area, tide_type, tide_height, temperature, wind_direction, lure, action, size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, time, area, tide_type, tide_height, temperature, wind_direction, lure, action, size))
        conn.commit()

def update_row(row_id, area, tide_type, temperature, wind_direction, lure, action, size, tide_height, time):
    with get_conn() as conn:
        conn.execute("""
            UPDATE fishing_log
            SET area=?, tide_type=?, temperature=?, wind_direction=?, lure=?, action=?, size=?, tide_height=?, time=?
            WHERE id=?
        """, (area, tide_type, temperature, wind_direction, lure, action, size, row_id, tide_height, time))
        conn.commit()

def delete_row(row_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM fishing_log WHERE id=?", (row_id,))
        conn.commit()

tab1, tab2 = st.tabs(["🎣 釣行データ", "📈 分析"])

with tab1:
    # ---------- 初期化 ----------
    init_db()
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
                time = st.time_input("時間", value=datetime.now().time())  # ← 追加
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

            if update:
                update_row(
                    int(row["id"]),
                    area_e.strip(),
                    tide_type_e,
                    float(temperature_e),
                    wind_direction_e.strip(),
                    lure_e.strip(),
                    action_e.strip(),
                    float(size_e),
                    float(tide_height) if tide_height is not None else None,
                    time.strftime("%H:%M")
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