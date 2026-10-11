from packages.intelligence.feed.policy import activity_kind, topic_matches


def test_identity_and_ordinary_development_are_not_activities():
    assert activity_kind("Repo", "security project", []) is None
    assert activity_kind("PullRequest", "Update documentation", ["belongs-to-repo"]) is None
    assert activity_kind("PullRequest", "Security fix", ["belongs-to-repo"]) is None
    assert activity_kind("PullRequest", "Fix CVE-2026-1234", ["fixes"]) == "security"
    assert activity_kind("Release", "v1.2.3", ["belongs-to-repo"]) is None
    assert (
        activity_kind("Release", "Security release fixing authentication bypass", []) == "security"
    )
    assert activity_kind("Release", "Major release with breaking changes", []) == "release"


def test_topic_matching_does_not_match_partial_words():
    assert topic_matches("Ray fixes isolation", ["Ray"]) == ["Ray"]
    assert topic_matches("Array implementation", ["Ray"]) == []


def test_same_content_from_different_objects_has_stable_activity_identity():
    from packages.intelligence.feed import activity_identity

    assert activity_identity(
        "source-a", "Security report", "Verified report body"
    ) == activity_identity("source-b", "Security report", "Verified report body")


def test_ordinary_documents_are_not_recommendation_fill():
    assert activity_kind("Document", "Weekly product marketing roundup", []) is None
    assert activity_kind("Document", "Major release introduces breaking changes", []) == "article"
    assert (
        activity_kind("Document", "New authentication bypass security advisory", []) == "security"
    )


def test_generic_security_landing_and_index_urls_are_not_updates():
    assert (
        activity_kind(
            "Document", "Application and API security", [], source_urls=["https://vendor.example/"]
        )
        is None
    )
    assert (
        activity_kind(
            "Document",
            "Security Dashboard",
            [],
            source_urls=["https://vendor.example/en/dashboard"],
        )
        is None
    )
    assert (
        activity_kind(
            "Document", "Security research", [], source_urls=["https://vendor.example/blog/"]
        )
        is None
    )
    assert (
        activity_kind(
            "Document",
            "Security report on CVE-2026-1234",
            [],
            source_urls=["https://vendor.example/blog/cve-2026-1234"],
        )
        == "security"
    )
    assert (
        activity_kind(
            "Document", "Security advisory", [], source_urls=["https://vendor.example/?p=123"]
        )
        == "security"
    )


def test_extracted_concepts_and_placeholder_vulnerabilities_are_not_activities():
    assert activity_kind("SecurityControl", "simple application and API security", []) is None
    assert activity_kind("attack", "indirect_prompt_injection security attack", []) is None
    assert (
        activity_kind(
            "Vulnerability",
            "this vulnerability",
            [],
            identity="this vulnerability",
            title="this vulnerability",
        )
        is None
    )
    assert (
        activity_kind(
            "Vulnerability",
            "remaining potential vulnerabilities",
            [],
            identity="remaining_potential_vulnerabilities",
            title="remaining_potential_vulnerabilities",
        )
        is None
    )
    assert activity_kind("Vulnerability", "", [], identity="cve:CVE-2026-12345") == "security"
    assert (
        activity_kind(
            "Vulnerability",
            "Ray permits unauthenticated remote code execution",
            [],
            title="Ray permits unauthenticated remote code execution",
        )
        == "security"
    )
    assert (
        activity_kind(
            "Document",
            "Security Dashboard",
            [],
            source_urls=["https://vendor.example/reports/dashboard"],
        )
        is None
    )
