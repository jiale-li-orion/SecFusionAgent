from typing import Any, cast

from packages.monitoring.storage.models import SourceStateModel
from packages.sources.contracts import SourceState


def source_state_from_model(model: SourceStateModel) -> SourceState:
    return SourceState.model_validate(
        {
            "cursor": cast(dict[str, Any], model.cursor),
            "last_attempt_at": model.last_attempt_at,
            "last_success_at": model.last_success_at,
            "last_change_at": model.last_change_at,
            "next_due_at": model.next_due_at,
            "consecutive_failures": model.consecutive_failures,
            "backoff_until": model.backoff_until,
            "rate_limit_state": cast(dict[str, Any], model.rate_limit_state),
        }
    )
