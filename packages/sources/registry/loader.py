from pathlib import Path

from packages.sources.contracts import SourceDefinition


def load_source_definitions(directory: Path) -> list[SourceDefinition]:
    definitions: list[SourceDefinition] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.json")):
        definition = SourceDefinition.model_validate_json(path.read_text(encoding="utf-8"))
        if definition.source_id in seen:
            raise ValueError(f"duplicate source_id: {definition.source_id}")
        seen.add(definition.source_id)
        definitions.append(definition)
    return definitions
