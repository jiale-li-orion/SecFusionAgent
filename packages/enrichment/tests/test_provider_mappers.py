import json
from pathlib import Path

from packages.enrichment.processors.cisa_kev import CISAKEVMapper
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
    return IngestEnvelope.for_json_payload(
        acquisition_run_id="run",
        trigger=AcquisitionTrigger.ON_DEMAND,
        source_id="source",
        external_object_id=external_id,
        payload=payload,
        canonical_url=None,
        published_at=None,
        updated_at=None,
        external_revision="r1",
    )


def test_cisa_kev_mapper_marks_known_exploited() -> None:
    candidate = CISAKEVMapper().map(_envelope("cisa_kev.json", "CVE-2026-42424"))
    values = {claim.predicate: claim.value for claim in candidate.claims}
    assert values["known_exploited"] is True
    assert values["kev_required_action"] == "Apply mitigations per vendor instructions."


def test_github_mapper_builds_package_relation() -> None:
    candidate = GitHubAdvisoryMapper().map(_envelope("github_advisory.json", "GHSA-aaaa-bbbb-cccc"))
    assert candidate.root_identifiers["cve"] == ["CVE-2026-42424"]
    assert candidate.root_identifiers["ghsa"] == ["GHSA-aaaa-bbbb-cccc"]
    assert candidate.relations[0].target.canonical_key == "package:pip:vllm"
    assert candidate.relations[0].qualifier["first_patched_version"] == "0.11.1"


def test_osv_mapper_builds_purl_and_version_relation() -> None:
    candidate = OSVMapper().map(_envelope("osv_cve.json", "CVE-2026-42424"))
    assert candidate.root_identifiers["ghsa"] == ["GHSA-aaaa-bbbb-cccc"]
    relation = candidate.relations[0]
    assert relation.target.identifiers == {"purl": ["pkg:pypi/vllm"]}
    assert relation.qualifier["versions"] == ["0.10.0", "0.11.0"]
