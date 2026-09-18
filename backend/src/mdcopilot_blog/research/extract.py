"""Extraction: trafilatura, newspaper4k, pypdfium2, dates."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Literal

from mdcopilot_blog.domain.enums import AccessMode, DateSource
from mdcopilot_blog.domain.text import count_words

ExtractionMethod = Literal["trafilatura_precision", "trafilatura_recall", "newspaper4k", "pdfium", "none"]
FALLBACK_WORD_THRESHOLD = 150
MIN_FULL_TEXT_WORDS = 50
_EARLIEST = datetime(1995, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class DatedValue:
    value: datetime
    source: DateSource


@dataclass(frozen=True)
class Extraction:
    text: str | None
    word_count: int
    title: str | None
    sitename: str | None
    published: DatedValue | None
    method: ExtractionMethod
    access_mode: AccessMode
    content_hash: str | None


def parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _plausible(candidate: datetime, now: datetime) -> bool:
    from datetime import timedelta

    return _EARLIEST <= candidate <= now + timedelta(days=1)


class _LdJsonAndMetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_ld_json = False
        self.ld_json_chunks: list[str] = []
        self.metas: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self.in_ld_json = True
        elif tag == "meta":
            self.metas.append(attributes)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.in_ld_json:
            self.in_ld_json = False

    def handle_data(self, data: str) -> None:
        if self.in_ld_json:
            self.ld_json_chunks.append(data)


def _walk_ld_json(node: object, now: datetime) -> datetime | None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "datePublished" and isinstance(value, str):
                parsed = parse_datetime(value)
                if parsed is not None and _plausible(parsed, now):
                    return parsed
        for value in node.values():
            found = _walk_ld_json(value, now)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _walk_ld_json(item, now)
            if found is not None:
                return found
    return None


def structured_date(html: str, *, now: datetime | None = None) -> DatedValue | None:
    current = now or datetime.now(UTC)
    parser = _LdJsonAndMetaParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - malformed HTML has no structured date
        return None
    for chunk in parser.ld_json_chunks:
        try:
            document = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        found = _walk_ld_json(document, current)
        if found is not None:
            return DatedValue(value=found, source=DateSource.JSONLD)
    for meta in parser.metas:
        if meta.get("property") == "article:published_time" or meta.get("name") == "article:published_time":
            parsed = parse_datetime(meta.get("content", ""))
            if parsed is not None and _plausible(parsed, current):
                return DatedValue(value=parsed, source=DateSource.META)
    return None


def htmldate_date(html: str, *, now: datetime | None = None) -> DatedValue | None:
    current = now or datetime.now(UTC)
    try:
        import htmldate  # type: ignore[import-untyped, unused-ignore]

        found = htmldate.find_date(html, extensive_search=True, original_date=True, outputformat="%Y-%m-%dT%H:%M:%S%z")
    except Exception:  # noqa: BLE001 - htmldate failures mean no date
        return None
    if not found:
        return None
    parsed = parse_datetime(found)
    if parsed is None or not _plausible(parsed, current):
        return None
    return DatedValue(value=parsed, source=DateSource.HTMLDATE)


def _run_trafilatura(html: str, url: str, *, favor_recall: bool) -> tuple[str, str | None, str | None]:
    import trafilatura  # type: ignore[import-untyped, unused-ignore]

    try:
        result = trafilatura.bare_extraction(
            html,
            url=url,
            with_metadata=True,
            favor_precision=not favor_recall,
            favor_recall=favor_recall,
        )
    except Exception:  # noqa: BLE001 - trafilatura failures fall through
        return "", None, None
    if result is None:
        return "", None, None
    if not isinstance(result, dict):
        # Current trafilatura returns a Document; older releases returned a mapping.
        result = result.as_dict()
    text = result.get("text") or ""
    title = result.get("title")
    sitename = result.get("sitename")
    return text, title if isinstance(title, str) else None, sitename if isinstance(sitename, str) else None


def _run_newspaper(html: str, url: str) -> tuple[str, str | None]:
    from newspaper import Article  # type: ignore[import-untyped, unused-ignore]

    article = Article(url)
    try:
        article.download(input_html=html)
        article.parse()
    except Exception:  # noqa: BLE001 - newspaper4k failures mean no fallback text
        return "", None
    return article.text or "", article.title or None


def extract_html(html: str, *, url: str, now: datetime | None = None) -> Extraction:
    current = now or datetime.now(UTC)
    text, title, sitename = _run_trafilatura(html, url, favor_recall=False)
    method: ExtractionMethod = "trafilatura_precision"
    if count_words(text) < FALLBACK_WORD_THRESHOLD:
        recall_text, recall_title, recall_sitename = _run_trafilatura(html, url, favor_recall=True)
        if count_words(recall_text) > count_words(text):
            text, title, sitename = recall_text, recall_title or title, recall_sitename or sitename
            method = "trafilatura_recall"
    if count_words(text) < FALLBACK_WORD_THRESHOLD:
        news_text, news_title = _run_newspaper(html, url)
        if count_words(news_text) > count_words(text):
            text, title = news_text, news_title or title
            method = "newspaper4k"
    word_count = count_words(text)
    if word_count >= MIN_FULL_TEXT_WORDS:
        stripped = text.strip()
        return Extraction(
            text=stripped,
            word_count=word_count,
            title=title if title and title.strip() else None,
            sitename=sitename,
            published=structured_date(html, now=current) or htmldate_date(html, now=current),
            method=method,
            access_mode=AccessMode.FULL_TEXT,
            content_hash=hashlib.sha256(stripped.encode("utf-8")).hexdigest(),
        )
    return Extraction(
        text=None,
        word_count=word_count,
        title=title if title and title.strip() else None,
        sitename=sitename,
        published=structured_date(html, now=current) or htmldate_date(html, now=current),
        method=method if word_count > 0 else "none",
        access_mode=AccessMode.METADATA_ONLY,
        content_hash=None,
    )


def extract_pdf(data: bytes, *, now: datetime | None = None) -> Extraction:
    current = now or datetime.now(UTC)
    try:
        import pypdfium2 as pdfium  # type: ignore[import-untyped, unused-ignore]

        document = pdfium.PdfDocument(data)
        try:
            pages: list[str] = []
            for index in range(min(len(document), 200)):
                page = document[index]
                text_page = page.get_textpage()
                pages.append(text_page.get_text_range() or "")
                text_page.close()
                page.close()
            text = "\n".join(pages).strip()
        finally:
            document.close()
    except Exception:  # noqa: BLE001 - a broken PDF means no text
        return Extraction(
            text=None,
            word_count=0,
            title=None,
            sitename=None,
            published=None,
            method="none",
            access_mode=AccessMode.METADATA_ONLY,
            content_hash=None,
        )
    word_count = count_words(text)
    if word_count >= MIN_FULL_TEXT_WORDS:
        return Extraction(
            text=text,
            word_count=word_count,
            title=None,
            sitename=None,
            published=None,
            method="pdfium",
            access_mode=AccessMode.FULL_TEXT,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
    return Extraction(
        text=None,
        word_count=word_count,
        title=None,
        sitename=None,
        published=structured_date("", now=current),
        method="pdfium",
        access_mode=AccessMode.METADATA_ONLY,
        content_hash=None,
    )


def looks_like_pdf(content_type: str | None, body: bytes) -> bool:
    if content_type and content_type.strip().lower().startswith("application/pdf"):
        return True
    return body.startswith(b"%PDF-")


def looks_like_html(content_type: str | None, body: bytes) -> bool:
    if content_type and "html" in content_type.lower():
        return True
    stripped = body.lstrip()
    return bool(stripped) and stripped.startswith(b"<") and not looks_like_pdf(None, stripped)
