# analysis_tab.py
import pandas as pd
import plotly.express as px
import streamlit as st
from db_utils import fetch_all

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
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(yaxis_title="キャッチ率（%）", 
                    xaxis_title="潮回り", 
                    uniformtext_minsize=8, 
                    uniformtext_mode="hide",
                    margin=dict(t=80, b=40, l=40, r=40),
                    yaxis=dict(automargin=True)
                    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": False,   # スクロールでズームしない
            "displayModeBar": False,  # 右上のツールバー非表示
        }
    )


    with st.expander("詳細（件数内訳）"):
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
        st.plotly_chart(
            fig1,
            use_container_width=True,
            config={
                "scrollZoom": False,   # スクロールでズームしない
                "displayModeBar": False,  # 右上のツールバー非表示
            }
        )

    with c2:
        fig2 = px.line(
            g, x="month", y="catch_rate", markers=True,
            labels={"month": "月", "catch_rate": "キャッチ率（%）"},
            title="月別 キャッチ率"
        )
        st.plotly_chart(
            fig2,
            use_container_width=True,
            config={
                "scrollZoom": False,   # スクロールでズームしない
                "displayModeBar": False,  # 右上のツールバー非表示
            }
        )


    with st.expander("詳細（件数・平均サイズ）"):
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
    st.plotly_chart(
        fig1,
        use_container_width=True,
        config={
            "scrollZoom": False,   # スクロールでズームしない
            "displayModeBar": False,  # 右上のツールバー非表示
        }
    )


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
    st.plotly_chart(
        fig2,
        use_container_width=True,
        config={
            "scrollZoom": False,   # スクロールでズームしない
            "displayModeBar": False,  # 右上のツールバー非表示
        }
    )


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

    fig.update_traces(marker=dict(opacity=0.6))
    fig.update_layout(showlegend=False, 
                    yaxis_title="潮位 (cm)", 
                    xaxis_title="エリア",
                    margin=dict(t=80, b=40, l=40, r=40),
                    yaxis=dict(automargin=True)
                    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "scrollZoom": False,   # スクロールでズームしない
            "displayModeBar": False,  # 右上のツールバー非表示
        }
    )


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
