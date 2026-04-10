# edit_tab.py
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime

def render_blog_detail_list(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("データがありません。")
        return
    
    if "blog_show_images" not in st.session_state:
        st.session_state["blog_show_images"] = False

    # st.warning("✅ edit_tab.render_edit_tab が呼ばれています（デバッグ表示）")
    # 並び順：日付 desc、時間 asc（近い釣行がまとまる）
    d = df.copy()
    d["date_dt"] = pd.to_datetime(d["date"], errors="coerce")
    d["time_dt"] = pd.to_datetime(d["time"], format="%H:%M", errors="coerce")
    d = d.sort_values(by=["date_dt", "time_dt"], ascending=[False, True], na_position="last")

    st.subheader("📚 詳細一覧（ブログ形式）")

    # 表示件数を絞れるとスマホで軽い＆探しやすい
    c1, c2, c3 = st.columns(3)
    with c1:
        limit = st.selectbox("表示件数", [10, 20, 50, 100], index=1, key="blog_limit")
    with c2:
        only_catch = st.toggle("釣れた記録だけ", value=False, key="blog_only_catch")
    with c3:
        show_images = st.toggle("画像を表示", key="blog_show_images")

    if only_catch:
        d["size_num"] = pd.to_numeric(d["size"], errors="coerce").fillna(0)
        d = d[d["size_num"] > 0]

    d = d.head(int(limit))

    # 日付ごとにまとまるようにグルーピング
    d["date_str"] = d["date_dt"].dt.strftime("%Y-%m-%d")
    for date_str, g in d.groupby("date_str", sort=False):
        st.markdown(f"### 📅 {date_str}")
        for _, row in g.iterrows():
            _render_one_blog_card(row, show_images=show_images)
        st.divider()


def _render_one_blog_card(row: pd.Series, show_images: bool = True):
    # 見出し（サッと把握）
    time = row.get("time") or "—"
    area = row.get("area") or "—"
    size = row.get("size")
    size_txt = f"{int(size)}cm" if pd.notna(size) and str(size).strip() != "" else "—"

    title = f"🕒 {time} / 📍 {area} / 🎣 {size_txt}"
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.caption(f"ID: {int(row['id'])}" if pd.notna(row.get("id")) else "")

        # 画像（縦でも横でもOK）
        if show_images:
            urls = [row.get("image_url1", ""), row.get("image_url2", ""), row.get("image_url3", "")]
            urls = [u for u in urls if isinstance(u, str) and u.strip()]
            if urls:
                # スマホでも見やすいように横並びより「1枚ずつ」優先
                for i, u in enumerate(urls, start=1):
                    st.image(u, caption=f"画像{i}", use_container_width=True)
            else:
                st.caption("📷 画像なし")

        # 情報（見やすく2列）
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"🌊 潮回り：{row.get('tide_type') or '—'}")
            st.write(f"📏 潮位：{_fmt_num(row.get('tide_height'), 'cm', digits=0)}")
            st.write(f"🌡 気温：{_fmt_num(row.get('temperature'), '℃', digits=1)}")
        with c2:
            st.write(f"🧭 風向：{row.get('wind_direction') or '—'}")
            st.write(f"🪝 ルアー：{row.get('lure') or '—'}")
            st.write(f"🎮 アクション：{row.get('action') or '—'}")

        rid = int(pd.to_numeric(row["id"], errors="coerce"))
        if st.button("✏️ このレコードを編集", key=f"blog_edit_{rid}"):
            st.session_state["jump_edit_id"] = rid
            st.rerun()



def _fmt_num(v, unit: str, digits: int = 0) -> str:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return "—"
        f = float(v)
        fmt = f"{{:.{digits}f}}"
        return fmt.format(f) + f" {unit}"
    except Exception:
        return "—"

