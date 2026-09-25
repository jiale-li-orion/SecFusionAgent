import ast
from pathlib import Path

PACKAGE_ROOT = Path("packages")

ALLOWED_PACKAGE_DEPENDENCIES = {
    "shared": {"shared"},
    "sources": {"shared", "sources"},
    "intelligence": {"shared", "sources", "intelligence"},
    "investigation": {"shared", "investigation"},
    "monitoring": {"shared", "sources", "intelligence", "monitoring"},
    "enrichment": {"shared", "sources", "intelligence", "monitoring", "enrichment"},
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
                if target not in allowed:
                    violations.append(
                        f"{path}: {owner} -> {target} is outside allowed dependency set "
                        f"{sorted(allowed)}"
                    )
    assert violations == [], "\n".join(violations)


def _internal_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports
