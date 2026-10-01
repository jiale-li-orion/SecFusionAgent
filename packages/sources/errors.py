class SourceError(RuntimeError):
    """Base class for provider-boundary failures."""


class SourceRateLimited(SourceError):
    def __init__(self, message: str, *, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class SourceAuthFailed(SourceError):
    pass


class SourceAccessBlocked(SourceError):
    """A public/provider endpoint rejected automated access (for example HTTP 403)."""

    pass


class SourceSchemaChanged(SourceError):
    pass


class SourceFetchFailed(SourceError):
    pass


class SourceConfigurationError(SourceError):
    """Configured source cannot be executed by the active runtime composition."""
