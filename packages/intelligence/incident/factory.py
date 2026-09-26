from __future__ import annotations

from packages.intelligence.incident.contracts import (
    GenericNewsSignalExtractor,
    IncidentSignalExtractor,
)


def create_incident_signal_extractors() -> dict[str, IncidentSignalExtractor]:
    return {
        "rss_incident": GenericNewsSignalExtractor(),
        "html_incident": GenericNewsSignalExtractor(),
        "slowmist_hacked": GenericNewsSignalExtractor(),
        "x_user_signal": GenericNewsSignalExtractor(),
    }
