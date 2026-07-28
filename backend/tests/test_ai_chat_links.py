"""Tests for Link Intelligence (Phase 6, Milestone 4). Pure parsing -- no network."""

from types import SimpleNamespace

import pytest

from app.ai_chat.links import (
    InvalidLinkError,
    LinkExtractor,
    LinkType,
    build_metadata,
    is_valid_url,
    normalize_url,
)

EX = LinkExtractor()


def _types(text):
    return [l.link_type for l in EX.extract(text)]


# --- extraction -------------------------------------------------------------


def test_extracts_multiple_urls():
    links = EX.extract("See https://example.com and https://github.com/a/b today.")
    assert [l.url for l in links] == ["https://example.com", "https://github.com/a/b"]


def test_trailing_punctuation_stripped():
    links = EX.extract("Check (https://example.com/path).")
    assert links[0].url == "https://example.com/path"


def test_order_is_preserved():
    links = EX.extract("https://a.com https://b.com https://c.com")
    assert [l.metadata.host for l in links] == ["a.com", "b.com", "c.com"]


# --- normalization ----------------------------------------------------------


def test_normalization_lowercases_host_strips_tracking_sorts_query():
    out = normalize_url("https://Example.COM/Path/?utm_source=x&b=2&a=1#frag")
    assert out == "https://example.com/Path?a=1&b=2"


def test_normalization_drops_default_port_and_trailing_slash():
    assert normalize_url("https://example.com:443/x/") == "https://example.com/x"
    assert normalize_url("http://example.com:80/") == "http://example.com"


# --- duplicate detection ----------------------------------------------------


def test_duplicate_urls_deduplicated():
    links = EX.extract("https://example.com/a https://example.com/a/ https://example.com/a")
    assert len(links) == 1


def test_tracking_variants_deduplicated():
    links = EX.extract("https://example.com/p?utm_source=a https://example.com/p")
    assert len(links) == 1


# --- provider detection -----------------------------------------------------


def test_github_detection_with_resource_id():
    link = EX.extract("https://github.com/goxl/ally/tree/main")[0]
    assert link.link_type == LinkType.GITHUB and link.metadata.resource_id == "goxl/ally"


def test_youtube_watch_and_short_links():
    watch = EX.extract("https://www.youtube.com/watch?v=abc123")[0]
    short = EX.extract("https://youtu.be/xyz789")[0]
    assert watch.link_type == LinkType.YOUTUBE and watch.metadata.resource_id == "abc123"
    assert short.link_type == LinkType.YOUTUBE and short.metadata.resource_id == "xyz789"


def test_google_docs_detection_with_doc_id():
    link = EX.extract("https://docs.google.com/document/d/DOC_123/edit")[0]
    assert link.link_type == LinkType.GOOGLE_DOCS and link.metadata.resource_id == "DOC_123"


def test_google_drive_detection():
    link = EX.extract("https://drive.google.com/file/d/FILE9/view")[0]
    assert link.link_type == LinkType.GOOGLE_DRIVE and link.metadata.resource_id == "FILE9"


def test_notion_linkedin_twitter_website_detection():
    assert _types("https://www.notion.so/page") == [LinkType.NOTION]
    assert _types("https://www.linkedin.com/in/someone") == [LinkType.LINKEDIN]
    assert _types("https://twitter.com/user") == [LinkType.TWITTER]
    assert _types("https://x.com/user") == [LinkType.TWITTER]
    assert _types("https://example.com") == [LinkType.WEBSITE]


def test_detect_type_helper():
    assert EX.detect_type("https://github.com/a/b") == LinkType.GITHUB
    assert EX.detect_type("not a url") == LinkType.UNKNOWN


def test_is_secure_flag():
    assert build_metadata("https://example.com").is_secure is True
    assert build_metadata("http://example.com").is_secure is False


# --- malformed handling -----------------------------------------------------


def test_malformed_links_skipped():
    assert EX.extract("http:// broken, ftp://x.com, just words, mailto:a@b.com") == ()


def test_no_urls_returns_empty():
    assert EX.extract("no links at all here") == ()


def test_is_valid_url():
    assert is_valid_url("https://example.com") and not is_valid_url("http://")
    assert not is_valid_url("notaurl") and not is_valid_url("ftp://x.com")


def test_parse_raises_on_malformed():
    with pytest.raises(InvalidLinkError):
        EX.parse("notaurl")


def test_parse_single_valid_url():
    link = EX.parse("https://github.com/a/b")
    assert link.link_type == LinkType.GITHUB


# --- Part 5 composition + determinism ---------------------------------------


def test_from_messages_extracts_unique_links_read_only():
    messages = [
        SimpleNamespace(content="see https://github.com/a/b"),
        SimpleNamespace(content="again https://github.com/a/b and https://youtu.be/z"),
        SimpleNamespace(content="no links"),
    ]
    links = EX.from_messages(messages)
    assert [l.link_type for l in links] == [LinkType.GITHUB, LinkType.YOUTUBE]


def test_deterministic_execution():
    text = "https://github.com/a/b and https://docs.google.com/document/d/D/edit"
    first = [(l.url, l.link_type, l.metadata.resource_id) for l in EX.extract(text)]
    second = [(l.url, l.link_type, l.metadata.resource_id) for l in EX.extract(text)]
    assert first == second
