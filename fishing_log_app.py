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

# 既存: df = fetch_all() の後に呼ぶ
def render_log_table_with_actions(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("データがありません。")
        return

    # --- 型整形（ソート用） ---
    d = df.copy()
    d["date_dt"] = pd.to_datetime(d["date"], errors="coerce")
    d["time_dt"] = pd.to_datetime(d["time"], format="%H:%M", errors="coerce")
    d["size_num"] = pd.to_numeric(d["size"], errors="coerce")

    # 初期は「日付の新しい順」
    d = d.sort_values(by=["date_dt","time_dt"], ascending=[False, True], na_position="last")

    # 表示用の列順に戻し、アクション列を付与
    display_cols = ["id","date","time","area","tide_type","tide_height",
                    "temperature","wind_direction","lure","action","size","image_url"]
    d = d[display_cols].reset_index(drop=True)
    d["編集"] = False
    d["削除"] = False

    # --- データエディタ（表内でチェック可能） ---
    edited_df = st.data_editor(
        d,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "編集": st.column_config.CheckboxColumn("編集", help="この行を編集します"),
            "削除": st.column_config.CheckboxColumn("削除", help="この行を削除します"),
            # 主要列の見出し整形（任意）
            "tide_height": st.column_config.NumberColumn("潮位(cm)", format="%.0f"),
            "temperature": st.column_config.NumberColumn("気温(℃)", format="%.1f"),
            "size":        st.column_config.NumberColumn("サイズ(cm)", format="%.0f"),
        "image_url": st.column_config.TextColumn("画像URL", disabled=True, width="small"),  # 表示だけ or 後で非表示にしてもOK
        },
    )

    # --- 編集対象（複数チェックされていても先頭だけ扱う） ---
    edit_rows = edited_df.index[edited_df["編集"] == True].tolist()
    delete_rows = edited_df.index[edited_df["削除"] == True].tolist()

    # ----- 編集フロー -----
    if edit_rows:
        i = edit_rows[0]
        row = edited_df.loc[i]

        st.markdown("#### ✏️ 編集")
        c1, c2 = st.columns(2)
        with st.form(f"edit_form_{int(row['id'])}"):
            # 既存値→ウィジェット
            # 日付はそのまま表示（編集対象に含めないなら読み取り専用で）
            st.write(f"ID: {int(row['id'])}　/　日付: {row['date']}")

            # 既存の URL（編集後、画像未選択ならこれを使う）
            existing_image_url = row.get("image_url", "")

            # 新しい画像選択（任意）
            image_file = st.file_uploader(
                "釣果写真（変更する場合のみアップロード）",
                type=["jpg", "jpeg", "png"],
                key=f"edit_image_{row['id']}"
            )

            # 既存の写真がある場合はプレビュー表示
            if existing_image_url:
                st.image(existing_image_url, caption="現在の画像", use_column_width=True)


            with c1:
                area_e = st.text_input("エリア", value=str(row["area"] or ""))
                tide_e = st.selectbox("潮回り", ["大潮","中潮","小潮","若潮","長潮"],
                                      index=["大潮","中潮","小潮","若潮","長潮"].index(str(row["tide_type"])) if str(row["tide_type"]) in ["大潮","中潮","小潮","若潮","長潮"] else 1)

                # 時間：文字列 "HH:MM" → time型
                def_time = None
                try:
                    if isinstance(row["time"], str) and row["time"]:
                        def_time = datetime.strptime(row["time"], "%H:%M").time()
                except Exception:
                    pass
                time_e = st.time_input("時間", value=def_time, key=f"time_e_{int(row['id'])}")

            with c2:
                temp_e = st.number_input("気温(℃)", value=float(row["temperature"]) if pd.notna(row["temperature"]) else 0.0, step=0.1, format="%.1f")
                tide_h_e = st.number_input("潮位(cm)", value=float(row["tide_height"]) if pd.notna(row["tide_height"]) else 0.0, step=1.0)
                wind_e = st.text_input("風向", value=str(row["wind_direction"] or ""))
                lure_e = st.text_input("ルアー", value=str(row["lure"] or ""))
                act_e  = st.text_input("アクション", value=str(row["action"] or ""))
                size_e = st.number_input("サイズ(cm)", value=int(row["size"]) if pd.notna(row["size"]) else 0, step=1, min_value=0)

            col_upd, col_cancel = st.columns([1,1])
            do_update = col_upd.form_submit_button("更新")
            cancel = col_cancel.form_submit_button("キャンセル")

            if do_update:
                from db_utils_gsheets import update_row, upload_image_to_drive
                time_str = time_e.strftime("%H:%M") if time_e else "00:00"

                # ここで初めて image_url を決める
                if image_file is not None:
                    filename = f"{row['id']}_{row['date']}_{image_file.name}"
                    image_url = upload_image_to_drive(image_file, filename)
                else:
                    image_url = existing_image_url

                update_row(
                    row_id=int(row["id"]),
                    area=area_e.strip(),
                    tide_type=tide_e,
                    temperature=float(temp_e),
                    wind_direction=wind_e.strip(),
                    lure=lure_e.strip(),
                    action=act_e.strip(),
                    size=int(size_e),
                    tide_height=float(tide_h_e),
                    time=time_str,
                    image_url=image_url,
                )
                st.success("更新しました")
                st.rerun()


            if cancel:
                st.info("編集をキャンセルしました")
                st.rerun()

    # ----- 削除フロー -----
    if delete_rows:
        ids = [int(edited_df.loc[i, "id"]) for i in delete_rows if pd.notna(edited_df.loc[i, "id"])]
        with st.expander(f"🗑️ 削除の確認（{len(ids)}件）", expanded=True):
            st.write("削除対象ID:", ids)
            col_yes, col_no = st.columns([1,1])
            if col_yes.button("削除を実行", type="primary"):
                from db_utils_gsheets import delete_row
                for _id in ids:
                    delete_row(_id)
                st.success(f"{len(ids)}件を削除しました")
                st.rerun()
            if col_no.button("やめる"):
                st.info("削除をキャンセルしました")
                st.rerun()


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

        # 🔽 ここ追加：1登録につき1枚の写真
        image_file = st.file_uploader(
            "釣果写真（1枚まで）",
            type=["jpg", "jpeg", "png"]
        )

        # time は st.time_input(...) の戻り値（datetime.time or None）
        time_str = time.strftime("%H:%M") if time else "00:00"

        submitted = st.form_submit_button("登録")
        if submitted:
            image_url = None
            if image_file is not None:
                from db_utils_gsheets import upload_image_to_drive
                filename = f"{date.strftime('%Y%m%d')}_{area}_{image_file.name}"
                image_url = upload_image_to_drive(image_file, filename)
            
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
                float(size) if size is not None else None,
                image_url,
            )
            st.success("✅ 登録が完了しました")
            st.rerun()

    st.divider()
    st.subheader("登録済みデータ")

    # ---------- 編集フォーム（必要時だけ表示） ----------
    # if st.session_state.edit_row:
    #     row = st.session_state.edit_row
    #     st.markdown(f"**✏️ 編集モード（ID: {row['id']}）**")

    #     with st.form("edit_form"):
    #         c1, c2 = st.columns(2)
    #         with c1:
    #             def_time = None
    #             if row.get("time"):
    #                 try:
    #                     def_time = datetime.strptime(row["time"], "%H:%M").time()
    #                 except ValueError:
    #                     pass
    #             time_e = st.time_input("時間", value=def_time, key=f"time_e_{row['id']}")
    #             # time = st.time_input("時間", value=datetime.now().time())  # ← 追加
    #             area_e = st.text_input("エリア", row["area"] or "")
    #             tide_list = ["大潮", "中潮", "小潮", "若潮", "長潮"]
    #             idx = tide_list.index(row["tide_type"]) if row["tide_type"] in tide_list else 1
    #             tide_type_e = st.selectbox("潮回り", tide_list, index=idx)
    #             temperature_e = st.number_input(
    #                 "気温 (℃)", value=float(row["temperature"]) if row["temperature"] is not None else 0.0,
    #                 step=0.1, format="%.1f"
    #             )

    #         with c2:
    #             tide_height = st.number_input("潮位 (cm)", step=1, min_value=0)  # ← 追加
    #             wind_direction_e = st.text_input("風向", row["wind_direction"] or "")
    #             lure_e = st.text_input("ルアー", row["lure"] or "")
    #             action_e = st.text_input("アクション", row["action"] or "")
    #             size_e = st.number_input(
    #                     "サイズ (cm)",
    #                     value=int(row["size"]) if row["size"] is not None else 0,
    #                     step=1,
    #                     min_value=0
    #                 )

    #         col_ok, col_cancel = st.columns(2)
    #         update = col_ok.form_submit_button("更新")
    #         cancel = col_cancel.form_submit_button("キャンセル")

    #         # （右側カラム）
    #         tide_height_e = st.number_input(
    #             "潮位 (cm)",
    #             value=float(row["tide_height"]) if row["tide_height"] is not None else 0.0,
    #             step=1.0
    #         )

    #         if update:
    #             time_str = time_e.strftime("%H:%M") if time_e else "00:00"
                
    #             update_row(
    #             int(row["id"]),
    #             area_e.strip(),
    #             tide_type_e,
    #             float(temperature_e),
    #             wind_direction_e.strip(),
    #             lure_e.strip(),
    #             action_e.strip(),
    #             float(size_e),
    #             float(tide_height_e) if tide_height_e is not None else None,
    #             time=time_str
    #         )
    #             st.success("✏️ 更新が完了しました")
    #             st.session_state.edit_row = None
    #             st.rerun()


    #         if cancel:
    #             st.info("✋ 編集をキャンセルしました")
    #             st.session_state.edit_row = None
    #             st.rerun()

    # ---------- 一覧表示 & 行ごとの操作 ----------
    df = fetch_all()
    render_log_table_with_actions(df)


with tab2:
    show_analysis()