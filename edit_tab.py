# edit_tab.py
from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import datetime


def _has_dataframe_selection() -> bool:
    """Streamlit の st.dataframe が selection_mode/on_select を受け付けるかを雑に判定。"""
    try:
        import inspect
        sig = inspect.signature(st.dataframe)
        return ("selection_mode" in sig.parameters) and ("on_select" in sig.parameters)
    except Exception:
        return False


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
    """スマホ向け：一覧→1件選択→ポップアップ（詳細）"""

    if df is None or df.empty:
        st.info("データがありません。")
        return

    d = df.copy()
    d["date_dt"] = pd.to_datetime(d["date"], errors="coerce")
    d["time_dt"] = pd.to_datetime(d["time"], format="%H:%M", errors="coerce")
    d = d.sort_values(by=["date_dt", "time_dt"], ascending=[False, True], na_position="last")

    # 一覧は最小限：URL列は出さない（横スクロール削減のキモ）
    d["画像"] = (
        d[["image_url1", "image_url2", "image_url3"]]
        .fillna("")
        .astype(str)
        .apply(lambda r: "あり" if any(x.strip() for x in r.values) else "—", axis=1)
    )

    list_df = d[["id", "date", "time", "area", "size", "画像"]].copy()
    list_df = list_df.rename(columns={"id": "ID", "date": "日付", "time": "時間", "area": "エリア", "size": "サイズ"})

    st.markdown("### 一覧（選択して詳細を開く）")

    selected_id: int | None = None

    if _has_dataframe_selection():
        ev = st.dataframe(
            list_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="log_select_table",
        )
        try:
            rows = ev.selection.rows  # type: ignore[attr-defined]
        except Exception:
            rows = []
        if rows:
            selected_id = int(list_df.iloc[rows[0]]["ID"])
    else:
        options = list_df["ID"].tolist()

        def _fmt(_id: int) -> str:
            r = list_df[list_df["ID"] == _id].iloc[0]
            return f"{r['日付']} {r['時間']} | {r['エリア']} | {r['サイズ']}cm | 画像:{r['画像']}"

        selected_id = st.selectbox("レコードを選択", options=options, format_func=_fmt, key="log_select_box")

    # --- 選択IDが取れたら即ポップアップを開く（ボタン不要） ---
    if selected_id is not None:
        row = d[d["id"] == selected_id].iloc[0]
        is_mobile = st.toggle("📱スマホ表示（縦レイアウト）", value=True, key="edit_is_mobile")

        # 前回と同じIDなら連続で開かない（連打防止）
        if st.session_state.get("last_opened_id") != int(selected_id):
            st.session_state["last_opened_id"] = int(selected_id)
            _open_details_dialog(row, is_mobile=is_mobile)