def render_add_form(*, TIDE736_PORTS=None, insert_row=None, get_tide_height_for_time=None):
    st.subheader("➕ 新規追加")

    if insert_row is None:
        st.warning("追加関数が見つからないため、新規追加フォームを表示できません。")
        return

    from db_utils_gsheets import upload_image_to_cloudinary

    if "add_image_uploader_nonce" not in st.session_state:
        st.session_state["add_image_uploader_nonce"] = 0

    uploader_nonce = st.session_state["add_image_uploader_nonce"]
    port_names = list((TIDE736_PORTS or {}).keys())

    with st.form("add_log_form"):
        c1, c2 = st.columns(2)
        with c1:
            date_v = st.date_input("日付", value=datetime.now().date(), key="add_date")
            area_v = st.text_input("エリア", key="add_area")
            tide_v = st.selectbox("潮回り", ["大潮", "中潮", "小潮", "若潮", "長潮"], index=1, key="add_tide")
            time_v = st.time_input(
                "時間",
                value=datetime.now().replace(second=0, microsecond=0).time(),
                key="add_time"
            )
        with c2:
            temp_v = st.number_input("気温(℃)", value=0.0, step=0.1, format="%.1f", key="add_temp")
            wind_v = st.text_input("風向", key="add_wind")
            lure_v = st.text_input("ルアー", key="add_lure")
            action_v = st.text_input("アクション", key="add_action")
            size_v = st.number_input("サイズ(cm) ※ボウズは0", min_value=0, value=0, step=1, key="add_size")

        st.markdown("#### 🌊 潮位")
        tide_height_manual = st.number_input(
            "潮位(cm) 手入力",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="add_tide_height_manual",
            help="自動取得しない場合は手入力してください。0のままでも登録できます。",
        )
        auto_tide = st.checkbox(
            "港と時刻から潮位を自動取得する",
            value=bool(port_names),
            disabled=not bool(port_names),
            key="add_auto_tide",
        )

        port_name = None
        if auto_tide and port_names:
            port_name = st.selectbox("潮位の基準港", options=port_names, index=0, key="add_tide_port")

        st.markdown("#### 📸 画像（任意）")
        ic1, ic2, ic3 = st.columns(3)
        
        with ic1:
            image_file1 = st.file_uploader(
                "画像1",
                type=["jpg", "jpeg", "png"],
                key=f"add_image1_{uploader_nonce}"
            )
        with ic2:
            image_file2 = st.file_uploader(
                "画像2",
                type=["jpg", "jpeg", "png"],
                key=f"add_image2_{uploader_nonce}"
            )
        with ic3:
            image_file3 = st.file_uploader(
                "画像3",
                type=["jpg", "jpeg", "png"],
                key=f"add_image3_{uploader_nonce}"
            )

        submitted = st.form_submit_button("追加する", type="primary")

    if not submitted:
        return

    area_clean = str(area_v).strip()
    if not area_clean:
        st.warning("エリアは必須です。")
        return

    time_str = time_v.strftime("%H:%M") if time_v else "00:00"

    tide_height_value = None
    if auto_tide and port_name and TIDE736_PORTS and get_tide_height_for_time is not None:
        try:
            port = TIDE736_PORTS[port_name]
            tide_height_value, matched_time = get_tide_height_for_time(
                pc=port["pc"],
                hc=port["hc"],
                target_date=date_v,
                t=time_v,
            )
            st.info(f"{port_name} の {matched_time} データから潮位 {float(tide_height_value):.0f}cm を採用しました。")
        except Exception as e:
            st.warning(f"潮位の自動取得に失敗したため、手入力値を使います: {e}")

    if tide_height_value is None:
        tide_height_value = float(tide_height_manual) if float(tide_height_manual) > 0 else None

    uploaded_urls = []
    for idx, image_file in enumerate([image_file1, image_file2, image_file3], start=1):
        if image_file is None:
            uploaded_urls.append(None)
            continue
        filename = f"new_{date_v.strftime('%Y%m%d')}_{idx}_{image_file.name}"
        uploaded_urls.append(upload_image_to_cloudinary(image_file, filename))

    try:
        insert_row(
            date=date_v.strftime("%Y-%m-%d"),
            time=time_str,
            area=area_clean,
            tide_type=tide_v,
            tide_height=tide_height_value,
            temperature=float(temp_v) if temp_v is not None else None,
            wind_direction=str(wind_v).strip() or None,
            lure=str(lure_v).strip() or None,
            action=str(action_v).strip() or None,
            size=float(size_v) if size_v is not None else None,
            image_url1=uploaded_urls[0],
            image_url2=uploaded_urls[1],
            image_url3=uploaded_urls[2],
        )
        st.success("新規追加しました")

        # フォーム初期化
        st.session_state["add_date"] = datetime.now().date()
        st.session_state["add_area"] = ""
        st.session_state["add_tide"] = "中潮"
        st.session_state["add_time"] = datetime.now().replace(second=0, microsecond=0).time()
        st.session_state["add_temp"] = 0.0
        st.session_state["add_wind"] = ""
        st.session_state["add_lure"] = ""
        st.session_state["add_action"] = ""
        st.session_state["add_size"] = 0
        st.session_state["add_tide_height_manual"] = 0.0
        st.session_state["add_auto_tide"] = bool(port_names)
        if port_names:
            st.session_state["add_tide_port"] = port_names[0]

        # file_uploader もキーを入れ替えて実質リセット
        st.session_state["add_image_uploader_nonce"] = st.session_state.get("add_image_uploader_nonce", 0) + 1

        st.rerun()
    except Exception as e:
        st.error(f"追加に失敗しました: {e}")

