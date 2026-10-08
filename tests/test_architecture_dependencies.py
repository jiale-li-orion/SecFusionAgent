import ast
from pathlib import Path

PACKAGE_ROOT = Path("packages")

ALLOWED_CROSS_PACKAGE_PREFIXES = {
    "investigation": (
        "packages.intelligence.retrieval",
        # A delegation names M3's canonical dimension contract, never its storage or writers.
        "packages.intelligence.knowledge.vocabulary",
    ),
}

ALLOWED_PACKAGE_DEPENDENCIES = {
    "shared": {"shared"},
    "sources": {"shared", "sources"},
    "intelligence": {"shared", "sources", "intelligence"},
    "investigation": {"shared", "investigation", "task_runtime"},
    "monitoring": {"shared", "sources", "intelligence", "monitoring"},
    "enrichment": {
        "shared",
        "sources",
        "intelligence",
        "monitoring",
        "enrichment",
        "task_runtime",
    },
    "evaluation": {
        "shared",
        "sources",
        "intelligence",
        "investigation",
        "task_runtime",
        "runtime",
        "evaluation",
    },
    "task_runtime": {"shared", "task_runtime"},
    "runtime": {"shared", "task_runtime", "runtime"},
    "reasoning": {"shared", "investigation", "reasoning"},
}


def test_package_dependency_direction() -> None:
    violations: list[str] = []
    for owner, allowed in ALLOWED_PACKAGE_DEPENDENCIES.items():
        root = PACKAGE_ROOT / owner
        for path in root.rglob("*.py"):
            if "tests" in path.parts or path.name.startswith("test_"):
                continue
            for imported in _internal_imports(path):
                if imported.startswith("apps.") or imported == "apps":
                    violations.append(f"{path}: package code imports deployable app {imported}")
                    continue
                if not imported.startswith("packages."):
                    continue
                parts = imported.split(".")
                if len(parts) < 2:
                    continue
                target = parts[1]
                allowed_prefixes = ALLOWED_CROSS_PACKAGE_PREFIXES.get(owner, ())
                if target not in allowed and not imported.startswith(allowed_prefixes):
                    violations.append(
                        f"{path}: {owner} -> {target} is outside allowed dependency set "
                        f"{sorted(allowed)} and public cross-package prefixes "
                        f"{list(allowed_prefixes)}"
                    )
    assert violations == [], "\n".join(violations)


def test_investigation_skills_are_not_owned_by_task_runtime() -> None:
    misplaced = sorted((PACKAGE_ROOT / "task_runtime" / "skills").rglob("*.py"))
    assert misplaced == [], (
        "investigation Skill runtime belongs under packages/investigation/skills: "
        + ", ".join(str(path) for path in misplaced)
    )


def _internal_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports
