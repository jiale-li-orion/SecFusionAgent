from scripts.run_prospective_investigation_probe import (
    _relation_supports_expected_fixed_version,
)


def test_fixed_version_gold_accepts_canonical_fixed_version_relation() -> None:
    assert _relation_supports_expected_fixed_version(
        relation_type="fixed-version",
        target_canonical_key="software-version:pip:pkg:4.2.1",
        qualifier={},
        expected_fixed_version="4.2.1",
    )


def test_fixed_version_gold_accepts_first_patched_package_relation() -> None:
    assert _relation_supports_expected_fixed_version(
        relation_type="affects-package",
        target_canonical_key="package:pip:pkg",
        qualifier={"first_patched_version": "4.2.1"},
        expected_fixed_version="4.2.1",
    )


def test_fixed_version_gold_rejects_unrelated_version_relation() -> None:
    assert not _relation_supports_expected_fixed_version(
        relation_type="applicability-status",
        target_canonical_key="package:pip:pkg",
        qualifier={"less_than": "4.2.1"},
        expected_fixed_version="4.2.1",
    )
