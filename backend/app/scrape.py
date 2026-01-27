import re
from typing import Iterable, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .config import (
    MAX_SCRAPE_CHARS,
    SCRAPE_CA_CERT_PATH,
    SCRAPE_TIMEOUT_SECONDS,
    SCRAPE_USER_AGENT,
)


BLOCKLIST_PATTERNS = [
    "comment",
    "reply",
    "respond",
    "discussion",
    "review",
    "rating",
    "share",
    "social",
    "subscribe",
    "newsletter",
    "footer",
    "header",
    "nav",
    "menu",
    "sidebar",
    "widget",
    "cookie",
    "consent",
    "banner",
    "promo",
    "advert",
    "sponsor",
    "breadcrumb",
    "related",
    "recommended",
    "login",
    "signup",
    "modal",
    "popup",
    "form",
    "search",
    "tag",
    "meta",
    "author",
    "коммент",
    "ответ",
    "подел",
    "подпис",
    "реклам",
    "баннер",
    "сайдбар",
    "меню",
    "навигац",
    "подвал",
    "шапк",
    "форма",
    "поиск",
    "похожие",
    "рекомендуем",
    "вход",
    "регистрац",
]

BLOCKLIST_RE = re.compile("|".join(BLOCKLIST_PATTERNS), re.IGNORECASE)

DROP_LINE_RE = re.compile(
    r"^(ответить|reply|share|поделиться|like|нравится|читать далее|read more|"
    r"оставить комментарий|leave a comment|комментарии|login|sign in|войти|регистрация)$",
    re.IGNORECASE,
)


def _normalize_title(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned


def _normalize_body(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _iter_attrs(tag) -> Iterable[str]:
    if tag is None:
        return []
    attrs = []
    tag_id = tag.get("id") if hasattr(tag, "get") else None
    if isinstance(tag_id, str):
        attrs.append(tag_id)
    tag_class = tag.get("class") if hasattr(tag, "get") else None
    if isinstance(tag_class, list):
        attrs.extend([item for item in tag_class if isinstance(item, str)])
    elif isinstance(tag_class, str):
        attrs.append(tag_class)
    return [attr for attr in attrs if attr]


def _strip_blocklisted(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(True):
        if not tag or not getattr(tag, "name", None):
            continue
        if tag.name in ("html", "body"):
            continue
        try:
            tag_name = tag.name or ""
            if BLOCKLIST_RE.search(tag_name):
                tag.decompose()
                continue
            attrs = " ".join(_iter_attrs(tag))
            if attrs and BLOCKLIST_RE.search(attrs):
                tag.decompose()
        except Exception:
            continue


def _extract_clean_text(soup: BeautifulSoup) -> str:
    raw_lines = []
    for line in soup.get_text("\n").split("\n"):
        if not isinstance(line, str):
            continue
        raw_lines.append(line.strip())
    filtered = []
    for line in raw_lines:
        if not line or len(line) < 2:
            continue
        if DROP_LINE_RE.match(line):
            continue
        filtered.append(line)
    return _normalize_body("\n".join(filtered))


async def scrape_url(url: str) -> Tuple[str, str, str, str]:
    headers = {"User-Agent": SCRAPE_USER_AGENT}
    timeout = httpx.Timeout(SCRAPE_TIMEOUT_SECONDS)
    verify = SCRAPE_CA_CERT_PATH if SCRAPE_CA_CERT_PATH else True
    async with httpx.AsyncClient(
        headers=headers, follow_redirects=True, timeout=timeout, verify=verify
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        final_url = str(response.url)
        html = response.text

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()
    _strip_blocklisted(soup)

    title = soup.title.string if soup.title and soup.title.string else ""
    title = _normalize_title(title)
    if not title:
        try:
            title = urlparse(final_url).hostname or final_url
        except Exception:
            title = final_url

    text = _extract_clean_text(soup)
    if len(text) > MAX_SCRAPE_CHARS:
        text = text[:MAX_SCRAPE_CHARS]

    content = text
    return title, content, text, final_url
