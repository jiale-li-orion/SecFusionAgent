from packages.intelligence.knowledge.vocabulary import (
    EnrichmentDimension,
    VocabularyScope,
    canonical_term,
    classify_object_type,
    classify_term,
)


def test_canonical_terms_have_stable_dimensions() -> None:
    cvss = canonical_term("claim", "cvss_score")
    assert cvss is not None
    assert cvss.dimension is EnrichmentDimension.SEVERITY
    affected = canonical_term("relation", "affects-package")
    assert affected is not None
    assert affected.dimension is EnrichmentDimension.PRODUCT_PACKAGE


def test_provider_fields_are_source_specific_and_model_only_terms_are_exploratory() -> None:
    assert (
        classify_term("claim", "github_summary", origin="source_asserted")
        is VocabularyScope.SOURCE_SPECIFIC
    )
    assert (
        classify_term("claim", "novel_model_finding", origin="semantic_derived")
        is VocabularyScope.EXPLORATORY
    )
    assert (
        classify_term("claim", "novel_deterministic_field", origin="deterministic_derived")
        is VocabularyScope.UNREGISTERED
    )


def test_object_types_are_closed_for_deterministic_writes_but_open_for_semantic_candidates() -> (
    None
):
    assert classify_object_type("Package", origin="source_asserted") is VocabularyScope.CANONICAL
    assert (
        classify_object_type("NovelResearchEntity", origin="semantic_derived")
        is VocabularyScope.EXPLORATORY
    )
    assert (
        classify_object_type("NovelResearchEntity", origin="deterministic_derived")
        is VocabularyScope.UNREGISTERED
    )


def test_canonical_scope_requires_registered_subject_and_target_shape() -> None:
    assert (
        classify_term(
            "relation",
            "affects-product",
            origin="semantic_derived",
            subject_type="Vulnerability",
            target_type="Product",
        )
        is VocabularyScope.CANONICAL
    )
    assert (
        classify_term(
            "relation",
            "affects-product",
            origin="semantic_derived",
            subject_type="ResearchWork",
            target_type="Product",
        )
        is VocabularyScope.EXPLORATORY
    )
    assert (
        classify_term(
            "relation",
            "affects-product",
            origin="deterministic_derived",
            subject_type="ResearchWork",
            target_type="Product",
        )
        is VocabularyScope.UNREGISTERED
    )


def test_applicability_is_scoped_relation_not_unbound_vulnerability_claim() -> None:
    term = canonical_term("relation", "applicability-status")
    assert term is not None
    assert term.dimension is EnrichmentDimension.VERSION_APPLICABILITY
    assert term.subject_types == ("Vulnerability",)
    assert term.target_types == ("Product", "Package", "SoftwareVersion")
    assert canonical_term("claim", "applicability-status") is None


def test_applicability_requires_state_and_source_semantics_to_be_canonical() -> None:
    assert (
        classify_term(
            "relation",
            "applicability-status",
            origin="deterministic_derived",
            subject_type="Vulnerability",
            target_type="Package",
            qualifier_keys={"state", "source_semantics"},
        )
        is VocabularyScope.CANONICAL
    )
    assert (
        classify_term(
            "relation",
            "applicability-status",
            origin="deterministic_derived",
            subject_type="Vulnerability",
            target_type="Package",
            qualifier_keys={"state"},
        )
        is VocabularyScope.UNREGISTERED
    )
    assert (
        classify_term(
            "relation",
            "applicability-status",
            origin="semantic_derived",
            subject_type="Vulnerability",
            target_type="Package",
            qualifier_keys={"state"},
        )
        is VocabularyScope.EXPLORATORY
    )
