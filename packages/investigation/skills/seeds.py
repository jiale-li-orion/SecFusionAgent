from __future__ import annotations

from packages.investigation.skills.contracts import (
    SkillManifest,
    SkillProcedure,
    SkillProvenance,
    SkillSourceType,
    SkillStatus,
    SkillStepFragment,
    SkillVersion,
)


def seeded_skills() -> list[SkillVersion]:
    return [
        _verify_fix_boundary(),
        _resolve_source_conflict(),
        _trace_incident_evidence(),
        _assess_affected_deployment(),
        _assess_applicability(),
    ]


def _verify_fix_boundary() -> SkillVersion:
    return _skill(
        skill_id="investigation.verify_fix_boundary",
        task_patterns=["verify_version_fix"],
        evidence_need_patterns=["*fix*", "*release*contain*"],
        object_types=["Vulnerability", "Package", "Release", "Commit"],
        required_capability_classes=["evidence.read", "graph.read"],
        expected_outcomes=["fix boundary verified", "conflict explicit", "unknown explicit"],
        steps=[
            (
                "inspect_fix_candidate",
                (
                    "Inspect the current fix candidate and its evidence-backed relations "
                    "before following repository history."
                ),
                ["evidence.read"],
                "candidate fix identity is evidence-backed",
                "candidate fix identity is missing or conflicting",
            ),
            (
                "trace_release_containment",
                (
                    "Trace whether a release actually contains the fix commit using "
                    "deterministic ancestry or release evidence."
                ),
                ["graph.read"],
                "release containment is supported by accepted evidence",
                "only temporal or textual association is available",
            ),
        ],
        evidence_expectations=[
            "fix commit identity resolves to EvidenceRef",
            "release containment uses ancestry/compare/changelog evidence",
        ],
        failure_guards=[
            "PR merged_at does not prove release containment",
            "absence of a fixed release does not prove not_affected",
        ],
        fallbacks=["seek primary advisory", "delegate enrichment for missing fix dimension"],
        stop_conditions=[
            "required EvidenceNeed is resolved/conflict/unknown",
            "no eligible evidence path",
        ],
    )


def _resolve_source_conflict() -> SkillVersion:
    return _skill(
        skill_id="investigation.resolve_source_conflict",
        task_patterns=["resolve_conflict"],
        evidence_need_patterns=["*conflict*", "*corroborat*"],
        object_types=[],
        required_capability_classes=["evidence.read"],
        expected_outcomes=["conflict resolved", "conflict remains explicit"],
        steps=[
            (
                "contrast_sources",
                (
                    "Separate conflicting claims by source family, revision and valid time "
                    "before comparing conclusions."
                ),
                ["evidence.read"],
                "conflicting evidence is version/time aligned",
                "source identity or revision cannot be resolved",
            ),
            (
                "seek_independent_authority",
                (
                    "Seek independent primary or authority evidence that directly "
                    "addresses the disputed proposition."
                ),
                ["evidence.read"],
                "evidence contract is satisfied",
                "only reposts or same-upstream evidence are available",
            ),
        ],
        evidence_expectations=[
            "source independence preserved",
            "authority role kept separate from retrieval score",
        ],
        failure_guards=["same-upstream reposts do not count as independent corroboration"],
        fallbacks=["keep conflict open", "wait for primary source update"],
        stop_conditions=["conflict resolved with evidence", "remaining paths blocked"],
    )


def _trace_incident_evidence() -> SkillVersion:
    return _skill(
        skill_id="investigation.trace_incident_evidence",
        task_patterns=["investigate_incident", "watch_incident"],
        evidence_need_patterns=[],
        object_types=["SecurityIncident"],
        required_capability_classes=["evidence.read"],
        expected_outcomes=["timeline evidence traced", "material update isolated"],
        steps=[
            (
                "trace_timeline",
                (
                    "Trace incident claims to primary, forensic and authority evidence "
                    "while preserving event time."
                ),
                ["evidence.read"],
                "timeline assertions have evidence references",
                "signal-only claims remain unconfirmed",
            ),
        ],
        evidence_expectations=["timeline events retain observed/valid time and source role"],
        failure_guards=["breaking-news repetition does not increase corroboration strength"],
        fallbacks=["wait for material update", "seek forensic source"],
        stop_conditions=["task completion predicate met", "watch episode returns to waiting"],
    )


