"""Deterministic editorial topic selection, not event or fact confirmation."""

import re
from dataclasses import dataclass
from datetime import datetime

THEMES = (
    ("Agent 安全与权限边界", r"\bagent(?:ic|s)?\b|prompt.injection|智能体|提示.*注入|mcp\b"),
    ("模型能力与安全评测", r"\bllm\b|\bmodel\b|模型|benchmark|评测|jailbreak|越狱"),
    ("云端攻防与身份安全", r"cloud|identity|credential|token.theft|云|身份|凭证"),
    ("AI 治理与基础设施", r"\bai\b|artificial.intelligence|算力|人工智能|数据中心"),
)


@dataclass(frozen=True)
class EditorialCandidate:
    document_id: str
    fingerprint: str
    title: str
    origin: str
    published_at: datetime


def choose_materials(
    candidates: list[EditorialCandidate], *, limit: int
) -> tuple[str, list[EditorialCandidate]]:
    groups: dict[str, list[EditorialCandidate]] = {}
    seen: set[str] = set()
    for item in sorted(candidates, key=lambda c: (c.published_at, c.document_id), reverse=True):
        if item.fingerprint in seen:
            continue
        seen.add(item.fingerprint)
        for topic, pattern in THEMES:
            if re.search(pattern, item.title, re.IGNORECASE):
                groups.setdefault(topic, []).append(item)
                break
    if not groups:
        return "", []
    # Freshness first, then source diversity inside the same theme. Never synthesize
    # unrelated topics merely to fill a fixed number of articles.
    topic = max(groups, key=lambda key: groups[key][0].published_at)
    pool = groups[topic]
    selected: list[EditorialCandidate] = []
    origins: set[str] = set()
    while pool and len(selected) < limit:
        index = next((i for i, item in enumerate(pool) if item.origin not in origins), 0)
        item = pool.pop(index)
        selected.append(item)
        origins.add(item.origin)
    return topic, selected
