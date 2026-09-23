"""Polite HTTP fetching + text extraction for the ingestion pipeline.

`requests` is already a hard dependency (see requirements.txt). HTML and PDF
*parsing* use the optional ``requirements-ingest.txt`` extras
(``beautifulsoup4``, ``pypdf``); when they are not installed, HTML falls back to
a small stdlib tag-stripper and PDF body text is simply unavailable (the entry
then verifies by reachability only).
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import requests

from app import config

# A number of government / treaty sites (India Code, WTO, …) serve a soft-404 or a
# block page to unrecognised User-Agents. This tool only ever issues plain GETs of
# public legal text for citation verification, so it presents a mainstream browser
# UA to get the same page a human reviewer would see. Override with INGEST_USER_AGENT.
_USER_AGENT = os.getenv("INGEST_USER_AGENT") or (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 (IP-SAKTI-Sahayak corpus verification)"
)
_TIMEOUT = 15
_RETRIES = 1  # a retrying host is usually just slow; don't punish `verify` runtime
_BACKOFF = 1.5
_CACHE_DIR = config.INGEST_DIR / "cache"


@dataclass
class FetchResult:
    url: str
    status: int  # HTTP status, or 0 on a transport error
    content_type: str
    raw: bytes
    fetched_at: str
    from_cache: bool
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def is_pdf(self) -> bool:
        return "pdf" in self.content_type.lower() or self.url.lower().split("?")[0].endswith(".pdf")


@dataclass
class ExtractResult:
    text: str
    parser: str  # "beautifulsoup" | "stdlib-html" | "pypdf" | "pdf-unparsed" | "empty"

    @property
    def ok(self) -> bool:
        return bool(self.text.strip()) and self.parser not in ("pdf-unparsed", "empty")


def _cache_path(url: str) -> Path:
    return _CACHE_DIR / hashlib.sha1(url.encode("utf-8")).hexdigest()


def fetch(url: str, *, use_cache: bool = True) -> FetchResult:
    """GET `url` politely, caching the raw body under `data/ingest/cache/`."""
    meta_path = _cache_path(url)
    body_path = meta_path.with_suffix(".body")
    if use_cache and meta_path.exists() and body_path.exists():
        status, content_type, fetched_at = meta_path.read_text(encoding="utf-8").split("\n", 2)
        return FetchResult(
            url=url,
            status=int(status),
            content_type=content_type,
            raw=body_path.read_bytes(),
            fetched_at=fetched_at,
            from_cache=True,
        )

    last_error: Optional[str] = None
    for attempt in range(_RETRIES + 1):
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": _USER_AGENT, "Accept": "*/*"},
                timeout=_TIMEOUT,
                allow_redirects=True,
            )
            fetched_at = datetime.now(timezone.utc).isoformat()
            result = FetchResult(
                url=url,
                status=resp.status_code,
                content_type=resp.headers.get("Content-Type", ""),
                raw=resp.content,
                fetched_at=fetched_at,
                from_cache=False,
            )
            if result.ok:
                _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                meta_path.write_text(
                    f"{result.status}\n{result.content_type}\n{fetched_at}", encoding="utf-8"
                )
                body_path.write_bytes(result.raw)
            return result
        except requests.exceptions.SSLError as exc:
            return FetchResult(url, 0, "", b"", datetime.now(timezone.utc).isoformat(), False, error=f"SSL: {exc}")
        except requests.RequestException as exc:  # noqa: PERF203 - retry loop
            last_error = str(exc)
            if attempt < _RETRIES:
                time.sleep(_BACKOFF ** attempt)

    return FetchResult(
        url=url,
        status=0,
        content_type="",
        raw=b"",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        from_cache=False,
        error=last_error,
    )


class _StdlibTextExtractor(HTMLParser):
    """Minimal fallback when BeautifulSoup isn't installed: drop script/style, keep text."""

    _SKIP = {"script", "style", "noscript", "head", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    @property
    def text(self) -> str:
        return "\n".join(self._chunks)


def _html_to_text(raw: bytes) -> ExtractResult:
    markup = raw.decode("utf-8", errors="replace")
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(markup, "html.parser")
        for tag in soup(["script", "style", "noscript", "head", "svg"]):
            tag.decompose()
        return ExtractResult(text=soup.get_text("\n", strip=True), parser="beautifulsoup")
    except ImportError:
        parser = _StdlibTextExtractor()
        parser.feed(markup)
        return ExtractResult(text=parser.text, parser="stdlib-html")


def _pdf_to_text(raw: bytes) -> ExtractResult:
    try:
        import io

        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        return ExtractResult(text=text, parser="pypdf" if text else "pdf-unparsed")
    except ImportError:
        return ExtractResult(text="", parser="pdf-unparsed")
    except Exception:  # noqa: BLE001 - a malformed PDF is just "unverifiable", never a crash
        return ExtractResult(text="", parser="pdf-unparsed")


def extract_text(result: FetchResult) -> ExtractResult:
    if not result.raw:
        return ExtractResult(text="", parser="empty")
    if result.is_pdf:
        return _pdf_to_text(result.raw)
    return _html_to_text(result.raw)
