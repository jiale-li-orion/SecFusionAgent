from datetime import UTC, datetime

import pytest

from packages.sources.adapters.html_article_metadata import extract_article_metadata


def test_article_metadata_prefers_heading_and_original_publication() -> None:
    result = extract_article_metadata(b"""<meta property="og:title" content="Marketing title">
    <meta property="article:published_time" content="2025-05-14T09:30:00+00:00">
    <meta property="article:modified_time" content="2026-10-15T00:00:00Z">
    <article><h1>AlphaEvolve research</h1></article>""")
    assert result.title == "AlphaEvolve research"
    assert result.published_at == datetime(2025, 5, 14, 9, 30, tzinfo=UTC)
    assert result.metadata["title_origin"] == "html:h1"
    assert result.metadata["published_at_origin"] == "html:article:published_time"


def test_article_metadata_jsonld_article_graph_and_malformed_script() -> None:
    result = extract_article_metadata(b"""<script type="application/ld+json">{broken</script>
    <script type="application/ld+json">{"@graph":[
      {"@type":"Event","datePublished":"2030-01-01T00:00:00Z"},
      {"@type":"NewsArticle","datePublished":"2024-02-03T04:05:06+02:00"}
    ]}</script><meta property="og:title" content="Trusted title">""")
    assert result.title == "Trusted title"
    assert result.published_at == datetime.fromisoformat("2024-02-03T04:05:06+02:00")
    assert result.metadata["published_at_origin"] == "html:jsonld:datePublished"


@pytest.mark.parametrize(
    "body",
    [
        b'<article><time itemprop="datePublished" datetime="2025-05-14">May 14'
        b", 2025</time></article>",
        b'<meta property="article:published_time" content="2025-05-14">',
        b'<article><time class="published" datetime="2025-05-14">May 14, 2025</time></article>',
    ],
)
def test_date_only_preserves_precision_without_fabricating_an_instant(body: bytes) -> None:
    result = extract_article_metadata(body)
    assert result.published_at is None
    assert result.metadata["published_date"] == "2025-05-14"
    assert result.metadata["published_at_precision"] == "date"


@pytest.mark.parametrize(
    "body",
    [
        b"<title>Site name</title><p>No article metadata</p>",
        b'<script type="application/ld+json">{"@type":"Event","datePublished":'
        b'"2030-01-01T00:00:00Z"}</script>',
        b'<script type="application/ld+json">{"@type":"Article","dateModified"'
        b':"2030-01-01T00:00:00Z"}</script>',
        b'<article><time class="updated" datetime="2030-01-01T00:00:00Z">Updated</time></article>',
        b'<article><time class="event-date" datetime="2030-01-01T00:00:00Z">Ev'
        b"ent date</time></article>",
        b'<article><time datetime="2025-01-01"></time><time datetime="2030-01-'
        b'01"></time></article>',
    ],
)
def test_absent_or_unrelated_dates_are_not_article_publication(body: bytes) -> None:
    result = extract_article_metadata(body)
    assert result.published_at is None
    assert result.title is None
    assert "published_at_origin" not in result.metadata


def test_timezone_free_timestamp_is_retained_without_assuming_utc() -> None:
    result = extract_article_metadata(
        b'<meta property="article:published_time" content="2025-05-14T09:30:00">'
    )
    assert result.published_at is None
    assert result.metadata["published_at_raw"] == "2025-05-14T09:30:00"
    assert result.metadata["published_at_precision"] == "local_datetime"


def test_unrelated_article_jsonld_does_not_supply_publication_date() -> None:
    result = extract_article_metadata(
        b'<script type="application/ld+json">'
        b'{"@type":"NewsArticle","url":"https://example.test/other",'
        b'"datePublished":"2030-01-01T00:00:00Z"}</script>',
        page_url="https://example.test/current",
    )
    assert result.published_at is None
    assert "published_at_origin" not in result.metadata


def test_ambiguous_article_jsonld_dates_are_not_guessed() -> None:
    result = extract_article_metadata(
        b'<script type="application/ld+json">['
        b'{"@type":"Article","datePublished":"2030-01-01T00:00:00Z"},'
        b'{"@type":"Article","datePublished":"2020-01-01T00:00:00Z"}]</script>'
    )
    assert result.published_at is None


@pytest.mark.parametrize(
    "body",
    [
        b'<article><p>Updated: <time datetime="2026-10-15T12:00:00Z">'
        b"15 October 2026</time></p></article>",
        b"<article><h1>Security conference preview</h1><p>The conference starts on "
        b'<time datetime="2026-12-01T09:00:00Z">December 1</time>.</p></article>',
        b'<article><time datetime="2025-05-14">May 14, 2025</time></article>',
    ],
)
def test_generic_time_is_not_publication_evidence(body: bytes) -> None:
    result = extract_article_metadata(body)
    assert result.published_at is None
    assert "published_at_origin" not in result.metadata


def test_title_and_time_follow_current_article_not_related_sidebar() -> None:
    result = extract_article_metadata(
        b"<aside><article><h1>Related story</h1>"
        b'<time class="published" datetime="2030-01-01T00:00:00Z">Jan 1</time>'
        b"</article></aside><article><h1>Current research</h1>"
        b'<time class="published" datetime="2025-05-14T00:00:00Z">May 14</time>'
        b"<p>Current article evidence.</p></article>"
    )
    assert result.title == "Current research"
    assert result.published_at == datetime(2025, 5, 14, tzinfo=UTC)


def test_conflicting_publication_meta_values_abstain() -> None:
    result = extract_article_metadata(
        b'<meta property="article:published_time" content="2030-01-01T00:00:00Z">'
        b'<meta property="article:published_time" content="2025-05-14T00:00:00Z">'
    )
    assert result.published_at is None
    assert "published_at_origin" not in result.metadata
