from typing import Tuple
from urllib.parse import urlparse

from .extract_text import (
    extract_text_from_url_async,
    is_available as extract_available,
    merge_extracted_text,
)


async def scrape_url(url: str) -> Tuple[str, str, str, str]:
    if not extract_available():
        raise RuntimeError(
            "The 'extract-text' module is not available. URL scraping is disabled."
        )

    extracted_items = await extract_text_from_url_async(url)
    if not extracted_items:
        raise ValueError(f"Could not extract any content from URL: {url}")

    text = merge_extracted_text(extracted_items)

    # Find the main page content to get the final URL and derive a title
    final_url = url
    title = ""
    for item in extracted_items:
        if item.get("filename") == "page_content":
            final_url = item.get("path", url)
            break

    try:
        title = urlparse(final_url).hostname or final_url
    except Exception:
        title = final_url

    # The function signature requires returning title, content, text, final_url
    # where content and text are the same.
    return title, text, text, final_url
