import json
from pathlib import Path

from packages.enrichment.processors.cisa_kev import CISAKEVMapper
from packages.enrichment.processors.csaf_vex import RedHatCSAFVEXMapper
from packages.enrichment.processors.epss import FIRSTEPSSMapper
from packages.enrichment.processors.github_advisory import GitHubAdvisoryMapper
from packages.enrichment.processors.osv import OSVMapper
from packages.sources.contracts import AcquisitionTrigger, IngestEnvelope

FIXTURES = Path("tests/fixtures")


def _envelope(name: str, external_id: str) -> IngestEnvelope:
    payload = json.loads((FIXTURES / name).read_text())
    if isinstance(payload, list):
        payload = payload[0]
    elif name == "cisa_kev.json":
        payload = {
            "catalogVersion": payload["catalogVersion"],
            "dateReleased": payload["dateReleased"],
            "vulnerability": payload["vulnerabilities"][0],
        }
    elif name == "first_epss.json":
        payload = {
            "api_version": payload["version"],
            "record": payload["data"][0],
        }
    canonical_url = None
    if name == "redhat_csaf_vex.json":
        canonical_url = (
            "https://security.access.redhat.com/data/csaf/v2/vex/2026/"
            "cve-2026-42424.json"
        )
    return IngestEnvelope.for_json_payload(
        acquisition_run_id="run",
        trigger=AcquisitionTrigger.ON_DEMAND,
        source_id="source",
        external_object_id=external_id,
        payload=payload,
        canonical_url=canonical_url,
        published_at=None,
        updated_at=None,
        external_revision="r1",
    )


def test_cisa_kev_mapper_marks_known_exploited() -> None:
    candidate = CISAKEVMapper().map(_envelope("cisa_kev.json", "CVE-2026-42424"))
    values = {claim.predicate: claim.value for claim in candidate.claims}
    assert values["known_exploited"] is True
    assert values["kev_required_action"] == "Apply mitigations per vendor instructions."


def test_first_epss_mapper_preserves_point_in_time_semantics() -> None:
    candidate = FIRSTEPSSMapper().map(_envelope("first_epss.json", "CVE-2026-42424"))
    claims = {claim.predicate: claim for claim in candidate.claims}
    assert claims["epss_probability"].value == 0.01152
    assert claims["epss_percentile"].value == 0.65554
    assert claims["epss_probability"].qualifier == {
        "source_semantics": "first_epss",
        "score_date": "2026-09-27",
    }


def test_redhat_csaf_vex_mapper_preserves_full_product_scope_and_justification() -> None:
    candidate = RedHatCSAFVEXMapper().map(
        _envelope("redhat_csaf_vex.json", "CVE-2026-42424")
    )
    applicability = [
        item for item in candidate.relations if item.relation_type == "applicability-status"
    ]
    assert len(applicability) == 2
    affected = next(item for item in applicability if item.qualifier["state"] == "affected")
    assert affected.qualifier["source_semantics"] == "csaf_vex"
    assert affected.qualifier["csaf_status"] == "known_affected"
    assert affected.qualifier["scope"] == {
        "kind": "csaf_product_status",
        "product_id": "red_hat_enterprise_linux_9:example.src",
    }
    product_context = affected.qualifier["product_context"]
    assert isinstance(product_context, dict)
    component = product_context["component"]
    platform = product_context["platform"]
    assert isinstance(component, dict)
    assert isinstance(platform, dict)
    assert component["purl"] == "pkg:rpm/redhat/example?arch=src"
    assert platform["cpe"] == "cpe:/o:redhat:enterprise_linux:9"
    not_affected = next(
        item for item in applicability if item.qualifier["state"] == "not_affected"
    )
    assert not_affected.qualifier["csaf_status"] == "known_not_affected"
    assert not_affected.qualifier["justification"] == ["vulnerable_code_not_present"]
    advisory = next(item for item in candidate.relations if item.relation_type == "vendor-advisory")
    assert advisory.target.object_type == "Document"
    assert advisory.target.properties["document_kind"] == "csaf_vex"
    assert advisory.qualifier == {"source_semantics": "redhat_csaf_vex_document"}


def test_github_mapper_builds_package_relation() -> None:
    candidate = GitHubAdvisoryMapper().map(_envelope("github_advisory.json", "GHSA-aaaa-bbbb-cccc"))
    assert candidate.root_identifiers["cve"] == ["CVE-2026-42424"]
    assert candidate.root_identifiers["ghsa"] == ["GHSA-aaaa-bbbb-cccc"]
    values = {claim.predicate: claim.value for claim in candidate.claims}
    assert values["epss_probability"] == 0.01152
    assert values["epss_percentile"] == 0.65554
    package = next(item for item in candidate.relations if item.relation_type == "affects-package")
    assert package.target.canonical_key == "package:pip:vllm"
    assert package.qualifier["first_patched_version"] == "0.11.1"
    fixed = next(item for item in candidate.relations if item.relation_type == "fixed-version")
    assert fixed.target.canonical_key == "software-version:pip:vllm:0.11.1"
    applicability = next(
        item for item in candidate.relations if item.relation_type == "applicability-status"
    )
    assert applicability.target.canonical_key == "package:pip:vllm"
    assert applicability.qualifier == {
        "state": "affected",
        "source_semantics": "github_advisory_range",
        "version_range": "< 0.11.1",
    }
    weakness = next(item for item in candidate.relations if item.relation_type == "has-weakness")
    assert weakness.target.canonical_key == "weakness:CWE-306"
    advisory = next(item for item in candidate.relations if item.relation_type == "described-by")
    assert advisory.target.canonical_key == "document:github-advisory:ghsa-aaaa-bbbb-cccc"


def test_osv_mapper_builds_purl_and_version_relation() -> None:
    candidate = OSVMapper().map(_envelope("osv_cve.json", "CVE-2026-42424"))
    assert candidate.root_identifiers["ghsa"] == ["GHSA-aaaa-bbbb-cccc"]
    package = next(item for item in candidate.relations if item.relation_type == "affects-package")
    assert package.target.identifiers == {"purl": ["pkg:pypi/vllm"]}
    assert package.qualifier["versions"] == ["0.10.0", "0.11.0"]
    applicability = next(
        item for item in candidate.relations if item.relation_type == "applicability-status"
    )
    assert applicability.target.canonical_key == "package:pypi:vllm"
    assert applicability.qualifier["state"] == "affected"
    assert applicability.qualifier["source_semantics"] == "osv_range"
    assert applicability.qualifier["versions"] == ["0.10.0", "0.11.0"]
    ranges = applicability.qualifier["ranges"]
    assert isinstance(ranges, list)
    assert len(ranges) == 2
    fixed = [item for item in candidate.relations if item.relation_type == "fixed-version"]
    assert [item.target.canonical_key for item in fixed] == ["software-version:pypi:vllm:0.11.1"]