def _assess_affected_deployment() -> SkillVersion:
    return _skill(
        skill_id="investigation.assess_affected_deployment",
        task_patterns=["observe_live_asset", "verify_version_fix"],
        evidence_need_patterns=["*asset*", "*affected*", "*deployment*"],
        object_types=["InternetAsset", "Product", "SoftwareVersion", "Vulnerability"],
        required_capability_classes=["evidence.read"],
        expected_outcomes=["affectedness supported", "identity/version gap explicit"],
        steps=[
            (
                "bind_asset_identity",
                (
                    "Verify asset, product and version identity before joining "
                    "vulnerability affectedness."
                ),
                ["evidence.read"],
                "asset/product/version mapping is explicit",
                "identity or version comparability is ambiguous",
            ),
        ],
        evidence_expectations=["observation time and fingerprint mapping version retained"],
        failure_guards=[
            "shared CDN edge observation does not prove asset ownership",
            "banner similarity does not prove affectedness",
        ],
        fallbacks=["observe a more authoritative endpoint", "return identity/version unknown"],
        stop_conditions=[
            "affectedness decision is evidence-backed",
            "required observation unavailable",
        ],
    )


def _assess_applicability() -> SkillVersion:
    return _skill(
        skill_id="investigation.assess_applicability",
        task_patterns=["assess_normative_applicability"],
        evidence_need_patterns=["*applicab*", "*control*"],
        object_types=["Requirement", "Control"],
        required_capability_classes=["evidence.read"],
        expected_outcomes=["applicable", "not_applicable", "uncertain with EvidenceNeed"],
        steps=[
            (
                "evaluate_conditions",
                (
                    "Evaluate structured applicability conditions against evidence-backed "
                    "system facts and rule version."
                ),
                ["evidence.read"],
                "all applicability conditions have evidence-backed values",
                "one or more applicability conditions remain unresolved",
            ),
        ],
        evidence_expectations=["system facts and normative rule revision are both retained"],
        failure_guards=["normative source text is not itself an execution permission"],
        fallbacks=["open EvidenceNeed for unresolved applicability"],
        stop_conditions=["applicability state explicit", "required system fact unavailable"],
    )


def _skill(
    *,
    skill_id: str,
    task_patterns: list[str],
    evidence_need_patterns: list[str],
    object_types: list[str],
    required_capability_classes: list[str],
    expected_outcomes: list[str],
    steps: list[tuple[str, str, list[str], str, str]],
    evidence_expectations: list[str],
    failure_guards: list[str],
    fallbacks: list[str],
    stop_conditions: list[str],
) -> SkillVersion:
    version = 1
    procedure_ref = f"skill-procedure:{skill_id}@{version}"
    provenance_ref = f"skill-provenance:{skill_id}@{version}"
    return SkillVersion(
        manifest=SkillManifest(
            skill_id=skill_id,
            version=version,
            status=SkillStatus.CANDIDATE,
            source_type=SkillSourceType.SEEDED,
            task_patterns=task_patterns,
            evidence_need_patterns=evidence_need_patterns,
            applicable_object_types=object_types,
            required_inputs=["task_contract", "investigation_state"],
            required_capability_classes=required_capability_classes,
            expected_outcomes=expected_outcomes,
            risk_hint="bounded investigation",
            cost_hint="prefer local evidence before external observation",
            procedure_ref=procedure_ref,
            provenance_ref=provenance_ref,
        ),
        procedure=SkillProcedure(
            skill_id=skill_id,
            version=version,
            steps=[
                SkillStepFragment(
                    skill_id=skill_id,
                    version=version,
                    step_id=step_id,
                    semantic_instruction=instruction,
                    required_capability_classes=capabilities,
                    success_predicate=success,
                    failure_predicate=failure,
                    fallback_refs=fallbacks,
                )
                for step_id, instruction, capabilities, success, failure in steps
            ],
            evidence_expectations=evidence_expectations,
            failure_guards=failure_guards,
            fallbacks=fallbacks,
            stop_conditions=stop_conditions,
        ),
        provenance=SkillProvenance(
            skill_id=skill_id,
            version=version,
            origin="Technical-Design-2 seeded investigation rule",
            promotion_history=["seeded_as_candidate_pending_m7_replay"],
        ),
    )
