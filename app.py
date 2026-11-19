"""
③ Webアプリ: 職種別タスクスコア（全職種）
起動: python -m streamlit run app.py
"""
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

DATA_FILE = Path(__file__).with_name("task_scores.csv")
TASKS = ["非定型分析", "非定型相互", "定型認識", "定型手仕事", "非定型手仕事"]
ALL = "すべての大分類"
COLORS = ["#2a78d6", "#b0b7c3"]
FMT = {t: "{:.2f}" for t in TASKS}

st.set_page_config(page_title="職種別タスクスコア", page_icon="📊", layout="wide")


@st.cache_data
def load(path):
    df = pd.read_csv(path, encoding="utf-8-sig", dtype={"職業コード": str})
    df["表示名"] = df["職業名"] + "（" + df["大分類"] + "）"
    return df


def wavg(d):
    return pd.Series({t: np.average(d[t], weights=d["就業者数"]) for t in TASKS})


def whole(m):
    return f"【{m} 全体】"


if not DATA_FILE.exists():
    st.error(f"{DATA_FILE.name} が見つかりません。先に `python prepare_data.py` を実行してください。")
    st.stop()

df = load(DATA_FILE)
majors = list(dict.fromkeys(df["大分類"]))   # 元データの並び順

st.title("職種別タスクスコア")
st.caption(f"日本版O-NET（job tag）の14項目から作成した5つのタスク指標。令和2年国勢調査の{len(df)}職業小分類"
           f"（就業者 {df['就業者数'].sum() / 1e4:,.0f}万人）。就業者数で加重して標準化"
           "（全職業の加重平均 = 0、加重標準偏差 = 1）。")

tab1, tab2 = st.tabs(["職種・大分類を調べる", "全職種一覧"])

# =================================================================
# タブ1: 職種・大分類を調べる
# =================================================================
with tab1:
    c1, c2 = st.columns([1, 2])
    major = c1.selectbox("大分類", [ALL] + majors)
    if major == ALL:
        choices = df["表示名"].tolist()
    else:
        choices = [whole(major)] + df.loc[df["大分類"] == major, "表示名"].tolist()
    target = c2.selectbox("職種（大分類全体の平均も選べます／入力して検索できます）", choices)

    is_major = major != ALL and target == whole(major)
    if is_major:
        sub = df[df["大分類"] == major]
        name, vals, own_major = f"{major}（全体）", wavg(sub), major
    else:
        row = df[df["表示名"] == target].iloc[0]
        name, vals, own_major = row["職業名"], row[TASKS].astype(float), row["大分類"]

    # --- 比較対象 ---
    opts = ([] if is_major else [f"{own_major}の平均"]) + ["全職業の平均（= 0）", "別の大分類", "別の職種"]
    cmp_mode = st.radio("比較対象", opts, horizontal=True)
    if cmp_mode == f"{own_major}の平均":
        cmp_label, cmp_vals = cmp_mode, wavg(df[df["大分類"] == own_major])
    elif cmp_mode.startswith("全職業"):
        cmp_label, cmp_vals = "全職業の平均", pd.Series(0.0, index=TASKS)
    elif cmp_mode == "別の大分類":
        om = st.selectbox("比較する大分類", [m for m in majors if not (is_major and m == major)])
        cmp_label, cmp_vals = f"{om}（全体）", wavg(df[df["大分類"] == om])
    else:
        other = st.selectbox("比較する職種", [x for x in df["表示名"] if is_major or x != target])
        orow = df[df["表示名"] == other].iloc[0]
        cmp_label, cmp_vals = orow["職業名"], orow[TASKS].astype(float)

    # --- 基本情報 ---
    m1, m2, m3 = st.columns(3)
    if is_major:
        m1.markdown(f"**大分類**  \n{major}")
        m2.markdown(f"**就業者数（合計）**  \n{int(sub['就業者数'].sum()):,} 人")
        m3.markdown(f"**含まれる職種数**  \n{len(sub)}")
    else:
        m1.markdown(f"**大分類**  \n{own_major}")
        m2.markdown(f"**就業者数**  \n{int(row['就業者数']):,} 人")
        m3.markdown(f"**対応する job tag 職業数**  \n{int(row['対応job tag職業数'])}")

    # --- 棒グラフ ---
    if cmp_label == name:
        cmp_label += "（比較）"
    order = [name, cmp_label]
    plot = pd.concat([
        pd.DataFrame({"タスク": TASKS, "スコア": vals.values, "系列": name}),
        pd.DataFrame({"タスク": TASKS, "スコア": cmp_vals.values, "系列": cmp_label}),
    ])
    chart = (
        alt.Chart(plot)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=alt.X("タスク:N", sort=TASKS, title=None, axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("系列:N", sort=order),
            y=alt.Y("スコア:Q", title="標準化スコア"),
            color=alt.Color("系列:N", sort=order, scale=alt.Scale(domain=order, range=COLORS),
                            legend=alt.Legend(orient="bottom", title=None, labelLimit=400)),
            tooltip=["系列", "タスク", alt.Tooltip("スコア:Q", format=".2f")],
        )
        .properties(height=380)
    )
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color="#888").encode(y="y:Q")

    g, t = st.columns([3, 2])
    g.altair_chart(chart + zero, width="stretch")

    table = pd.DataFrame({name: vals, cmp_label: cmp_vals, "差": vals - cmp_vals})
    fmt = {name: "{:.2f}", cmp_label: "{:.2f}", "差": "{:+.2f}"}
    if not is_major:
        col = f"順位（全{len(df)}職種中）"
        table[col] = pd.Series({k: int((df[k] > row[k]).sum() + 1) for k in TASKS})
    t.dataframe(table.style.format(fmt), width="stretch")
    t.download_button(
        "このスコアをCSVで保存",
        table.reset_index(names="タスク").to_csv(index=False).encode("utf-8-sig"),
        file_name=f"task_scores_{major if is_major else row['職業コード']}.csv",
        mime="text/csv",
    )

    # --- 大分類全体を選んだときは、含まれる職種の一覧 ---
    if is_major:
        st.markdown(f"**{major} に含まれる職種**")
        st.dataframe(
            sub[["職業名", "就業者数"] + TASKS].sort_values("就業者数", ascending=False)
            .style.format(FMT | {"就業者数": "{:,}"})
            .background_gradient(subset=TASKS, cmap="RdBu_r", vmin=-2.5, vmax=2.5),
            width="stretch", hide_index=True,
        )

