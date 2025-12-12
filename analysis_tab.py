# analysis_tab.py
import pandas as pd
import plotly.express as px
import streamlit as st
# from db_utils import fetch_all
import numpy as np
from db_utils_gsheets import fetch_all

# 東京湾向けの潮位レンジ設定
TIDE_MAX_CM  = 220.0   # 上限（これ以上は最後のビンにまとめる）
TIDE_STEP_CM = 20.0    # 刻み（細かめ）

def render_tap_only(fig, key=None):
    fig.update_layout(dragmode=False, hovermode="closest")
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    st.plotly_chart(
        fig, use_container_width=True, key=key,
        config={
            "scrollZoom": False,
            "doubleClick": False,
            "displayModeBar": False,
            "displaylogo": False,
            "modeBarButtonsToRemove": [
                "zoom","pan","select","lasso2d",
                "zoomIn2d","zoomOut2d","autoScale2d","resetScale2d"
            ],
        },
    )

def _prep_df():
    df = fetch_all()
    if df.empty:
        return df
    # 日付→月、サイズ→キャッチ有無
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    df["size"] = pd.to_numeric(df["size"], errors="coerce")
    df["caught"] = df["size"].fillna(0) > 0
    # 欠損の扱いを軽く整理
    df["tide_type"] = df["tide_type"].fillna("不明")
    df["area"] = df["area"].fillna("未入力")
    return df

def _summary_block(df):
    total = len(df)
    catches = int(df["caught"].sum())
    rate = (catches / total * 100) if total else 0.0

    st.subheader("📊 釣行サマリー")
    c1, c2, c3 = st.columns(3)
    c1.metric("総釣行回数", f"{total}")
    c2.metric("釣れた回数", f"{catches}")
    c3.metric("キャッチ率", f"{rate:.1f}%")

def _tide_block(df):
    st.title("🎣 シーバス釣行ログ管理アプリ")
    st.caption("各要素の分析")
    st.divider()
    st.subheader("🌊 潮回り別の傾向（キャッチ率）")
    if df.empty:
        st.info("データがありません。")
        return
    g = df.groupby("tide_type").agg(
        trips=("id", "count"),
        catches=("caught", "sum"),
    ).reset_index()
    g["catch_rate"] = (g["catches"] / g["trips"] * 100).round(1)
    # 表示順（よく使う順）に並べ替え
    order = ["大潮", "中潮", "小潮", "若潮", "長潮", "不明"]
    g["order_key"] = g["tide_type"].apply(lambda x: order.index(x) if x in order else len(order))
    g = g.sort_values(["order_key"])

    fig = px.bar(
        g, x="tide_type", y="catch_rate",
        text="catch_rate",
        labels={"tide_type": "潮回り", "catch_rate": "キャッチ率（%）"},
        title="潮回り別キャッチ率"
    )

    # 最大値に余裕をもたせる
    y_max = g["catch_rate"].max() * 1.15  # 15%くらい余裕を上に
    fig.update_yaxes(range=[0, y_max])

    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(yaxis_title="キャッチ率（%）", 
                    xaxis_title="潮回り", 
                    uniformtext_minsize=8, 
                    uniformtext_mode="hide",
                    margin=dict(t=80, b=40, l=40, r=40),
                    yaxis=dict(automargin=True)
                    )
    # st.plotly_chart(
    #     fig,
    #     use_container_width=True,
    #     config={
    #         "scrollZoom": False,   # スクロールでズームしない
    #         "displayModeBar": False,  # 右上のツールバー非表示
    #     }
    # )

    render_tap_only(fig)


    # with st.expander("詳細（件数内訳）"):
    st.dataframe(g[["tide_type", "trips", "catches", "catch_rate"]].rename(
        columns={"tide_type": "潮回り", "trips": "釣行数", "catches": "ヒット回数", "catch_rate": "キャッチ率（%）"}
    ))

