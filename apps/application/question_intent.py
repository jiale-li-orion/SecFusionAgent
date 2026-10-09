"""Bounded Product question interpretation before task admission.

The public chat sends a question, not an execution profile. Explicit API
profiles remain available for callers that deliberately request one.
"""

from __future__ import annotations

import re

from packages.task_runtime.contracts.models import TaskKind

_CVE = re.compile(r"\bCVE-\d{4}-\d{4,}\b", re.IGNORECASE)
_TECHNICAL_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9._:/+-]{2,}|\d+(?:\.\d+){1,}")
_QUESTION_WORDS = frozenset({
    "about", "after", "against", "and", "are", "could", "describe", "does",
    "event", "evidence", "explain", "for", "from", "happened", "have", "how",
    "incident", "investigation", "know", "latest", "please", "recent",
    "research", "security", "show", "support", "tell", "that", "the", "these",
    "this", "was", "were", "what", "when", "where", "which", "who", "with",
    "would", "you",
})


def infer_question_route(
    question: str, *, cve_id: str | None, object_id: str | None,
) -> tuple[TaskKind, str | None]:
    """Bind a stable ID when present; search open language before deciding to investigate.

    RETRIEVE deliberately remains the initial route for natural language. M6
    can request a durable continuation after it has inspected current evidence.
    """
    mentioned = _CVE.findall(question)
    resolved_cve = cve_id or (
        mentioned[0].upper()
        if len(set(map(str.upper, mentioned))) == 1 and not object_id
        else None
    )
    if cve_id or object_id:
        return TaskKind.LOOKUP, resolved_cve
    return TaskKind.RETRIEVE, resolved_cve


def lexical_queries(question: str) -> list[str]:
    """Use the original phrase when compact, then safe exact terms for mixed prose.

    PostgreSQL simple FTS ANDs all terms from a sentence. Long Chinese prose
    mixed with a product/incident name can therefore hide an exact match.
    These bounded fallback terms preserve IDs and names without an unrecorded
    model rewrite. Every physical query gets its own retrieval invocation.
    """
    original = question.strip()
    if not original:
        return []
    result = [original]
    for identifier in _CVE.findall(original):
        if identifier.upper() not in result:
            result.append(identifier.upper())
    tokens = sorted(
        _TECHNICAL_TOKEN.findall(original),
        key=lambda item: (bool(re.search(r"[._:/+\d-]", item)), len(item)),
        reverse=True,
    )
    for token in tokens:
        cleaned = token.strip("./:+-")
        if cleaned.lower() in _QUESTION_WORDS or cleaned in result:
            continue
        if len(cleaned) >= 3:
            result.append(cleaned)
        if len(result) >= 5:
            break
    return result


def unbound_target_message(question: str, *, ambiguous: bool) -> str:
    chinese = any("\u4e00" <= character <= "\u9fff" for character in question)
    if chinese and ambiguous:
        return (
            "找到了多个可能相关的对象，现有证据无法确定你指的是哪一个。"  # noqa: RUF001
            "请补充事件名称、来源链接或 CVE 编号。"
        )
    if chinese:
        return (
            "当前证据不足以确认这个问题，也没有找到可继续调查的对象。"  # noqa: RUF001
            "请提供更具体的事件名称、来源链接或 CVE 编号。"
        )
    if ambiguous:
        return (
            "Several related objects were found, but the evidence does not identify "
            "which one to investigate. Please specify an event, source link, or CVE ID."
        )
    return (
        "The available evidence does not identify an investigation target for this "
        "question. Please provide a specific event name, source link, or CVE ID."
    )
