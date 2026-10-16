"""Search facets for public reading; multi-label lexical matches, never canonical facts."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class LibrarySubject:
    key: str
    label: str
    label_en: str
    terms: tuple[str, ...]


LIBRARY_SUBJECTS = (
    LibrarySubject(
        "prompt-injection",
        "提示注入",
        "Prompt injection",
        ("prompt injection", "indirect injection", "提示注入", "间接注入"),
    ),
    LibrarySubject(
        "jailbreak",
        "越狱与护栏",
        "Jailbreaks & guardrails",
        ("jailbreak", "guardrail", "越狱", "护栏", "alignment bypass"),
    ),
    LibrarySubject(
        "runtime-containment",
        "运行隔离与工具权限",
        "Runtime containment & tools",
        (
            "sandbox",
            "containment",
            "tool permission",
            "tool use",
            "tool-use",
            "tool execution",
            "沙箱",
            "隔离",
            "工具权限",
            "工具调用",
        ),
    ),
    LibrarySubject(
        "agent-memory",
        "Agent 记忆与上下文",
        "Agent memory & context",
        (
            "agent memory",
            "memory poisoning",
            "context poisoning",
            "context window",
            "记忆投毒",
            "上下文投毒",
            "上下文窗口",
        ),
    ),
    LibrarySubject(
        "rag-retrieval",
        "RAG 与检索安全",
        "RAG & retrieval security",
        ("retrieval augmented", "retrieval-augmented", "rag", "检索增强", "检索投毒"),
    ),
    LibrarySubject(
        "model-evaluation",
        "模型与 Agent 评测",
        "Model & agent evaluation",
        ("benchmark", "evaluation", "red teaming", "red-teaming", "评测", "基准测试", "红队"),
    ),
    LibrarySubject(
        "identity-access",
        "身份、凭证与访问控制",
        "Identity & access control",
        (
            "authentication",
            "authorization",
            "credential",
            "oauth",
            "identity",
            "身份",
            "凭证",
            "认证",
            "访问控制",
            "授权",
        ),
    ),
    LibrarySubject(
        "supply-chain",
        "软件与模型供应链",
        "Software & model supply chain",
        (
            "supply chain",
            "supply-chain",
            "dependency",
            "dependencies",
            "package registry",
            "model hub",
            "供应链",
            "依赖",
            "模型仓库",
            "软件包",
        ),
    ),
    LibrarySubject(
        "training-poisoning",
        "训练数据与后门",
        "Training data & backdoors",
        (
            "data poisoning",
            "training data",
            "backdoor",
            "fine-tuning",
            "finetuning",
            "数据投毒",
            "训练数据",
            "后门",
            "微调",
        ),
    ),
    LibrarySubject(
        "privacy-leakage",
        "隐私与数据泄露",
        "Privacy & data leakage",
        (
            "privacy",
            "data leak",
            "data breach",
            "exfiltration",
            "model inversion",
            "隐私",
            "数据泄露",
            "数据外传",
            "模型反演",
        ),
    ),
    LibrarySubject(
        "inference-infrastructure",
        "推理服务与基础设施",
        "Inference & infrastructure",
        (
            "inference",
            "gpu",
            "container",
            "kubernetes",
            "vllm",
            "推理服务",
            "推理框架",
            "容器",
            "基础设施",
        ),
    ),
    LibrarySubject(
        "vulnerability-exploit",
        "漏洞、利用与修复",
        "Vulnerabilities & remediation",
        (
            "vulnerability",
            "vulnerabilities",
            "exploit",
            "cve-",
            "remote code execution",
            "漏洞",
            "利用链",
            "修复",
            "补丁",
        ),
    ),
    LibrarySubject(
        "ai-governance",
        "AI 治理与合规",
        "AI governance & compliance",
        (
            "governance",
            "compliance",
            "regulation",
            "risk management",
            "ai act",
            "治理",
            "合规",
            "监管",
            "风险管理",
            "标准",
            "规范",
        ),
    ),
    LibrarySubject(
        "incident-response",
        "攻击事件与响应",
        "Incidents & response",
        (
            "incident",
            "ransomware",
            "breach",
            "forensic",
            "threat actor",
            "事件响应",
            "攻击事件",
            "勒索",
            "取证",
            "威胁组织",
        ),
    ),
    LibrarySubject(
        "agent-safety",
        "Agent 行为与能力边界",
        "Agent behavior & safety",
        ("agent", "agentic", "autonomous", "智能体", "自主行为", "能力边界"),
    ),
)
SUBJECT_BY_KEY = {subject.key: subject for subject in LIBRARY_SUBJECTS}
CATEGORY_LABELS = {
    "academic": ("学术研究", "Research"),
    "development": ("开发资料", "Development"),
    "vulnerability": ("漏洞资料", "Vulnerabilities"),
    "vendor": ("厂商材料", "Vendors"),
    "independent": ("独立研究", "Independent research"),
    "normative": ("标准与法规", "Standards & policy"),
    "assets": ("资产情报", "Assets"),
    "incidents": ("事件材料", "Incident material"),
}


def material_subjects(title: str, excerpt: str) -> list[str]:
    content = f"{title}\n{excerpt}".casefold()
    return [
        subject.key
        for subject in LIBRARY_SUBJECTS
        if any(
            (
                re.search(
                    r"\b" + re.escape(term) + (r"s?\b" if term[-1].isalnum() else ""), content
                )
                is not None
            )
            if term.isascii()
            else term in content
            for term in subject.terms
        )
    ] or ["other"]