def _month_block(df):
    st.subheader("📆 月別の傾向（釣行回数・キャッチ率）")
    if df.empty:
        st.info("データがありません。")
        return
    g = df.groupby("month").agg(
        trips=("id", "count"),
        catches=("caught", "sum"),
        avg_size=("size", lambda x: x[x > 0].mean() if (x > 0).any() else None),
    ).reset_index()
    g["catch_rate"] = (g["catches"] / g["trips"] * 100).round(1)
    # 月を時系列順に
    g["month_dt"] = pd.to_datetime(g["month"], format="%Y-%m")
    g = g.sort_values("month_dt")

    c1, c2 = st.columns(2)
    with c1:
        fig1 = px.bar(
            g, x="month", y="trips",
            labels={"month": "月", "trips": "釣行回数"},
            title="月別 釣行回数"
        )
        render_tap_only(fig1)

    with c2:
        fig2 = px.line(
            g, x="month", y="catch_rate", markers=True,
            labels={"month": "月", "catch_rate": "キャッチ率（%）"},
            title="月別 キャッチ率"
        )
        render_tap_only(fig2)


    # with st.expander("詳細（件数・平均サイズ）"):
    st.dataframe(
        g[["month", "trips", "catches", "catch_rate", "avg_size"]]
        .rename(columns={"month": "月", "trips": "釣行数", "catches": "ヒット回数", "catch_rate": "キャッチ率（%）", "avg_size": "平均サイズ(cm)"})
    )

def _lure_block(df):
    st.subheader("🪝 ルアー別の釣果")

    if df.empty:
        st.info("データがありません。")
        return

    # サイズ0（ボウズ）は除外
    df_catch = df[df["size"] > 0]

    if df_catch.empty:
        st.info("まだ釣果データがありません。")
        return

    g = df_catch.groupby("lure").agg(
        catches=("id", "count"),
        avg_size=("size", "mean")
    ).reset_index().sort_values("catches", ascending=False)

    # --- グラフ1：使用ルアー別の釣果回数 ---
    fig1 = px.bar(
        g,
        x="lure",
        y="catches",
        text="catches",
        labels={"lure": "ルアー", "catches": "釣果数"},
        title="ルアー別の釣果数"
    )

    fig1.update_traces(texttemplate="%{text}", textposition="outside")
    render_tap_only(fig1)


    # --- グラフ2：ルアー別の平均サイズ ---
    fig2 = px.bar(
        g,
        x="lure",
        y="avg_size",
        text="avg_size",
        labels={"lure": "ルアー", "avg_size": "平均サイズ (cm)"},
        title="ルアー別の平均サイズ",
        color="avg_size",
        color_continuous_scale="Viridis"
    )

    fig2.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    render_tap_only(fig2)


    # --- テーブル表示 ---
    st.dataframe(
        g.rename(columns={
            "lure": "ルアー",
            "catches": "釣果数",
            "avg_size": "平均サイズ(cm)"
        }),
        use_container_width=True
    )

def _area_tide_block(df):
    st.subheader("📍 エリア別の潮位分布")

    if df.empty:
        st.info("データがありません。")
        return

    # サイズ0（ボウズ）は除外
    df_catch = df[df["size"] > 0].dropna(subset=["tide_height"])

    if df_catch.empty:
        st.info("潮位データのある釣果がありません。")
        return

    # 箱ひげ図（潮位の分布をエリア別に）
    fig = px.box(
        df_catch,
        x="area",
        y="tide_height",
        color="area",
        points="all",  # 実際のデータ点も表示
        labels={"area": "エリア", "tide_height": "潮位 (cm)"},
        title="エリア別 潮位分布と釣果"
    )

    # 最大値に余裕をもたせる
    y_max = df_catch["tide_height"].max() * 1.15  # 15%くらい余裕を上に
    fig.update_yaxes(range=[0, y_max])

    fig.update_traces(marker=dict(opacity=0.6))
    fig.update_layout(showlegend=False, 
                    yaxis_title="潮位 (cm)", 
                    xaxis_title="エリア",
                    margin=dict(t=80, b=40, l=40, r=40),
                    yaxis=dict(automargin=True)
                    )

    render_tap_only(fig)