def render_edit_tab(*, TIDE736_PORTS=None, fetch_all=None, insert_row=None, get_tide_height_for_time=None, **_ignore):
    """
    fishing_log_app.py からキーワード引数付きで呼ばれても落ちない入口。
    いま使わない引数があってもOK（将来の拡張に強い）。
    """
    st.title("🎣 シーバス釣行ログ管理アプリ")
    st.caption("データ追加・編集・削除・画像のプレビュー")
    st.divider()
    st.header("📝 データ編集")

    if fetch_all is None:
        from db_utils_gsheets import fetch_all as _fetch_all
        fetch_all = _fetch_all

    df = fetch_all()

    # ① 新規追加
    render_add_form(
        TIDE736_PORTS=TIDE736_PORTS,
        insert_row=insert_row,
        get_tide_height_for_time=get_tide_height_for_time,
    )

    st.divider()

    # ② 一覧
    render_log_table_with_actions(df)

    st.divider()

    # ③ ブログ形式の詳細一覧
    render_blog_detail_list(df)


def _open_details_dialog(row: pd.Series, *, is_mobile: bool = True):
    """選択した1レコードの詳細（プレビュー/編集/削除）を “ポップアップ風” に表示する。
    st.dialog が無い場合は expander にフォールバックする。
    """

    def _render_body():
        st.caption(f"ID: {int(row['id'])} / {row.get('date','')} {row.get('time','')}")
        st.write(f"**エリア**：{row.get('area','')}")
        st.write(f"**サイズ**：{row.get('size','')} cm")

        tabs = st.tabs(["📸 プレビュー", "✏️ 編集", "🗑️ 削除"])

        # ----------------- プレビュー -----------------
        with tabs[0]:
            urls = [row.get("image_url1", ""), row.get("image_url2", ""), row.get("image_url3", "")]
            if is_mobile:
                for idx, url in enumerate(urls, start=1):
                    if isinstance(url, str) and url.strip():
                        st.image(url, caption=f"画像{idx}", use_container_width=True)
                    else:
                        st.caption(f"画像{idx}（なし）")
            else:
                c1, c2, c3 = st.columns(3)
                for idx, (url, col) in enumerate(zip(urls, [c1, c2, c3]), start=1):
                    with col:
                        if isinstance(url, str) and url.strip():
                            st.image(url, caption=f"画像{idx}", use_container_width=True)
                        else:
                            st.caption(f"画像{idx}（なし）")

        # ----------------- 編集 -----------------
        with tabs[1]:
            from db_utils_gsheets import update_row, upload_image_to_cloudinary

            existing_image_url1 = row.get("image_url1", "")
            existing_image_url2 = row.get("image_url2", "")
            existing_image_url3 = row.get("image_url3", "")

            with st.form(f"edit_form_dialog_{int(row['id'])}"):
                st.subheader("📝 本文")

                # time のデフォルト
                def_time = None
                try:
                    if isinstance(row.get("time"), str) and row.get("time"):
                        def_time = datetime.strptime(row.get("time"), "%H:%M").time()
                except Exception:
                    pass

                if is_mobile:
                    area_e = st.text_input("エリア", value=str(row.get("area", "") or ""))
                    tide_e = st.selectbox(
                        "潮回り",
                        ["大潮", "中潮", "小潮", "若潮", "長潮"],
                        index=["大潮", "中潮", "小潮", "若潮", "長潮"].index(str(row.get("tide_type", "中潮")))
                        if str(row.get("tide_type")) in ["大潮", "中潮", "小潮", "若潮", "長潮"]
                        else 1,
                    )
                    time_e = st.time_input("時間", value=def_time, key=f"dialog_time_e_{int(row['id'])}")

                    temp_e = st.number_input(
                        "気温(℃)",
                        value=float(row.get("temperature")) if pd.notna(row.get("temperature")) else 0.0,
                        step=0.1,
                        format="%.1f",
                    )
                    tide_h_e = st.number_input(
                        "潮位(cm)",
                        value=float(row.get("tide_height")) if pd.notna(row.get("tide_height")) else 0.0,
                        step=1.0,
                    )
                    wind_e = st.text_input("風向", value=str(row.get("wind_direction", "") or ""))
                    lure_e = st.text_input("ルアー", value=str(row.get("lure", "") or ""))
                    act_e = st.text_input("アクション", value=str(row.get("action", "") or ""))
                    size_e = st.number_input(
                        "サイズ(cm)",
                        value=int(row.get("size")) if pd.notna(row.get("size")) else 0,
                        step=1,
                        min_value=0,
                    )
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        area_e = st.text_input("エリア", value=str(row.get("area", "") or ""))
                        tide_e = st.selectbox(
                            "潮回り",
                            ["大潮", "中潮", "小潮", "若潮", "長潮"],
                            index=["大潮", "中潮", "小潮", "若潮", "長潮"].index(str(row.get("tide_type", "中潮")))
                            if str(row.get("tide_type")) in ["大潮", "中潮", "小潮", "若潮", "長潮"]
                            else 1,
                        )
                        time_e = st.time_input("時間", value=def_time, key=f"dialog_time_e_{int(row['id'])}")
                    with c2:
                        temp_e = st.number_input(
                            "気温(℃)",
                            value=float(row.get("temperature")) if pd.notna(row.get("temperature")) else 0.0,
                            step=0.1,
                            format="%.1f",
                        )
                        tide_h_e = st.number_input(
                            "潮位(cm)",
                            value=float(row.get("tide_height")) if pd.notna(row.get("tide_height")) else 0.0,
                            step=1.0,
                        )
                        wind_e = st.text_input("風向", value=str(row.get("wind_direction", "") or ""))
                        lure_e = st.text_input("ルアー", value=str(row.get("lure", "") or ""))
                        act_e = st.text_input("アクション", value=str(row.get("action", "") or ""))
                        size_e = st.number_input(
                            "サイズ(cm)",
                            value=int(row.get("size")) if pd.notna(row.get("size")) else 0,
                            step=1,
                            min_value=0,
                        )
                st.subheader("📸 画像")

                if is_mobile:
                    cols = [st.container(), st.container(), st.container()]
                else:
                    cols = list(st.columns(3))

                # --- slot 1 ---
                with cols[0]:
                    st.caption("画像1")
                    image_file1 = st.file_uploader(
                        "変更する場合のみ",
                        type=["jpg", "jpeg", "png"],
                        key=f"dialog_edit_image1_{row['id']}",
                    )
                    delete_image1 = False
                    if existing_image_url1:
                        st.image(existing_image_url1, caption="現在の画像1", use_container_width=True)
                        delete_image1 = st.checkbox(
                            "この画像1を削除する",
                            value=False,
                            key=f"dialog_delete_image1_{row['id']}",
                        )

                # --- slot 2 ---
                with cols[1]:
                    st.caption("画像2")
                    image_file2 = st.file_uploader(
                        "変更する場合のみ",
                        type=["jpg", "jpeg", "png"],
                        key=f"dialog_edit_image2_{row['id']}",
                    )
                    delete_image2 = False
                    if existing_image_url2:
                        st.image(existing_image_url2, caption="現在の画像2", use_container_width=True)
                        delete_image2 = st.checkbox(
                            "この画像2を削除する",
                            value=False,
                            key=f"dialog_delete_image2_{row['id']}",
                        )

                # --- slot 3 ---
                with cols[2]:
                    st.caption("画像3")
                    image_file3 = st.file_uploader(
                        "変更する場合のみ",
                        type=["jpg", "jpeg", "png"],
                        key=f"dialog_edit_image3_{row['id']}",
                    )
                    delete_image3 = False
                    if existing_image_url3:
                        st.image(existing_image_url3, caption="現在の画像3", use_container_width=True)
                        delete_image3 = st.checkbox(
                            "この画像3を削除する",
                            value=False,
                            key=f"dialog_delete_image3_{row['id']}",
                        )

                st.divider()

                col_upd, col_cancel = st.columns([1, 1])
                do_update = col_upd.form_submit_button("更新")
                cancel = col_cancel.form_submit_button("キャンセル")

                if do_update:
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
                        area=str(area_e).strip(),
                        tide_type=tide_e,
                        temperature=float(temp_e),
                        wind_direction=str(wind_e).strip(),
                        lure=str(lure_e).strip(),
                        action=str(act_e).strip(),
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

        # ----------------- 削除 -----------------
        with tabs[2]:
            from db_utils_gsheets import delete_row
            st.warning("このレコードを削除します。元に戻せません。")
            confirm = st.checkbox("理解したうえで削除する", value=False, key=f"dialog_del_confirm_{int(row['id'])}")
            if st.button("削除を実行", type="primary", disabled=not confirm, key=f"dialog_del_btn_{int(row['id'])}"):
                delete_row(int(row["id"]))
                st.success("削除しました")
                st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog("レコード詳細")
        def _dlg():
            _render_body()
        _dlg()
    else:
        with st.expander("レコード詳細", expanded=True):
            _render_body()


