import requests
from bs4 import BeautifulSoup
import re
from typing import List, Tuple
from urllib.parse import urlparse


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def scrape_article(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = _detect_encoding(resp)
        soup = BeautifulSoup(resp.text, "lxml")

        title = _extract_title(soup)
        meta_desc = _extract_meta(soup)

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        headings = _extract_headings(soup)
        content, word_count = _extract_content(soup)

        result = {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "headings": headings,
            "content": content,
            "word_count": word_count,
            "error": None,
        }

        if word_count < 100:
            wp_data = _try_wp_api(url)
            if wp_data:
                result.update(wp_data)

        return result
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


def _detect_encoding(resp) -> str:
    # Priority 1: charset in HTML meta tag
    raw_soup = BeautifulSoup(resp.content, "lxml")
    for meta in raw_soup.find_all("meta"):
        charset = meta.get("charset")
        if charset:
            return charset
        http_equiv = meta.get("http-equiv", "")
        if http_equiv.lower() == "content-type":
            content = meta.get("content", "")
            if "charset=" in content:
                return content.split("charset=")[-1].strip()
    # Priority 2: Content-Type header
    ct = resp.headers.get("content-type", "")
    if "charset=" in ct:
        return ct.split("charset=")[-1].strip()
    # Priority 3: chardet detection
    return resp.apparent_encoding or "utf-8"


def _extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1 and h1.text.strip():
        return h1.text.strip()
    og = soup.find("meta", property="og:title")
    if og and og.get("content", "").strip():
        return og["content"].strip()
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.text.strip()
        for sep in ["|", "｜", " - ", " – ", " — ", "－"]:
            if sep in text:
                return text.split(sep)[0].strip()
        return text
    return "タイトル不明"


def _extract_meta(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", attrs={"name": "description"})
    if meta:
        return meta.get("content", "")
    og = soup.find("meta", property="og:description")
    if og:
        return og.get("content", "")
    return ""


def _extract_headings(soup: BeautifulSoup) -> List[str]:
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"]):
        text = tag.text.strip()
        if text and len(text) < 200:
            headings.append(f"[{tag.name.upper()}] {text}")
    return headings


def _extract_content(soup: BeautifulSoup) -> Tuple[str, int]:
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(id=re.compile(r"content|article|post|body", re.I))
        or soup.find(class_=re.compile(r"content|article|post|entry", re.I))
        or soup.body
    )
    text = main.get_text(separator="\n", strip=True) if main else ""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    text = "\n".join(lines)
    return text[:6000], len(text)


def _try_wp_api(url: str) -> dict | None:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        return None
    slug = parts[-1]
    api_url = f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2/posts?slug={slug}"
    try:
        resp = requests.get(api_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
        posts = resp.json()
        if not posts:
            return None
        post = posts[0]

        title = BeautifulSoup(post.get("title", {}).get("rendered", ""), "lxml").get_text().strip()
        content_html = post.get("content", {}).get("rendered", "")
        content_soup = BeautifulSoup(content_html, "lxml")

        headings = []
        for tag in content_soup.find_all(["h1", "h2", "h3"]):
            text = tag.text.strip()
            if text and len(text) < 200:
                headings.append(f"[{tag.name.upper()}] {text}")

        content_text = content_soup.get_text(separator="\n", strip=True)
        lines = [l.strip() for l in content_text.splitlines() if l.strip()]
        content_text = "\n".join(lines)

        excerpt = BeautifulSoup(post.get("excerpt", {}).get("rendered", ""), "lxml").get_text().strip()

        return {
            "title": title or "タイトル不明",
            "meta_description": excerpt,
            "headings": headings,
            "content": content_text[:6000],
            "word_count": len(content_text),
        }
    except Exception:
        return None
