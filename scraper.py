import requests
from bs4 import BeautifulSoup
import re
from typing import List, Tuple


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def scrape_article(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = _detect_encoding(resp)
        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        title = _extract_title(soup)
        meta_desc = _extract_meta(soup)
        headings = _extract_headings(soup)
        content, word_count = _extract_content(soup)

        return {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "headings": headings,
            "content": content,
            "word_count": word_count,
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
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.text.strip().split("|")[0].strip()
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
