from apify_client import ApifyClient
from scraper import scrape_article
from typing import List


_PAGE_FN = """async function pageFunction(context) {
    const { $, request } = context;
    const title = $('h1').first().text().trim() ||
                  $('title').text().trim().split(/[|｜\\u002d\\u2013\\u2014\\uff0d]/).shift().trim();
    const metaDesc = $('meta[name="description"]').attr('content') ||
                     $('meta[property="og:description"]').attr('content') || '';
    const headings = [];
    $('h1,h2,h3').each(function() {
        const t = $(this).text().trim();
        if (t && t.length < 200) headings.push('[' + this.tagName.toUpperCase() + '] ' + t);
    });
    $('script,style,nav,footer,header,aside').remove();
    const body = $('article,main,[id*="content"],[class*="content"],body').first();
    const lines = body.text().split('\\n').map(function(l){ return l.trim(); }).filter(Boolean);
    const content = lines.join('\\n').slice(0, 6000);
    return { title: title || 'タイトル不明', metaDesc: metaDesc, headings: headings,
             content: content, wordCount: lines.join('\\n').length };
}"""


def scrape_url_with_apify(url: str, api_key: str) -> dict:
    client = ApifyClient(api_key)
    try:
        run = client.actor("apify/cheerio-scraper").call(run_input={
            "startUrls": [{"url": url}],
            "pageFunction": _PAGE_FN,
            "maxRequestsPerCrawl": 1,
        })
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            return scrape_article(url)
        item = items[0]
        return {
            "url": url,
            "title": item.get("title", "タイトル不明"),
            "meta_description": item.get("metaDesc", ""),
            "headings": item.get("headings", []),
            "content": item.get("content", ""),
            "word_count": item.get("wordCount", 0),
            "error": None,
        }
    except Exception as e:
        return {
            "url": url,
            "title": "取得エラー",
            "meta_description": "",
            "headings": [],
            "content": "",
            "word_count": 0,
            "error": str(e),
        }


def get_top10_competitors(keyword: str, api_key: str, country: str = "jp") -> List[dict]:
    client = ApifyClient(api_key)

    run_input = {
        "queries": keyword,
        "maxPagesPerQuery": 1,
        "resultsPerPage": 10,
        "languageCode": "ja",
        "countryCode": country,
    }

    run = client.actor("apify/google-search-scraper").call(run_input=run_input)
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

    urls = _extract_urls(items)

    competitors = []
    for url in urls:
        article = scrape_article(url)
        competitors.append(article)

    return competitors


def _extract_urls(items: list) -> List[str]:
    urls = []
    for item in items:
        organic = item.get("organicResults", [])
        for result in organic:
            url = result.get("url") or result.get("link") or ""
            if url and url.startswith("http"):
                urls.append(url)
        if urls:
            break
    return urls[:10]
