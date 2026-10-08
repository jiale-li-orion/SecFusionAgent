from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    code = "application_error"
    retryable = False

    def __init__(
        self,
        detail: str,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.context = context or {}


class ResourceNotFoundError(ApplicationError):
    code = "resource_not_found"


class RevisionConflictError(ApplicationError):
    code = "revision_conflict"


class LifecycleConflictError(ApplicationError):
    code = "lifecycle_conflict"


class PermissionDeniedError(ApplicationError):
    code = "permission_denied"


class DependencyUnavailableError(ApplicationError):
    code = "dependency_unavailable"
    retryable = True


class DeadlineExceededError(ApplicationError):
    code = "deadline_exceeded"
    retryable = True
