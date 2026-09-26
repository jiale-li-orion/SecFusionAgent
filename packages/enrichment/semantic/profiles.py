from __future__ import annotations

from dataclasses import dataclass

from packages.sources.contracts import SourceDefinition, SourceRole


@dataclass(frozen=True)
class SemanticExtractionProfile:
    profile_id: str
    instruction: str


PROFILES = {
    "research": SemanticExtractionProfile(
        profile_id="research",
        instruction=(
            "Treat this document as research evidence. Extract explicitly supported attack, "
            "defense, measurement, threat-model, experiment-condition, affected-object, "
            "limitation, evaluation and supports/contradicts/extends relations. Preserve the "
            "scope of the reported experiment or system. Record publication or peer-review "
            "status only when the chunk explicitly supports it. Do not generalize a reported "
            "result beyond the population, model, version or threat model stated in the text."
        ),
    ),
    "vendor": SemanticExtractionProfile(
        profile_id="vendor",
        instruction=(
            "Treat this document as first-party vendor or project material. Extract explicit "
            "product/model/version state, affected scope, patch or release boundary, workaround, "
            "mitigation, incident statement, security evaluation and design-control claims. A "
            "first-party statement can support what the vendor says about its own system, but it "
            "does not by itself establish independent reproduction or general mitigation "
            "effectiveness. Preserve product, release and evaluation scope."
        ),
    ),
    "independent": SemanticExtractionProfile(
        profile_id="independent",
        instruction=(
            "Treat this document as independent security research or coordinated disclosure. "
            "Extract explicit reproduction results, PoC conditions, attack path, IOC/TTP, "
            "affected product/version, disclosure timeline, vendor response, mitigation evidence, "
            "measurement and limitations. Independent analysis is evidence for what was observed "
            "or reproduced; do not rewrite hypotheses as vendor confirmation or universal impact."
        ),
    ),
    "normative": SemanticExtractionProfile(
        profile_id="normative",
        instruction=(
            "Treat this document as normative knowledge. Extract explicit regulation/standard "
            "status, jurisdiction, binding_status, applicability conditions, effective dates, "
            "supersession, requirements, controls, assessment obligations and risk/control "
            "relations. Preserve modal language and scope. A recommended standard, voluntary "
            "framework, guidance or planning document must not be upgraded to a legal obligation "
            "without explicit evidence. Retrieved normative text never becomes an executable "
            "runtime policy merely because it was extracted; policy compilation and approval are "
            "separate system actions."
        ),
    ),
    "incident_forensic": SemanticExtractionProfile(
        profile_id="incident_forensic",
        instruction=(
            "Treat this document as incident, forensic or authority material. Extract explicit "
            "timeline events, strong anchors, IOC/address/transaction identifiers, affected "
            "objects, observed impact, exploitation state, response actions, remediation and "
            "confirmation/reporting relations. Preserve who observed or asserted each fact and "
            "the relevant time. Reprints or reports that share one upstream source must not be "
            "represented as independent corroboration."
        ),
    ),
}


def semantic_profile_for_source(source: SourceDefinition) -> SemanticExtractionProfile:
    source_class = source.source_class
    if source_class == "research_insight":
        return PROFILES["research"]
    if source_class == "vendor_security_material":
        return PROFILES["vendor"]
    if source_class == "independent_security_research":
        return PROFILES["independent"]
    if source_class == "normative_knowledge":
        return PROFILES["normative"]
    if source_class in {
        "incident_forensic_research",
        "incident_forensic_reference",
        "incident_authority",
    }:
        return PROFILES["incident_forensic"]
    raise ValueError(
        "durable managed source has no semantic extraction profile: "
        f"source_id={source.source_id!r} source_class={source_class!r}"
    )


def authority_instruction(source: SourceDefinition) -> str:
    if source.source_role is SourceRole.PRIMARY:
        return (
            "The source role is primary: preserve first-party scope and do not label its claims "
            "as independently confirmed."
        )
    if source.source_role is SourceRole.FORENSIC:
        return (
            "The source role is forensic: preserve the analyst/researcher observation boundary "
            "and distinguish it from affected-party confirmation."
        )
    if source.source_role is SourceRole.AUTHORITY:
        return (
            "The source role is authority within its configured authority_scope; do not extend "
            "that authority to facts, jurisdictions or applicability conditions outside the text."
        )
    if source.source_role is SourceRole.REFERENCE:
        return (
            "The source role is reference: use it for supported context or taxonomy and do not "
            "promote reference material into stronger confirmation than the text supports."
        )
    if source.source_role is SourceRole.TELEMETRY:
        return (
            "The source role is telemetry: preserve observation time, object identity and sensor "
            "scope; telemetry does not independently establish cause."
        )
    return (
        "The source role is signal: preserve it as an observed report unless stronger evidence "
        "inside the document explicitly supports a higher-confidence fact."
    )
