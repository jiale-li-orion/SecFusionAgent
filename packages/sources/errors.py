class SourceError(RuntimeError):
    """Base class for provider-boundary failures."""


class SourceRateLimited(SourceError):
    pass


class SourceAuthFailed(SourceError):
    pass


class SourceSchemaChanged(SourceError):
    pass


class SourceFetchFailed(SourceError):
    pass


class SourceConfigurationError(SourceError):
    """Configured source cannot be executed by the active runtime composition."""
