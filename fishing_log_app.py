# fishing_log_app.py
# import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from analysis_tab import show_analysis
from db_utils_gsheets import fetch_all, insert_row, update_row, delete_row
import urllib.parse
from datetime import datetime, date as Date
import requests  # ← 追加

# fishing_log_app.py の上の方に追加
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

@st.cache_data(show_spinner=False)
def fetch_tide736_day(pc: int, hc: int, target_date: Date):
    """
    指定した港(pc/hc)・日付の 1日分の潮位データを tide736 から取得する
    """
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
    tide_list = chart["tide"]  # [{time: "HH:MM", cm: float, ...}, ...]
    return tide_list


def get_tide_height_for_time(pc: int, hc: int, target_date: Date, t: datetime.time):
    """
    指定日時に一番近い tide データを拾って (cm, データ側の時刻文字列) を返す
    """
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

    return float(best["cm"]), best["time"]  # (潮位cm, 何時のデータか)

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
        "rg": "day",      # 1日分
        "w": width,
        "h": height,
        # 以下は見た目系のオプション（お好みで）
        "lc": "blue",     # 線の色 (line color)
        "gcs": "cyan",    # グラデーション start
        "gcf": "blue",    # グラデーション finish
        "ld": "on",       # 凡例 on/off
        "ttd": "on",      # 潮位テーブル表示 on/off
        "tsmd": "on",     # 太陽・月情報テーブル on/off
    }
    return base + "?" + urllib.parse.urlencode(params)


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
                    "temperature","wind_direction","lure","action","size","image_url1","image_url2","image_url3",]
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
            "image_url1": st.column_config.LinkColumn("画像1", display_text="1枚目"),
            "image_url2": st.column_config.LinkColumn("画像2", display_text="2枚目"),
            "image_url3": st.column_config.LinkColumn("画像3", display_text="3枚目"),
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
            st.write(f"ID: {int(row['id'])}　/　日付: {row['date']}")

            # --- 画像まわり（最大3枚） ---
            existing_image_url1 = row.get("image_url1", "")
            existing_image_url2 = row.get("image_url2", "")
            existing_image_url3 = row.get("image_url3", "")

            # 新しい画像アップロード（各スロットごと）
            st.markdown("##### 📸 画像")
            c_img1, c_img2, c_img3 = st.columns(3)

            with c_img1:
                st.caption("画像1")
                image_file1 = st.file_uploader(
                    "変更する場合のみ",
                    type=["jpg", "jpeg", "png"],
                    key=f"edit_image1_{row['id']}",
                )
                delete_image1 = False
                if existing_image_url1:
                    st.image(existing_image_url1, caption="現在の画像1", use_column_width=True)
                    delete_image1 = st.checkbox(
                        "この画像1を削除する",
                        value=False,
                        key=f"delete_image1_{row['id']}",
                    )

            with c_img2:
                st.caption("画像2")
                image_file2 = st.file_uploader(
                    "変更する場合のみ",
                    type=["jpg", "jpeg", "png"],
                    key=f"edit_image2_{row['id']}",
                )
                delete_image2 = False
                if existing_image_url2:
                    st.image(existing_image_url2, caption="現在の画像2", use_column_width=True)
                    delete_image2 = st.checkbox(
                        "この画像2を削除する",
                        value=False,
                        key=f"delete_image2_{row['id']}",
                    )

            with c_img3:
                st.caption("画像3")
                image_file3 = st.file_uploader(
                    "変更する場合のみ",
                    type=["jpg", "jpeg", "png"],
                    key=f"edit_image3_{row['id']}",
                )
                delete_image3 = False
                if existing_image_url3:
                    st.image(existing_image_url3, caption="現在の画像3", use_column_width=True)
                    delete_image3 = st.checkbox(
                        "この画像3を削除する",
                        value=False,
                        key=f"delete_image3_{row['id']}",
                    )

            # --- テキスト系の編集項目 ---
            c1, c2 = st.columns(2)
            with c1:
                area_e = st.text_input("エリア", value=str(row["area"] or ""))
                tide_e = st.selectbox(
                    "潮回り",
                    ["大潮", "中潮", "小潮", "若潮", "長潮"],
                    index=["大潮", "中潮", "小潮", "若潮", "長潮"].index(str(row["tide_type"]))
                    if str(row["tide_type"]) in ["大潮", "中潮", "小潮", "若潮", "長潮"]
                    else 1,
                )

                # 時間：文字列 "HH:MM" → time型
                def_time = None
                try:
                    if isinstance(row["time"], str) and row["time"]:
                        def_time = datetime.strptime(row["time"], "%H:%M").time()
                except Exception:
                    pass
                time_e = st.time_input("時間", value=def_time, key=f"time_e_{int(row['id'])}")

            with c2:
                temp_e = st.number_input(
                    "気温(℃)",
                    value=float(row["temperature"]) if pd.notna(row["temperature"]) else 0.0,
                    step=0.1,
                    format="%.1f",
                )
                tide_h_e = st.number_input(
                    "潮位(cm)",
                    value=float(row["tide_height"]) if pd.notna(row["tide_height"]) else 0.0,
                    step=1.0,
                )
                wind_e = st.text_input("風向", value=str(row["wind_direction"] or ""))
                lure_e = st.text_input("ルアー", value=str(row["lure"] or ""))
                act_e = st.text_input("アクション", value=str(row["action"] or ""))
                size_e = st.number_input(
                    "サイズ(cm)",
                    value=int(row["size"]) if pd.notna(row["size"]) else 0,
                    step=1,
                    min_value=0,
                )

            col_upd, col_cancel = st.columns([1, 1])
            do_update = col_upd.form_submit_button("更新")
            cancel = col_cancel.form_submit_button("キャンセル")

            if do_update:
                from db_utils_gsheets import update_row, upload_image_to_cloudinary

                time_str = time_e.strftime("%H:%M") if time_e else "00:00"

                # --- 画像URLの決定（スロット1〜3） ---
                image_url1_arg = None
                image_url2_arg = None
                image_url3_arg = None

                # 画像1
                if delete_image1 and existing_image_url1:
                    image_url1_arg = ""  # 削除
                elif image_file1 is not None:
                    filename1 = f"{row['id']}_{row['date']}_1_{image_file1.name}"
                    image_url1_arg = upload_image_to_cloudinary(image_file1, filename1)

                # 画像2
                if delete_image2 and existing_image_url2:
                    image_url2_arg = ""  # 削除
                elif image_file2 is not None:
                    filename2 = f"{row['id']}_{row['date']}_2_{image_file2.name}"
                    image_url2_arg = upload_image_to_cloudinary(image_file2, filename2)

                # 画像3
                if delete_image3 and existing_image_url3:
                    image_url3_arg = ""  # 削除
                elif image_file3 is not None:
                    filename3 = f"{row['id']}_{row['date']}_3_{image_file3.name}"
                    image_url3_arg = upload_image_to_cloudinary(image_file3, filename3)

                # update_row 呼び出し用の kwargs を組み立て
                kwargs = dict(
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
                )

                # 画像は「変更があったスロットだけ」渡す
                if image_url1_arg is not None:
                    kwargs["image_url1"] = image_url1_arg
                if image_url2_arg is not None:
                    kwargs["image_url2"] = image_url2_arg
                if image_url3_arg is not None:
                    kwargs["image_url3"] = image_url3_arg

                update_row(**kwargs)

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

    # ==== ここからタイドグラフ ====
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

    # st.write("DEBUG tide URL:", tide_img_url)  # ← これ追加
    st.image(tide_img_url, use_column_width=True)
    # st.image("https://api.tide736.net/tide_image.php?pc=28&hc=9&yr=2025&mn=12&dy=11&rg=day&w=768&h=512&lc=blue&gcs=cyan&gcf=blue&ld=on&ttd=on&tsmd=on")
    st.caption("※データ元：tide736.net（日本沿岸736港の潮汐表）")
    st.divider()

    # ---------- 新規登録フォーム ----------
    st.caption("📝 新しい釣行データを入力してください")
    st.subheader("釣行データ新規入力")

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
            tide_height = st.number_input(
                "潮位 (cm)",
                step=1,
                min_value=0,
                key="log_tide_height",  # ← ここだけ追加
            )
            wind_direction = st.text_input("風向（例：北北東）")
            lure = st.text_input("ルアー（例：バクリースピン6）")
            action = st.text_input("アクション（例：スローリトリーブ）")

        image_files = st.file_uploader(
            "釣果写真（最大3枚まで）",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )

        # ボタンを2つ並べる
        btn_col1, btn_col2 = st.columns(2)
        reflect_tide = btn_col1.form_submit_button("潮位を反映")
        submitted    = btn_col2.form_submit_button("登録")

        # time は st.time_input(...) の戻り値（datetime.time or None）
        time_str = time.strftime("%H:%M") if time else "00:00"

        # ① 「潮位を反映」が押されたとき：APIを叩いて潮位欄を更新するだけ
        if reflect_tide:
            if not time:
                st.warning("先に時間を入力してください")
            else:
                try:
                    spot = TIDE736_PORTS[spot_name]  # 上のタイドグラフで選んだ港をそのまま使う
                    cm, base_time = get_tide_height_for_time(
                        spot["pc"],
                        spot["hc"],
                        tide_date,   # タイドグラフで選んだ日付
                        time,
                    )
                    st.session_state["log_tide_height"] = int(round(cm))
                    st.success(f"{base_time} の潮位 {cm:.1f} cm を反映しました")
                except Exception as e:
                    st.error(f"潮位の取得に失敗しました: {e}")

        # submitted = st.form_submit_button("登録")
        if submitted:
            image_url1 = image_url2 = image_url3 = None

            if image_files:
                from db_utils_gsheets import upload_image_to_cloudinary
                urls = []
                for i, f in enumerate(image_files[:3]):  # 最大3枚
                    filename = f"{date.strftime('%Y%m%d')}_{area}_{i+1}_{f.name}"
                    url = upload_image_to_cloudinary(f, filename)
                    urls.append(url)

                # 足りない分は None のまま
                if len(urls) > 0: image_url1 = urls[0]
                if len(urls) > 1: image_url2 = urls[1]
                if len(urls) > 2: image_url3 = urls[2]

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
                image_url1,
                image_url2,
                image_url3,
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