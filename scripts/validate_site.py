from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_FILES = {
    "index.html",
    "requirements.html",
    "tech-design.html",
    "lifecycle.html",
    "assets/site.css",
    "assets/site.js",
    "assets/lifecycle.js",
    "assets/lang.js",
    "diagrams/requirements.zh.html",
    "diagrams/requirements.en.html",
    "diagrams/tech-design.zh.html",
    "diagrams/tech-design.en.html",
    "specs/requirements.workflow.json",
    "specs/requirements.en.workflow.json",
    "specs/tech-design.architecture.json",
    "specs/tech-design.en.architecture.json",
}


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        for key in ("href", "src"):
            value = attr_map.get(key)
            if value:
                self.targets.append((key, value))


def _local_target(base: Path, value: str) -> Path | None:
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or value.startswith("#") or value.startswith("mailto:"):
        return None
    path = parsed.path
    if not path:
        return None
    return (base / path).resolve()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _workflow_signature(data: dict[str, object]) -> tuple[set[str], set[tuple[str, str]]]:
    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("workflow spec requires nodes and edges arrays")
    node_ids = {
        str(node["id"])
        for node in nodes
        if isinstance(node, dict) and isinstance(node.get("id"), str)
    }
    edge_pairs = {
        (str(edge["from"]), str(edge["to"]))
        for edge in edges
        if isinstance(edge, dict)
        and isinstance(edge.get("from"), str)
        and isinstance(edge.get("to"), str)
    }
    return node_ids, edge_pairs


def _architecture_signature(data: dict[str, object]) -> tuple[set[str], set[tuple[str, str]]]:
    components = data.get("components")
    connections = data.get("connections")
    if not isinstance(components, list) or not isinstance(connections, list):
        raise ValueError("architecture spec requires components and connections arrays")
    component_ids = {
        str(component["id"])
        for component in components
        if isinstance(component, dict) and isinstance(component.get("id"), str)
    }
    connection_pairs = {
        (str(connection["from"]), str(connection["to"]))
        for connection in connections
        if isinstance(connection, dict)
        and isinstance(connection.get("from"), str)
        and isinstance(connection.get("to"), str)
    }
    return component_ids, connection_pairs


def validate(site: Path) -> list[str]:
    errors: list[str] = []
    for relative in sorted(REQUIRED_FILES):
        if not (site / relative).is_file():
            errors.append(f"missing required site file: {relative}")

    diagrams = site / "diagrams"
    if diagrams.exists():
        for path in diagrams.iterdir():
            if path.suffix.lower() == ".png" or ".visual-check." in path.name:
                errors.append(
                    f"visual-check evidence must not be committed: {path.relative_to(site)}"
                )

    for html_path in sorted(site.rglob("*.html")):
        collector = LinkCollector()
        try:
            collector.feed(html_path.read_text(encoding="utf-8"))
        except UnicodeDecodeError as exc:
            errors.append(f"cannot decode HTML as UTF-8: {html_path.relative_to(site)}: {exc}")
            continue
        for attr, target in collector.targets:
            local = _local_target(html_path.parent, target)
            if local is None:
                continue
            if not local.exists():
                errors.append(f"broken local {attr} in {html_path.relative_to(site)}: {target}")

    try:
        workflow_zh = _load_json(site / "specs/requirements.workflow.json")
        workflow_en = _load_json(site / "specs/requirements.en.workflow.json")
        if (
            workflow_zh.get("diagram_type") != "workflow"
            or workflow_en.get("diagram_type") != "workflow"
        ):
            errors.append("requirements specs must use diagram_type=workflow")
        if _workflow_signature(workflow_zh) != _workflow_signature(workflow_en):
            errors.append("requirements zh/en specs must share the same node and edge topology")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid requirements spec: {exc}")

    try:
        architecture_zh = _load_json(site / "specs/tech-design.architecture.json")
        architecture_en = _load_json(site / "specs/tech-design.en.architecture.json")
        if (
            architecture_zh.get("diagram_type") != "architecture"
            or architecture_en.get("diagram_type") != "architecture"
        ):
            errors.append("technical-design specs must use diagram_type=architecture")
        if _architecture_signature(architecture_zh) != _architecture_signature(architecture_en):
            errors.append("technical-design zh/en specs must share the same component topology")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid technical-design spec: {exc}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the SecFusionAgent static documentation site"
    )
    parser.add_argument("--site", type=Path, required=True)
    args = parser.parse_args()
    site = args.site.resolve()
    errors = validate(site)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"site validation passed: {site}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
