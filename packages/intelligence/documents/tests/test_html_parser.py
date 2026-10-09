from packages.intelligence.documents.chunking import chunk_sections
from packages.intelligence.documents.parsers import HTMLDocumentParser


def test_html_parser_extracts_article_sections_and_drops_page_chrome() -> None:
    body = b"""
    <html>
      <head><title>Incident analysis</title><style>.x{}</style></head>
      <body>
        <header>site header</header>
        <nav>home docs pricing</nav>
        <main>
          <h1>Authentication bypass in vLLM</h1>
          <p>The vulnerable endpoint accepted unauthenticated requests.</p>
          <h2>Root cause</h2>
          <p>A missing authorization check exposed the control path.</p>
          <ul><li>Impact: remote request execution.</li></ul>
          <h2>Mitigation</h2>
          <p>Upgrade to the fixed release and enforce authentication.</p>
        </main>
        <footer>copyright</footer>
        <script>alert('noise')</script>
      </body>
    </html>
    """

    sections = HTMLDocumentParser().parse(body)
    assert [item.section for item in sections] == [
        "Authentication bypass in vLLM",
        "Root cause",
        "Mitigation",
    ]
    text = "\n".join(item.text for item in sections)
    assert "site header" not in text
    assert "home docs pricing" not in text
    assert "copyright" not in text
    assert "alert" not in text
    assert "unauthenticated requests" in text
    assert "missing authorization check" in text
    assert "fixed release" in text
    assert sections[1].source_locator == {
        "kind": "html_section",
        "heading": "Root cause",
        "section_index": 1,
    }

    chunks = chunk_sections(sections, chunk_size=80, overlap=10)
    root_cause = next(item for item in chunks if item.section == "Root cause")
    assert root_cause.source_locator["kind"] == "html_section"
    assert root_cause.source_locator["heading"] == "Root cause"


def test_html_parser_falls_back_to_body_text_without_block_markup() -> None:
    sections = HTMLDocumentParser().parse(b"<html><body>plain security bulletin</body></html>")
    assert len(sections) == 1
    assert sections[0].text == "plain security bulletin"
    assert sections[0].source_locator["kind"] == "html_document"


def test_html_parser_prefers_article_body_over_related_post_cards() -> None:
    body = b"""
    <html><body><main>
      <div class="entry-content">
        <p>AI-themed phishing campaigns impersonate trusted tools.</p>
      </div>
      <section class="related-posts"><article><h2>Different post</h2>
        <p>Unrelated CISO perspectives and vulnerability risks.</p></article></section>
    </main></body></html>
    """
    sections = HTMLDocumentParser().parse(body)
    text = "\n".join(section.text for section in sections)
    assert "AI-themed phishing campaigns" in text
    assert "Unrelated CISO" not in text


def test_html_parser_prefers_post_content_over_related_article_cards() -> None:
    body = b"""
    <html><body>
      <div class="single-post__content post-content">
        <h1>Incident investigation</h1>
        <p>Investigators traced the theft through several exchanges.</p>
        <h2>Response</h2>
        <p>The affected organization suspended withdrawals.</p>
      </div>
      <section class="related-posts">
        <article class="related-posts__card"><h2>Another incident</h2>
          <p>This preview is not part of the investigation.</p></article>
      </section>
    </body></html>
    """
    sections = HTMLDocumentParser().parse(body)
    text = "\n".join(section.text for section in sections)
    assert "Investigators traced the theft" in text
    assert "suspended withdrawals" in text
    assert "This preview is not part" not in text