# =================================================================
# タブ2: 全職種一覧
# =================================================================
with tab2:
    q = st.text_input("職業名で検索", "")
    lmajor = st.multiselect("大分類", majors, default=majors)
    view = df[df["大分類"].isin(lmajor)]
    if q:
        view = view[view["職業名"].str.contains(q, regex=False)]
    cols = ["職業コード", "職業名", "大分類", "就業者数"] + TASKS
    st.dataframe(
        view[cols].style.format(FMT | {"就業者数": "{:,}"})
        .background_gradient(subset=TASKS, cmap="RdBu_r", vmin=-2.5, vmax=2.5),
        width="stretch", height=560, hide_index=True,
    )
    st.caption(f"{len(view)}職種を表示。列名をクリックで並べ替え。")

    st.markdown("**大分類別の平均（就業者数で加重）**")
    st.dataframe(
        df.groupby("大分類", sort=False).apply(wavg, include_groups=False)
        .style.format("{:.2f}").background_gradient(cmap="RdBu_r", vmin=-2, vmax=2),
        width="stretch",
    )
    st.download_button(
        "全職種のスコアをCSVで保存",
        df[cols].to_csv(index=False).encode("utf-8-sig"),
        file_name="task_scores_all.csv",
        mime="text/csv",
    )

with st.expander("タスク指標の定義と出典"):
    st.markdown(
        "- **非定型分析**: 情報やデータを分析する／創造的に考える／情報の意味を他者に説明する\n"
        "- **非定型相互**: 人間関係を構築し、維持する／部下への指導、指示、動機づけ／他者をコーチし、能力開発を行う\n"
        "- **定型認識**: 同一作業の反復／厳密さ、正確さ／仕事の構造化（ver.3.00 の「優先順位や目標の自己設定」を逆転）\n"
        "- **定型手仕事**: 機器等の速度に応じた作業／機械、および機械製造のプロセスをコントロールする／反復作業\n"
        "- **非定型手仕事**: 乗り物を運転・操縦する／モノ、道具、制御装置を扱う手作業\n\n"
        "出典: job tag 簡易版数値系データ ver.3.00、原論文 付表1（対応表）、令和2年国勢調査。"
        "原論文（Acemoglu and Autor 2011 準拠）と同じく、各項目を国勢調査の就業者数で加重して標準化し、"
        "指標ごとに合計したうえで再度加重して標準化しています。"
        "推定就業者数500人程度以下の job tag 職業は平均に含めていません。"
        "大分類の値は、含まれる職種のスコアの就業者数加重平均です。"
        "job tag 職業が対応しない小分類は含まれません。"
    )
