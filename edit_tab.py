# edit_tab.py
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime

def render_log_table_with_actions(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("データがありません。")
        return

    d = df.copy()
    d["date_dt"] = pd.to_datetime(d["date"], errors="coerce")
    d["time_dt"] = pd.to_datetime(d["time"], format="%H:%M", errors="coerce")
    d["size_num"] = pd.to_numeric(d["size"], errors="coerce")

    d = d.sort_values(by=["date_dt", "time_dt"], ascending=[False, True], na_position="last")

    display_cols = [
        "id","date","time","area","tide_type","tide_height",
        "temperature","wind_direction","lure","action","size",
        "image_url1","image_url2","image_url3",
    ]
    d = d[display_cols].reset_index(drop=True)
    d["編集"] = False
    d["削除"] = False
    d["プレビュー"] = False

    edited_df = st.data_editor(
        d,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key="log_table_editor",
        column_config={
            "編集": st.column_config.CheckboxColumn("編集", help="この行を編集します"),
            "削除": st.column_config.CheckboxColumn("削除", help="この行を削除します"),
            "プレビュー": st.column_config.CheckboxColumn("プレビュー", help="この行の画像を下で表示します"),
            "tide_height": st.column_config.NumberColumn("潮位(cm)", format="%.0f"),
            "temperature": st.column_config.NumberColumn("気温(℃)", format="%.1f"),
            "size": st.column_config.NumberColumn("サイズ(cm)", format="%.0f"),
            "image_url1": st.column_config.LinkColumn("画像1", display_text="1枚目"),
            "image_url2": st.column_config.LinkColumn("画像2", display_text="2枚目"),
            "image_url3": st.column_config.LinkColumn("画像3", display_text="3枚目"),
        },
    )

    edit_rows = edited_df.index[edited_df["編集"] == True].tolist()
    delete_rows = edited_df.index[edited_df["削除"] == True].tolist()
    preview_rows = edited_df.index[edited_df["プレビュー"] == True].tolist()

    # --- プレビュー ---
    if preview_rows:
        i = preview_rows[0]
        row = edited_df.loc[i]

        st.markdown("#### 画像プレビュー")
        c1, c2, c3 = st.columns(3)
        urls = [
            row.get("image_url1", ""),
            row.get("image_url2", ""),
            row.get("image_url3", ""),
        ]
        for idx, (url, col) in enumerate(zip(urls, [c1, c2, c3]), start=1):
            with col:
                if isinstance(url, str) and url.strip():
                    st.image(url, caption=f"画像{idx}", use_column_width=True)
                else:
                    st.caption(f"画像{idx}（なし）")

    # --- 編集 ---
    if edit_rows:
        i = edit_rows[0]
        row = edited_df.loc[i]

        st.markdown("#### ✏️ 編集")
        with st.form(f"edit_form_{int(row['id'])}"):
            st.write(f"ID: {int(row['id'])}　/　日付: {row['date']}")

            existing_image_url1 = row.get("image_url1", "")
            existing_image_url2 = row.get("image_url2", "")
            existing_image_url3 = row.get("image_url3", "")

            st.markdown("##### 📸 画像")
            c_img1, c_img2, c_img3 = st.columns(3)

            with c_img1:
                st.caption("画像1")
                image_file1 = st.file_uploader("変更する場合のみ", type=["jpg", "jpeg", "png"], key=f"edit_image1_{row['id']}")
                delete_image1 = False
                if existing_image_url1:
                    st.image(existing_image_url1, caption="現在の画像1", use_column_width=True)
                    delete_image1 = st.checkbox("この画像1を削除する", value=False, key=f"delete_image1_{row['id']}")

            with c_img2:
                st.caption("画像2")
                image_file2 = st.file_uploader("変更する場合のみ", type=["jpg", "jpeg", "png"], key=f"edit_image2_{row['id']}")
                delete_image2 = False
                if existing_image_url2:
                    st.image(existing_image_url2, caption="現在の画像2", use_column_width=True)
                    delete_image2 = st.checkbox("この画像2を削除する", value=False, key=f"delete_image2_{row['id']}")

            with c_img3:
                st.caption("画像3")
                image_file3 = st.file_uploader("変更する場合のみ", type=["jpg", "jpeg", "png"], key=f"edit_image3_{row['id']}")
                delete_image3 = False
                if existing_image_url3:
                    st.image(existing_image_url3, caption="現在の画像3", use_column_width=True)
                    delete_image3 = st.checkbox("この画像3を削除する", value=False, key=f"delete_image3_{row['id']}")

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
                # importはここで（循環を避ける）
                from db_utils_gsheets import update_row, upload_image_to_cloudinary

                time_str = time_e.strftime("%H:%M") if time_e else "00:00"

                image_url1_arg = None
                image_url2_arg = None
                image_url3_arg = None

                if delete_image1 and existing_image_url1:
                    image_url1_arg = ""
                elif image_file1 is not None:
                    filename1 = f"{row['id']}_{row['date']}_1_{image_file1.name}"
                    image_url1_arg = upload_image_to_cloudinary(image_file1, filename1)

                if delete_image2 and existing_image_url2:
                    image_url2_arg = ""
                elif image_file2 is not None:
                    filename2 = f"{row['id']}_{row['date']}_2_{image_file2.name}"
                    image_url2_arg = upload_image_to_cloudinary(image_file2, filename2)

                if delete_image3 and existing_image_url3:
                    image_url3_arg = ""
                elif image_file3 is not None:
                    filename3 = f"{row['id']}_{row['date']}_3_{image_file3.name}"
                    image_url3_arg = upload_image_to_cloudinary(image_file3, filename3)

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

    # --- 削除 ---
    if delete_rows:
        ids = [int(edited_df.loc[i, "id"]) for i in delete_rows if pd.notna(edited_df.loc[i, "id"])]
        with st.expander(f"🗑️ 削除の確認（{len(ids)}件）", expanded=True):
            st.write("削除対象ID:", ids)
            col_yes, col_no = st.columns([1, 1])
            if col_yes.button("削除を実行", type="primary"):
                from db_utils_gsheets import delete_row
                for _id in ids:
                    delete_row(_id)
                st.success(f"{len(ids)}件を削除しました")
                st.rerun()
            if col_no.button("やめる"):
                st.info("削除をキャンセルしました")
                st.rerun()


def render_edit_tab(
    *,
    TIDE736_PORTS: dict,
    fetch_all,
    insert_row,
    get_tide_height_for_time,
):
    st.caption("📝 新規入力・編集・削除・画像プレビュー（データ編集）")
    st.subheader("釣行データ新規入力")

    # チェックタブで選択している港（なければ先頭）
    spot_name = st.session_state.get("tide736_spot", list(TIDE736_PORTS.keys())[0])

    if "log_tide_height" not in st.session_state:
        st.session_state["log_tide_height"] = 0

    with st.form("log_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            date = st.date_input("日付", datetime.now())
            time = st.time_input("時間", value=None)
            area = st.text_input("エリア（例：水の広場公園）")
            temperature = st.number_input("気温 (℃)", step=0.1, format="%.1f")
            size = st.number_input("サイズ (cm)", step=1, min_value=0)
        with c2:
            tide_type = st.selectbox("潮回り", ["大潮", "中潮", "小潮", "若潮", "長潮"])
            tide_height = st.number_input(
                "潮位 (cm)",
                step=1,
                min_value=0,
                value=int(st.session_state.get("log_tide_height", 0)),
            )
            wind_direction = st.text_input("風向（例：北北東）")
            lure = st.text_input("ルアー（例：バクリースピン6）")
            action = st.text_input("アクション（例：スローリトリーブ）")

        image_files = st.file_uploader(
            "釣果写真（最大3枚まで）",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )

        btn_col1, btn_col2 = st.columns(2)
        reflect_tide = btn_col1.form_submit_button("潮位を反映")
        submitted = btn_col2.form_submit_button("登録")

        time_str = time.strftime("%H:%M") if time else "00:00"

        if reflect_tide:
            if not time:
                st.warning("先に時間を入力してください")
            else:
                try:
                    spot = TIDE736_PORTS[spot_name]
                    cm, base_time = get_tide_height_for_time(spot["pc"], spot["hc"], date, time)
                    st.session_state["log_tide_height"] = int(round(cm))
                    st.success(f"{base_time} の潮位 {cm:.1f} cm を反映しました")
                except Exception as e:
                    st.error(f"潮位の取得に失敗しました: {e}")

        if submitted:
            image_url1 = image_url2 = image_url3 = None

            if image_files:
                from db_utils_gsheets import upload_image_to_cloudinary
                urls = []
                for i, f in enumerate(image_files[:3]):
                    filename = f"{date.strftime('%Y%m%d')}_{area}_{i+1}_{f.name}"
                    url = upload_image_to_cloudinary(f, filename)
                    urls.append(url)
                if len(urls) > 0: image_url1 = urls[0]
                if len(urls) > 1: image_url2 = urls[1]
                if len(urls) > 2: image_url3 = urls[2]

            insert_row(
                date.strftime("%Y-%m-%d"),
                time_str,
                area.strip(),
                tide_type,
                float(tide_height),
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

    df = fetch_all()
    render_log_table_with_actions(df)
