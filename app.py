import streamlit as st
from dotenv import load_dotenv
from urllib.parse import urlparse
import os

load_dotenv()


def _get_secret(key: str) -> str:
    """st.secrets（Streamlit Cloud）→ os.getenv（ローカル）の順で取得"""
    try:
        return st.secrets.get(key, os.getenv(key, ""))
    except Exception:
        return os.getenv(key, "")

st.set_page_config(
    page_title="競合記事分析ツール",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 競合記事分析ツール")
st.caption("自分の記事をGoogle上位10記事と比較し、Claude AIが改善提案を生成します")

# --- Sidebar: API Keys ---
with st.sidebar:
    st.header("⚙️ API設定")
    apify_key = st.text_input(
        "Apify APIキー",
        value=_get_secret("APIFY_API_KEY"),
        type="password",
        help="https://console.apify.com/account/integrations からコピー",
    )
    claude_key = st.text_input(
        "Claude APIキー",
        value=_get_secret("ANTHROPIC_API_KEY"),
        type="password",
        help="https://console.anthropic.com/settings/api-keys からコピー",
    )
    st.divider()
    model_choice = st.radio(
        "Claudeモデル",
        options=["claude-opus-4-7", "claude-sonnet-4-6"],
        format_func=lambda m: "Opus 4.7（高精度・低速）" if "opus" in m else "Sonnet 4.6（バランス・高速）",
        index=0,
    )
    country = st.selectbox(
        "Google検索の国",
        ["jp", "us", "uk"],
        index=0,
        help="競合検索に使う国コード",
    )

# --- Main Input ---
article_url = st.text_input(
    "自分の記事URL",
    placeholder="https://example.com/your-article",
)
custom_keyword = st.text_input(
    "検索キーワード（必須）",
    placeholder="例: ダイエット 食事制限 方法",
    help="Googleでこのキーワードを検索し、上位10記事を競合として取得します。",
)

run_button = st.button("▶ 分析開始", type="primary", use_container_width=True)

if run_button:
    # Validation
    if not article_url:
        st.error("記事URLを入力してください")
        st.stop()
    if not custom_keyword.strip():
        st.error("検索キーワードを入力してください")
        st.stop()
    effective_apify_key = apify_key or _get_secret("APIFY_API_KEY")
    effective_claude_key = claude_key or _get_secret("ANTHROPIC_API_KEY")
    if not effective_apify_key:
        st.error("Apify APIキーを入力してください")
        st.stop()
    if not effective_claude_key:
        st.error("Claude APIキーを入力してください")
        st.stop()
    apify_key = effective_apify_key
    claude_key = effective_claude_key

    # Step 1: Scrape own article
    with st.status("自分の記事を取得中...", expanded=True) as status:
        from scraper import scrape_article
        my_article = scrape_article(article_url)

        if my_article["error"]:
            st.error(f"記事の取得に失敗しました: {my_article['error']}")
            st.stop()

        st.write(f"✅ タイトル: **{my_article['title']}**")
        st.write(f"📝 文字数: {my_article['word_count']:,}文字 / 見出し数: {len(my_article['headings'])}個")

        keyword = custom_keyword.strip()
        st.write(f"🔎 検索キーワード: `{keyword}`")

        # Step 2: Get competitors via Apify
        status.update(label="Google検索で競合記事を収集中（1〜2分）...")
        from apify_wrapper import get_top10_competitors
        competitors = get_top10_competitors(keyword, apify_key, country)

        valid = [c for c in competitors if not c["error"]]
        st.write(f"✅ 競合記事: {len(valid)}/{len(competitors)}件取得成功")

        # Step 3: Claude analysis
        status.update(label="Claude AIで分析中...")
        from analyzer import analyze_with_claude
        analysis = analyze_with_claude(my_article, competitors, claude_key, model_choice)

        status.update(label="分析完了！", state="complete")

    st.divider()

    # --- Results ---
    st.subheader("📊 基本比較")

    avg_words = sum(c["word_count"] for c in valid) / len(valid) if valid else 0
    max_words = max((c["word_count"] for c in valid), default=0)
    avg_headings = sum(len(c["headings"]) for c in valid) / len(valid) if valid else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("自分の文字数", f"{my_article['word_count']:,}")
    col2.metric("競合平均文字数", f"{int(avg_words):,}", delta=f"{my_article['word_count'] - int(avg_words):+,}")
    col3.metric("競合最大文字数", f"{max_words:,}")
    col4.metric(
        "自分の見出し数",
        len(my_article["headings"]),
        delta=f"{len(my_article['headings']) - int(avg_headings):+.0f} vs 競合平均",
    )

    st.divider()

    # Cannibalization check
    my_domain = urlparse(article_url).netloc
    cannibal_hits = [
        (i + 1, c)
        for i, c in enumerate(competitors)
        if urlparse(c["url"]).netloc == my_domain
    ]
    if cannibal_hits:
        st.warning(
            "⚠️ **カニバリゼーション警告**\n\n"
            "自分のサイトの記事が検索上位に入っています。"
            "同じキーワードで複数記事が競合しており、評価が分散している可能性があります。\n\n"
            + "\n".join(f"- 順位 **{rank}位**: {c['url']}" for rank, c in cannibal_hits)
        )

    st.divider()

    # Competitor list
    st.subheader("🏆 競合上位10記事")
    for i, comp in enumerate(competitors, 1):
        is_cannibal = urlparse(comp["url"]).netloc == my_domain
        if comp["error"]:
            icon = "⚠️"
        elif is_cannibal:
            icon = "🔴"
        else:
            icon = "✅"
        cannibal_tag = " 【自社記事・カニバリ】" if is_cannibal else ""
        label = f"{icon} {i}. {comp['title']}{cannibal_tag} — {comp['word_count']:,}文字"
        with st.expander(label):
            st.write(f"**URL:** {comp['url']}")
            if comp["error"]:
                st.warning(f"取得エラー: {comp['error']}")
            else:
                st.write(f"**見出し数:** {len(comp['headings'])}")
                if comp["headings"]:
                    st.code("\n".join(comp["headings"][:15]), language=None)

    st.divider()

    # Claude analysis
    st.subheader("🤖 Claude AIによる改善提案")
    st.markdown(analysis)

    # Download button
    report = f"# 競合分析レポート\n\n**自分の記事:** {my_article['title']}\n**URL:** {article_url}\n\n{analysis}"
    st.download_button(
        "📥 レポートをダウンロード（Markdown）",
        data=report,
        file_name="competitive_analysis_report.md",
        mime="text/markdown",
    )
