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


def test_html_parser_prefers_article_over_main_chrome_and_removes_injected_banner() -> None:
    body = b"""<main><div role="navigation">Home Login</div>
    <div class="w-richtext"><h2>Webflow Input Enhancer</h2>
    <p>For the best experience, this project uses the Webflow Input Enhancer extension.
    We highly recommend installing it.</p>
    <a href="/install">Click here to download</a></div>
    <article><header><h1>Security findings</h1></header><p>The attacker exploited the endpoint.</p>
    <h2>Evidence</h2><p>The proof of concept uses a CAPTCHA bypass.</p></article>
    <div class="related-posts"><p>Other resources</p></div></main>"""
    sections = HTMLDocumentParser().parse(body)
    text = "\n".join(section.text for section in sections)
    assert "Webflow Input Enhancer" not in text
    assert "Other resources" not in text
    assert "The attacker exploited" in text
    assert sections[0].section == "Security findings"


def test_html_parser_cleans_banner_and_navigation_without_article_wrapper() -> None:
    body = b"""<body><div><h2>Webflow Input Enhancer</h2>
    <p>For the best experience, this project uses the Webflow Input Enhancer extension.
    We highly recommend installing it.</p>
    <a>Click here to download</a></div><div role="navigation"><p>Home Login</p></div>
    <div><h1>Research</h1><p>Researchers documented an exploit.</p>
    <p>The Webflow Input Enhancer extension itself is discussed as evidence.</p></div></body>"""
    text = "\n".join(section.text for section in HTMLDocumentParser().parse(body))
    assert "recommend installing" not in text
    assert "Home Login" not in text
    assert "Researchers documented" in text
    assert "discussed as evidence" in text


def test_html_parser_prefers_full_article_over_a_related_article_card() -> None:
    sections = HTMLDocumentParser().parse(b"""<main>
    <article class="card"><h2>Related story</h2><p>Unrelated preview</p></article>
    <article><header><h1>Research findings</h1></header>
    <div><p>Detailed attack evidence and mitigation.</p></div></article></main>""")
    assert sections[0].section == "Research findings"
    assert "Unrelated preview" not in "\n".join(section.text for section in sections)


def test_html_parser_preserves_leaf_div_notice_labels_for_quality_assessment() -> None:
    from packages.intelligence.documents.quality import assess_document_quality

    # Reduced DOM from the retained European Commission multilingual outage page:
    # notice titles are ordinary divs; only the apology is marked as a paragraph.
    body = """<main>
    <div><div>Der Server ist vorübergehend nicht verfügbar</div>
    <p>Wir entschuldigen uns für etwaige Unannehmlichkeiten.</p></div>
    <div><div>The server is temporarily unavailable</div>
    <p>We apologise for any inconvenience. Please try again later.</p></div>
    <div><div>Le serveur est temporairement indisponible</div>
    <p>Veuillez nous excuser pour ce désagrément.</p></div>
    </main>""".encode()
    sections = HTMLDocumentParser().parse(body)
    text = "\n".join(section.text for section in sections)
    assert "The server is temporarily unavailable" in text
    assert text.count("Please try again later") == 1
    assert not assess_document_quality(text).usable


def test_html_parser_keeps_leaf_div_evidence_but_not_navigation_or_widget() -> None:
    body = b"""<main><nav><div>Navigation home</div></nav>
    <div role="navigation"><div>Account login</div></div>
    <div><h2>Webflow Input Enhancer</h2>
    <p>This project uses the Webflow Input Enhancer extension. We recommend installing it.</p>
    </div><article><h1>Research findings</h1>
    <div>Direct evidence with <strong>inline emphasis</strong>.</div>
    <div><p>A nested paragraph should appear once.</p></div></article></main>"""
    text = "\n".join(section.text for section in HTMLDocumentParser().parse(body))
    assert "Direct evidence with inline emphasis" in text
    assert text.count("A nested paragraph should appear once") == 1
    assert "Navigation home" not in text
    assert "Account login" not in text
    assert "recommend installing" not in text


def test_explicit_blog_body_excludes_navigation_and_community_comments():
    parser = HTMLDocumentParser()
    for cls in ("text--blog-content", "blog-content prose"):
        sections = parser.parse(
            f"""<main><div>Vendor navigation and product catalog</div>
            <div class="{cls}"><h1>Agent intrusion</h1>
            <p>The agent reached an external production system.</p></div>
            <div class="prose">Community speculation is not the publisher report.</div>
            </main>""".encode()
        )
        body = "\n".join(section.text for section in sections)
        assert "external production system" in body
        assert "Vendor navigation" not in body
        assert "Community speculation" not in body
