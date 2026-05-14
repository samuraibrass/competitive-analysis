import anthropic
from typing import List


def analyze_with_claude(my_article: dict, competitors: List[dict], api_key: str, model: str = "claude-opus-4-7") -> str:
    client = anthropic.Anthropic(api_key=api_key)

    comp_text = _build_competitor_summary(competitors)
    my_text = _build_my_article_summary(my_article)

    prompt = f"""あなたはSEOコンテンツ戦略の専門家です。
以下の「自分の記事」をGoogle検索上位10記事と比較・分析し、具体的な改善提案をしてください。

{my_text}

{comp_text}

以下の形式で分析してください：

## 総合評価
競合と比べた強みと弱みを3点ずつ挙げてください。

## コンテンツ量の分析
- 自分の文字数 vs 競合平均・最大
- 推奨文字数と根拠

## 見出し構成の差分分析
- 競合が頻繁に扱っているが自分の記事にない重要トピック（箇条書き）
- 追加を推奨する見出し案（5〜10個、具体的なタイトル文字列で）

## 独自差別化ポイントの提案
競合が扱っていない切り口や深堀りポイントを3つ提案してください。

## 優先度別アクションリスト
**今すぐやること（高優先度）**
- （具体的なアクション）

**次にやること（中優先度）**
- （具体的なアクション）

**余裕があればやること（低優先度）**
- （具体的なアクション）

日本語で、具体的かつ実践的に回答してください。"""

    message = client.messages.create(
        model=model,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def _build_my_article_summary(article: dict) -> str:
    headings_text = "\n".join(article["headings"][:25]) or "（見出し取得不可）"
    return f"""=== 自分の記事 ===
タイトル: {article['title']}
URL: {article['url']}
文字数: {article['word_count']:,}
見出し構成:
{headings_text}

冒頭内容:
{article['content'][:800]}"""


def _build_competitor_summary(competitors: List[dict]) -> str:
    lines = ["=== 競合上位10記事 ==="]
    for i, comp in enumerate(competitors, 1):
        headings_text = "\n".join(comp["headings"][:12]) or "  （取得不可）"
        lines.append(
            f"\n--- 競合{i}: {comp['title']} ---\n"
            f"URL: {comp['url']}\n"
            f"文字数: {comp['word_count']:,}\n"
            f"見出し構成:\n{headings_text}"
        )
    return "\n".join(lines)
