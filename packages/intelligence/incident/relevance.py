from __future__ import annotations

import re

from packages.intelligence.incident.contracts import SignalItem

_BROAD_NEWS_SOURCES = frozenset({"blockbeats-newsflash", "bleepingcomputer-news"})
_REPORTED_EVENT = re.compile(
    r"\b(?:hackers? (?:exploit|hijack|breach|attack)|hacked|breached|data breach|"
    r"malware (?:campaign|infects?|ships?|spreads?)|(?:phishing|ransomware|"
    r"cryptomining) attacks?|(?:ongoing|active) [\w-]+ attacks?|"
    r"credential theft|stolen funds|security incident)\b",
    re.IGNORECASE,
)
_CHINESE_REPORTED_EVENT = re.compile(
    r"(?:遭黑客|遭网络攻击|遭攻击|被黑客|被盗|被入侵|私钥泄露|信息泄露|"
    r"数据泄露|漏洞利用者|攻击者利用|钓鱼攻击|钓鱼事件|恶意授权|盗取资产|"
    r"安全事件|热钱包疑似私钥泄露)"
)


def is_presentable_incident_signal(signal: SignalItem) -> bool:
    """Select reported security events for the public candidate watch view.

    The Redis working set can contain general news. This screen does not promote
    a candidate or change its durable evidence status.
    """
    return is_presentable_incident_headline(signal.source_id, signal.title)


def is_presentable_incident_headline(source_id: str, title: str) -> bool:
    if source_id == "slowmist-hacked":
        return True
    return bool(_REPORTED_EVENT.search(title) or _CHINESE_REPORTED_EVENT.search(title))


def should_collect_incident_headline(source_id: str, title: str) -> bool:
    """Keep broad news feeds from filling Incident Watch with market headlines."""
    return source_id not in _BROAD_NEWS_SOURCES or is_presentable_incident_headline(
        source_id, title
    )
