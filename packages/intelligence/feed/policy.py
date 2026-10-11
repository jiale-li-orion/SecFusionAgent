"""Deterministic, evidence-gated activity eligibility and feed ordering."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

SECURITY = re.compile(
    r"\b(?:CVE-\d{4}-\d+|GHSA-[\w-]+|vulnerabilit\w*|security|exploit\w*|advisory|"
    r"authentication bypass|remote code execution|prompt injection)\b|漏洞|安全|攻击|补丁",
    re.I,
)
SECURITY_RELATIONS = {
    "references-development-object",
    "fixes",
    "fixed-by",
    "remediates",
    "has-patch",
    "patch-for",
    "discusses-vulnerability",
    "affects",
    "applicability-status",
    "has-poc",
}
TEXT_FIELDS = {
    "title",
    "name",
    "display_name",
    "summary",
    "description",
    "abstract",
    "body",
    "github_title",
    "github_release_name",
    "github_body",
    "github_release_body",
    "github_commit_message",
}


IDENTITY_TYPES = {
    "Repo",
    "Repository",
    "Product",
    "Package",
    "InternetAsset",
    "Weakness",
    "Organization",
    "Person",
}


ACTIVITY_TYPES = {
    "Vulnerability",
    "SecurityIncident",
    "Incident",
    "ExploitArtifact",
    "Document",
    "ResearchWork",
    "NormativeDocument",
    "Release",
    "SoftwareVersion",
    "PullRequest",
    "Commit",
    "Issue",
}
VULNERABILITY_ID = re.compile(
    r"\b(?:CVE-\d{4}-\d+|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}|"
    r"(?:CNVD|CNNVD|PYSEC|RUSTSEC|GO|GSD)-\d{4}-\d+)\b",
    re.I,
)
_GENERIC_VULNERABILITY_WORDS = {
    "this",
    "that",
    "the",
    "these",
    "those",
    "a",
    "an",
    "remaining",
    "potential",
    "vulnerability",
    "vulnerabilities",
    "security",
    "issue",
    "issues",
    "unknown",
    "unidentified",
    "unspecified",
    "multiple",
    "several",
    "new",
    "possible",
    "current",
    "remote",
    "code",
    "execution",
    "prompt",
    "indirect",
    "injection",
    "attack",
    "attacks",
    "other",
    "any",
    "some",
    "related",
    "critical",
    "high",
    "risk",
    "risks",
}


def substantive_vulnerability(identity: str, title: str) -> bool:
    if VULNERABILITY_ID.search(identity):
        return True
    identity_words = set(re.findall(r"[a-z]+", identity.casefold()))
    if identity_words and identity_words <= _GENERIC_VULNERABILITY_WORDS:
        return False
    words = set(re.findall(r"[a-z]+", title.casefold()))
    if VULNERABILITY_ID.search(title):
        return True
    return (
        len(title.strip()) >= 20
        and bool(words - _GENERIC_VULNERABILITY_WORDS)
        and bool(
            SECURITY.search(title)
            or re.search(
                r"overflow|bypass|execution|leak|escalation|injection|use.after.free|denial.of.service",
                title,
                re.I,
            )
        )
    )


def is_landing_document(source_urls: list[str]) -> bool:
    """Root and recognizable directory URLs do not establish an article update."""
    landing = []
    for url in source_urls:
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        query = parse_qs(parsed.query)
        if any(query.get(key) for key in ("p", "article", "article_id", "story", "id")):
            landing.append(False)
            continue
        parts = [part.casefold() for part in parsed.path.strip("/").split("/") if part]
        if parts and re.fullmatch(r"(?:en|zh|ja|de|fr|es|ko|pt)(?:-[a-z]{2})?", parts[0]):
            parts = parts[1:]
        landing.append(
            not parts
            or (bool(parts) and parts[-1] == "dashboard")
            or (
                len(parts) == 1
                and parts[0]
                in {
                    "index",
                    "index.html",
                    "index.htm",
                    "home",
                    "dashboard",
                    "security",
                    "blog",
                    "news",
                    "research",
                    "insights",
                    "resources",
                    "articles",
                    "advisories",
                }
            )
            or (bool(parts) and parts[0] in {"category", "categories", "tag", "tags"})
        )
    return bool(landing) and all(landing)


def activity_kind(
    object_type: str,
    text: str,
    evidenced_relations: list[str],
    *,
    source_urls: list[str] | None = None,
    identity: str = "",
    title: str = "",
) -> str | None:
    if object_type not in ACTIVITY_TYPES:
        return None
    if object_type == "Vulnerability" and not substantive_vulnerability(identity, title):
        return None
    if object_type == "Document" and is_landing_document(source_urls or []):
        return None
    security = bool(SECURITY.search(text))
    if object_type in {"PullRequest", "Commit", "Issue"}:
        return (
            "security"
            if security and SECURITY_RELATIONS.intersection(evidenced_relations)
            else None
        )
    if object_type in {"Vulnerability", "SecurityIncident", "Incident", "ExploitArtifact"}:
        return "security"
    if security:
        return "security"
    if object_type in {"Release", "SoftwareVersion"}:
        return (
            "release"
            if re.search(r"breaking change|major release|重大|不兼容", text, re.I)
            else None
        )
    if object_type == "ResearchWork" and text.strip():
        return "research"
    if object_type in {"Document", "NormativeDocument"} and re.search(
        r"breaking change|major release|重大|不兼容", text, re.I
    ):
        return "article"
    return None


def topic_matches(text: str, keywords: list[str]) -> list[str]:
    return [
        word
        for word in keywords
        if re.search(
            r"(?<!\w)" + re.escape(word) + r"(?!\w)" if word.isascii() else re.escape(word),
            text,
            re.I,
        )
    ]


def activity_identity(object_id: str, title: str, summary: str, material_change: str = "") -> str:
    # Knowledge revision, observation IDs and collection time are intentionally absent.
    content = "\n".join(
        (
            object_id if not summary.strip() else "content",
            " ".join(title.split()),
            " ".join(summary.split()),
            material_change,
        )
    )
    return "activity-" + hashlib.sha256(content.encode()).hexdigest()[:40]


def rank_key(
    mode: str, kind: str, matched: bool, score: int, at: datetime, activity_id: str
) -> tuple[int, int, int, float, str]:
    timestamp = at.replace(tzinfo=UTC).timestamp() if at.tzinfo is None else at.timestamp()
    if mode == "following":
        return (0, 0, 0, -timestamp, activity_id)
    return (0 if kind == "security" else 1, -int(matched), -score, -timestamp, activity_id)
