import pytest

from packages.intelligence.documents.quality import assess_document_quality


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("  ", "empty_content"),
        (
            "The server is temporarily unavailable\nWe apologise for any inconveni"
            "ence. Please try again later.",
            "error_page",
        ),
        (
            "bg\nСървърът е временно недостъпен\nde\nDer Server ist vorübergehend ni"  # noqa: RUF001 — Bulgarian outage notice
            "cht verfügbar\nen\nThe server is temporarily unavailable\nWe apologise "
            "for any inconvenience. Please try again later.\nfr\nLe serveur est tem"
            "porairement indisponible",
            "error_page",
        ),
        ("Access denied\nYou do not have permission to access this resource.", "access_challenge"),
        ("Just a moment...\nVerify you are human", "access_challenge"),
        ("Home\nLogin\nPrivacy policy\nContact us", "boilerplate_only"),
        (
            "Webflow Input Enhancer\nFor the best experience, this project uses th"
            "e Webflow Input Enhancer extension. We highly recommend installing i"
            "t.\nClick here to download\nSecurity research follows.",
            "boilerplate_contamination",
        ),
    ],
)
def test_quality_rejects_recognizable_non_material(text: str, reason: str) -> None:
    assessment = assess_document_quality(text, title="A legitimate discovery card")
    assert not assessment.usable
    assert reason in assessment.reasons
    assert assessment.to_metadata() == {
        "version": "material-quality-v2",
        "status": "rejected",
        "usable": False,
        "reasons": list(assessment.reasons),
    }


@pytest.mark.parametrize(
    "text",
    [
        "The attack produced HTTP 503 errors. The server is temporarily unava"
        "ilable message was logged.",
        "Error handling research\nWe study access denied failures and CAPTCHA "
        "bypass in deployed systems.",
        "Service unavailable\nOur experiments measure how overload affects dis"
        "tributed inference. The benchmark compares recovery time and success"
        "ful requests.",
        "A short advisory: upgrade the vulnerable service.",
        "Webflow Input Enhancer was exploited by attackers to inject scripts into the article.",
    ],
)
def test_quality_preserves_research_discussing_errors(text: str) -> None:
    assert assess_document_quality(text).usable


@pytest.mark.parametrize(
    "text,reason",
    [
        ("404 Not Found\nnginx", "error_page"),
        ("503 Service Temporarily Unavailable\nnginx", "error_page"),
        ("Sign in to continue\nPlease log in to access this content.", "access_challenge"),
        (
            "Just a moment...\nChecking if the site connection is secure\n"
            "Enable JavaScript and cookies to continue",
            "access_challenge",
        ),
    ],
)
def test_delivery_template_variants(text: str, reason: str) -> None:
    result = assess_document_quality(text)
    assert not result.usable
    assert result.reasons == (reason,)


@pytest.mark.parametrize(
    "path", ["category.cloud-security/", "categories-overview/", "recent-articles/"]
)
def test_crowdstrike_catalog_is_not_article_material(path: str) -> None:
    quality = assess_document_quality(
        "Prompt injection research and AI security articles",
        canonical_url=f"https://www.crowdstrike.com/en-us/blog/{path}",
    )
    assert not quality.usable
    assert quality.reasons == ("catalog_page",)
    assert assess_document_quality(
        "Prompt injection research and AI security articles",
        canonical_url="https://www.crowdstrike.com/en-us/blog/unknown-threat-actor-uses-artex-to-target-south-korean-finance/",
    ).usable
