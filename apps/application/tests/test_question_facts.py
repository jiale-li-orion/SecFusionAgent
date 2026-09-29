from __future__ import annotations

import json

from apps.application.question_facts import (
    compact_claim_semantics,
    compact_relation_semantics,
    render_claim_fact,
    render_relation_fact,
)


def test_claim_fact_only_preserves_semantic_ep_ss_qualifiers() -> None:
    ordinary = render_claim_fact(
        "cve:CVE-2026-7273",
        "cvss_score",
        8.8,
        qualifier={"source_id": "nvd-cves-2", "vocabulary_revision": "enrichment-v1"},
    )
    assert ordinary == "cve:CVE-2026-7273 cvss_score = 8.8"

    first = render_claim_fact(
        "cve:CVE-2026-7273",
        "epss_probability",
        0.02501,
        qualifier={
            "source_id": "first-epss",
            "source_semantics": "first_epss",
            "score_date": "2026-09-27",
            "vocabulary_revision": "enrichment-v1",
        },
    )
    assert first == (
        'cve:CVE-2026-7273 epss_probability = 0.02501 '
        'semantics={"score_date":"2026-09-27","source_semantics":"first_epss"}'
    )
    assert compact_claim_semantics(
        "epss_percentile",
        {"source_id": "github-global-advisories"},
    ) == {"source_id": "github-global-advisories"}
    assert compact_claim_semantics(
        "status",
        {
            "source_id": "nvd-cves-2",
            "vocabulary_scope": "source_specific",
            "vocabulary_revision": "enrichment-v1",
        },
    ) == {"source_id": "nvd-cves-2"}


def test_nvd_applicability_fact_keeps_version_semantics_without_root_snapshot() -> None:
    qualifier: dict[str, object] = {
        "state": "affected",
        "source_semantics": "nvd_cpe",
        "platform": "cpe:2.3:o:zyxel:firmware:*:*:*:*:*:*:*:*",
        "version_range": {"versionEndExcluding": "2.90"},
        "source_id": "nvd-cves-2",
        "vocabulary_revision": "enrichment-v1",
        "configuration": {
            "root_index": 4,
            "root_operator": "AND",
            "root_negate": False,
            "node_path": [0],
            "node_operator": "OR",
            "node_negate": False,
            "match_criteria_id": "match-1",
            "match_index": 0,
            "root_snapshot": {"huge": ["payload"] * 100},
        },
    }
    semantics = compact_relation_semantics(
        qualifier,
        target_properties={"vendor": "Zyxel", "product": "GS1900"},
    )
    assert semantics["state"] == "affected"
    assert semantics["version_range"] == {"versionEndExcluding": "2.90"}
    assert semantics["configuration"] == {
        "root_index": 4,
        "root_operator": "AND",
        "root_negate": False,
        "node_path": [0],
        "node_operator": "OR",
        "node_negate": False,
        "match_criteria_id": "match-1",
        "match_index": 0,
    }
    assert "source_id" not in semantics
    assert "vocabulary_revision" not in semantics
    assert "root_snapshot" not in json.dumps(semantics)


def test_csaf_applicability_fact_keeps_status_component_platform_and_justification() -> None:
    proposition = render_relation_fact(
        "cve:CVE-2025-32463",
        "applicability-status",
        "product:csaf-sha256:example",
        qualifier={
            "state": "not_affected",
            "source_semantics": "csaf_vex",
            "csaf_status": "known_not_affected",
            "scope": {
                "kind": "csaf_product_status",
                "product_id": "red_hat_enterprise_linux_8:sudo",
            },
            "justification": ["vulnerable_code_not_present"],
            "product_context": {
                "full_product_id": "red_hat_enterprise_linux_8:sudo",
                "full_product_name": "sudo as a component of Red Hat Enterprise Linux 8",
                "relationship_category": "default_component_of",
                "component": {
                    "product_id": "sudo",
                    "name": "sudo",
                    "purl": "pkg:rpm/redhat/sudo",
                },
                "platform": {
                    "product_id": "red_hat_enterprise_linux_8",
                    "name": "Red Hat Enterprise Linux 8",
                    "cpe": "cpe:/o:redhat:enterprise_linux:8",
                },
            },
            "source_id": "redhat-csaf-vex",
        },
        target_properties={
            "identity_scheme": "csaf_product_id",
            "csaf_product_id": "red_hat_enterprise_linux_8:sudo",
        },
    )
    assert "not_affected" in proposition
    assert "known_not_affected" in proposition
    assert "vulnerable_code_not_present" in proposition
    assert "pkg:rpm/redhat/sudo" in proposition
    assert "Red Hat Enterprise Linux 8" in proposition
    assert "full_product_name" not in proposition
    assert "csaf_product_id" not in proposition
    assert "redhat-csaf-vex" not in proposition