def _tide_time_heatmap(df):
    st.subheader("⏰ 潮位 × 時間帯 ヒートマップ")

    if df.empty:
        st.info("データがありません。")
        return

    # --- 1) 前処理：ボウズ除外 / 潮位・時間の欠損/ダミー除外 ---
    d = df.copy()

    # 釣れたときだけを見る（ヒット傾向を出したい前提）
    d = d[pd.to_numeric(d["size"], errors="coerce").fillna(0) > 0]

    # 潮位：数値化→欠損除外
    d["tide_height"] = pd.to_numeric(d["tide_height"], errors="coerce")
    d = d.dropna(subset=["tide_height"])

    # “m”入力の可能性をcmに正規化（<=5をmとみなす）
    m_mask = d["tide_height"].between(0.1, 5, inclusive="both")
    d.loc[m_mask, "tide_height"] = d.loc[m_mask, "tide_height"] * 100

    # 時間：文字列 "HH:MM" → datetime → hour
    # 00:00 は“空欄代替”として扱って除外（必要なら残してもOK）
    t = pd.to_datetime(d["time"], format="%H:%M", errors="coerce")
    d = d[~((d["time"] == "00:00") | t.isna())].copy()
    d["hour"] = t.dt.hour

    if d.empty:
        st.info("潮位と時間の有効データがありません。")
        return

    # --- 2) 設定UI：時間帯の粒度・色指標 ---
    c1, c2 = st.columns(2)
    with c1:
        hour_step = st.selectbox("時間帯の粒度", [1, 2, 3], index=1, help="1=1時間刻み、2=2時間刻み…")
    with c2:
        metric = st.selectbox("色で表示する指標", ["釣果数", "平均サイズ"], index=0)

    # 時間帯ビン（例：0-2, 2-4…）
    d["hour_bin_start"] = (d["hour"] // hour_step) * hour_step
    d["hour_bin_end"] = d["hour_bin_start"] + hour_step
    d["hour_bin"] = d["hour_bin_start"].astype(str) + "–" + d["hour_bin_end"].astype(str) + "時"

    # --- 2-b) 潮位ビン（東京湾向け：0〜220cmを20cm刻みで固定） ---
    # 入力が上限を超えていても、最後のビンに“丸める”ためにクリップ
    d["tide_h_cm"] = d["tide_height"].clip(lower=0, upper=TIDE_MAX_CM - 1e-6)

    edges  = np.arange(0.0, TIDE_MAX_CM + 1e-6, TIDE_STEP_CM)  # 0,20,40,...,220
    labels = [f"{int(edges[i])}–{int(edges[i+1])}cm" for i in range(len(edges)-1)]

    d["tide_bin"] = pd.cut(
        d["tide_h_cm"],
        bins=edges,
        right=False,           # 左閉右開 [a,b)
        labels=labels,
        include_lowest=True
    )

    # 念のため空判定
    if d["tide_bin"].isna().all():
        st.info("潮位ビンに該当するデータがありません。")
        return

    # --- 3) 集計 ---
    if metric == "釣果数":
        pivot = d.pivot_table(index="tide_bin", columns="hour_bin", values="id", aggfunc="count", fill_value=0)
        color_title = "釣果数"
    else:
        # 釣れた魚の平均サイズ（cm）
        pivot = d.pivot_table(index="tide_bin", columns="hour_bin", values="size", aggfunc="mean")
        color_title = "平均サイズ (cm)"

    # 軸の並びを自然順に（時間ビンを時間順で）
    # hour_binの開始時刻でソート
    def _hour_key(lbl):
        try:
            return int(lbl.split("–")[0])
        except Exception:
            return 0
    cols_sorted = sorted(pivot.columns, key=_hour_key)
    pivot = pivot[cols_sorted]

    # --- 4) 可視化 ---
    fig = px.imshow(
        pivot,
        aspect="auto",
        color_continuous_scale="YlOrRd",
        labels=dict(x="時間帯", y="潮位帯", color=color_title),
        title="潮位 × 時間帯 ヒートマップ（釣れたデータのみ）"
    )

    # スマホ見切れ対策（上下左右余白）
    # fig.update_layout(margin=dict(t=80, b=60, l=60, r=40))
    # fig.update_xaxes(side="bottom")

    # タップのみ有効（ズーム・パン禁止）
    render_tap_only(fig)

    # 数値の裏取り用テーブルも出す
    st.dataframe(pivot.fillna(0).astype(float).round(1), use_container_width=True)


def show_analysis():
    st.header("📈 分析")
    df = _prep_df()

    # --- エリアフィルタ（“全エリア”も選べる） ---
    areas = ["全エリア"] + sorted(df["area"].dropna().unique().tolist()) if not df.empty else ["全エリア"]
    sel = st.selectbox("エリア", areas, index=0)
    if sel != "全エリア" and not df.empty:
        df = df[df["area"] == sel]

    if df.empty:
        st.info("まだデータがありません。まずは釣行を登録してください。")
        return

    _summary_block(df)
    st.divider()
    _tide_block(df)
    st.divider()
    _month_block(df)
    _lure_block(df)
    _area_tide_block(df)
    _tide_time_heatmap(df)
