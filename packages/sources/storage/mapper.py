from typing import Any, cast

from packages.sources.contracts import SourceDefinition
from packages.sources.storage.models import SourceModel


def source_definition_from_model(model: SourceModel) -> SourceDefinition:
    return SourceDefinition.model_validate(
        {
            "source_id": model.source_id,
            "adapter_type": model.adapter_type,
            "source_class": model.source_class,
            "authority_scope": model.authority_scope,
            "source_role": model.source_role,
            "source_family": model.source_family,
            "upstream_source": model.upstream_source,
            "access_mode": model.access_mode,
            "update_semantics": model.update_semantics,
            "discovery_method": cast(dict[str, Any], model.discovery_method),
            "time_semantics": cast(dict[str, Any], model.time_semantics),
            "identity_semantics": cast(dict[str, Any], model.identity_semantics),
            "auth_ref": model.auth_ref,
            "rate_limit_policy": cast(dict[str, Any], model.rate_limit_policy),
            "access_rights": cast(dict[str, Any], model.access_rights),
            "retention_mode": model.retention_mode,
            "schedule_policy": cast(dict[str, Any], model.schedule_policy),
            "schema_version": model.schema_version,
        }
    )
