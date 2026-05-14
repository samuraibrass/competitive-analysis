from apify_client import ApifyClient
from scraper import scrape_article
from typing import List


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