def render_log_table_with_actions(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("データがありません。")
        return

    d = df.copy()
    d["date_dt"] = pd.to_datetime(d["date"], errors="coerce")
    d["time_dt"] = pd.to_datetime(d["time"], format="%H:%M", errors="coerce")
    d = d.sort_values(by=["date_dt", "time_dt"], ascending=[False, True], na_position="last")

    # ✅ ブログからのジャンプがあれば最優先で開く（ここは1回だけ）
    jump_id = st.session_state.pop("jump_edit_id", None)
    if jump_id is not None:
        d["id_int"] = pd.to_numeric(d["id"], errors="coerce").fillna(-1).astype(int)
        row = d[d["id_int"] == int(jump_id)].iloc[0]
        _open_details_dialog(row, is_mobile=True)
        return

    # 一覧は最小限：URL列は出さない
    d["画像"] = (
        d[["image_url1", "image_url2", "image_url3"]]
        .fillna("")
        .astype(str)
        .apply(lambda r: "あり" if any(x.strip() for x in r.values) else "—", axis=1)
    )
    list_df = d[["id", "date", "time", "area", "size", "画像"]].copy()
    list_df = list_df.rename(columns={"id": "ID", "date": "日付", "time": "時間", "area": "エリア", "size": "サイズ"})

    st.markdown("### 一覧")
    st.caption("選択してから「開く」を押すと編集/削除/プレビューが出ます")

    # 選択UIは1つだけ（確実に）
    list_df["ID_int"] = pd.to_numeric(list_df["ID"], errors="coerce").fillna(-1).astype(int)
    options = list_df["ID_int"].tolist()

    def _fmt(_id: int) -> str:
        r = list_df[list_df["ID_int"] == _id].iloc[0]
        return f"{r['日付']} {r['時間']} | {r['エリア']} | {r['サイズ']}cm | 画像:{r['画像']}"

    selected_id = st.selectbox(
        "レコードを選択",
        options=options,
        format_func=_fmt,
        key="log_select_box",
    )

    is_mobile = st.toggle("📱スマホ表示（縦レイアウト）", value=True, key="edit_is_mobile")

    if st.button("詳細（編集/削除/プレビュー）を開く", type="primary", key="open_detail_btn"):
        d["id_int"] = pd.to_numeric(d["id"], errors="coerce").fillna(-1).astype(int)
        row = d[d["id_int"] == int(selected_id)].iloc[0]
        _open_details_dialog(row, is_mobile=is_mobile)


