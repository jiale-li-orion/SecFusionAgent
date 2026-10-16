"""Conservative, versioned material checks; never judge a source's factual claims."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

QUALITY_VERSION = "material-quality-v2"


class DocumentMaterialRejectedError(ValueError):
    """Terminal material rejection, distinct from processing or provider failures."""


_ERROR_HEADINGS = frozenset(
    {
        "the server is temporarily unavailable",
        "service unavailable",
        "503 service unavailable",
        "503 service temporarily unavailable",
        "502 bad gateway",
        "bad gateway",
        "404 not found",
        "page not found",
        "der server ist vorübergehend nicht verfügbar",
        "le serveur est temporairement indisponible",
        "сървърът е временно недостъпен",  # noqa: RUF001 — Bulgarian outage notice
    }
)
_ACCESS_HEADINGS = frozenset(
    {
        "access denied",
        "403 forbidden",
        "forbidden",
        "just a moment",
        "verify you are human",
        "checking your browser",
        "sign in to continue",
        "log in to continue",
    }
)
_BOILERPLATE = frozenset(
    {
        "home",
        "login",
        "log in",
        "sign in",
        "register",
        "privacy policy",
        "contact us",
        "terms of use",
        "cookie policy",
        "首页",
        "登录",
        "注册",
        "联系我们",
        "网站地图",
    }
)
_TEMPLATE_PHRASES = (
    "please try again later",
    "we apologise for any inconvenience",
    "we apologize",
    "you do not have permission",
    "verify you are human",
    "enable javascript and cookies",
    "checking if the site connection is secure",
    "please log in to access this content",
)


@dataclass(frozen=True, slots=True)
class DocumentQualityAssessment:
    usable: bool
    reasons: tuple[str, ...] = ()
    version: str = QUALITY_VERSION

    @property
    def status(self) -> str:
        return "usable" if self.usable else "rejected"

    def to_metadata(self) -> dict[str, object]:
        return {
            "version": self.version,
            "status": self.status,
            "usable": self.usable,
            "reasons": list(self.reasons),
        }


def assess_document_quality(
    text: str, title: str | None = None, *, canonical_url: str | None = None
) -> DocumentQualityAssessment:
    """Recognize empty bodies and explicit delivery templates, not error-related topics.

    A discovery title is deliberately not evidence that a downloaded body is usable.
    Unknown or short prose remains usable; this is not an editorial quality score.
    """
    if canonical_url:
        url = urlsplit(canonical_url)
        path = url.path.rstrip("/").casefold()
        if url.hostname in {"crowdstrike.com", "www.crowdstrike.com"} and (
            "/blog/category." in path
            or path
            in {"/en-us/blog", "/en-us/blog/categories-overview", "/en-us/blog/recent-articles"}
        ):
            return DocumentQualityAssessment(False, ("catalog_page",))
    lines = [" ".join(line.casefold().split()).strip(" .!:…") for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return DocumentQualityAssessment(False, ("empty_content",))
    normalized = "\n".join(lines)
    if (
        "webflow input enhancer" in normalized[:500]
        and "this project uses the webflow input enhancer extension" in normalized
        and "recommend installing it" in normalized
    ):
        return DocumentQualityAssessment(False, ("boilerplate_contamination",))
    # The EU multilingual outage template is long but consists of translated notices.
    headings = sum(line in _ERROR_HEADINGS for line in lines)
    if headings >= 3 and "please try again later" in normalized:
        return DocumentQualityAssessment(False, ("error_page",))
    first = lines[0]
    if first in _ERROR_HEADINGS | _ACCESS_HEADINGS and len(normalized) <= 1000:
        template_lines = sum(
            line in _ERROR_HEADINGS | _ACCESS_HEADINGS
            or re.fullmatch(r"(?:nginx|openresty|apache)(?:/[\d.]+)?", line) is not None
            or any(phrase in line for phrase in _TEMPLATE_PHRASES)
            for line in lines
        )
        if template_lines == len(lines):
            reason = "access_challenge" if first in _ACCESS_HEADINGS else "error_page"
            return DocumentQualityAssessment(False, (reason,))
    if all(line in _BOILERPLATE for line in lines):
        return DocumentQualityAssessment(False, ("boilerplate_only",))
    return DocumentQualityAssessment(True)
