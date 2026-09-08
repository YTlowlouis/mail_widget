"""Parsing d'en-têtes email et conversion HTML -> texte, sans dépendance externe."""
from __future__ import annotations

import re
from html.parser import HTMLParser

_AUTH_RESULT_KEYS = ("spf", "dkim", "dmarc")
_BLOCK_TAGS = ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6")


def parse_auth_results(header_values: list[str]) -> dict[str, str]:
    """Extrait spf/dkim/dmarc depuis un ou plusieurs en-têtes Authentication-Results.

    Le résultat est déterministe (lu directement dans l'en-tête), jamais deviné par un modèle.
    """
    combined = " ".join(header_values)
    result: dict[str, str] = {}
    for key in _AUTH_RESULT_KEYS:
        match = re.search(rf"\b{key}=([a-zA-Z]+)", combined, flags=re.IGNORECASE)
        result[key] = match.group(1).lower() if match else "unknown"
    return result


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        joined = "".join(self._chunks)
        joined = re.sub(r"[ \t]+", " ", joined)
        joined = re.sub(r"\n\s*\n+", "\n\n", joined)
        return joined.strip()


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.text()


def truncate_body(text: str, limit: int = 2000) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + "…", True


def extract_unsubscribe_urls(list_unsubscribe: str | None) -> tuple[list[str], list[str]]:
    """Retourne (urls_http, urls_mailto) trouvées entre < > dans List-Unsubscribe."""
    if not list_unsubscribe:
        return [], []
    candidates = re.findall(r"<([^>]+)>", list_unsubscribe)
    http_urls = [u for u in candidates if u.lower().startswith(("http://", "https://"))]
    mailto_urls = [u for u in candidates if u.lower().startswith("mailto:")]
    return http_urls, mailto_urls
