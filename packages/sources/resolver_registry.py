from __future__ import annotations

from packages.sources.resolution import (
    CuratedPublicationResolver,
    DynamicSourceResolver,
    ExplicitURLResolver,
    GitHubIncidentFollowupResolver,
    PublicationResolver,
)


def create_dynamic_source_resolvers() -> dict[str, DynamicSourceResolver]:
    resolvers: list[DynamicSourceResolver] = [
        PublicationResolver(),
        CuratedPublicationResolver(),
        GitHubIncidentFollowupResolver(),
        ExplicitURLResolver(
            owner="vendor_primary_source_resolver",
            source_role_hint="primary",
            source_class_hint="vendor_security_material",
        ),
        ExplicitURLResolver(
            owner="public_disclosure_resolver",
            source_role_hint="forensic",
            source_class_hint="independent_security_research",
        ),
        ExplicitURLResolver(
            owner="incident_primary_source_resolver",
            source_role_hint="primary",
            source_class_hint="incident_primary_evidence",
        ),
    ]
    return {resolver.owner: resolver for resolver in resolvers}


def get_dynamic_source_resolver(owner: str) -> DynamicSourceResolver:
    resolver = create_dynamic_source_resolvers().get(owner)
    if resolver is None:
        raise KeyError(f"unknown dynamic source resolver: {owner}")
    return resolver
