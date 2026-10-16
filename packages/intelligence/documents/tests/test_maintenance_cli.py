import pytest

from scripts.audit_document_quality import parse_args


def test_quality_cli_defaults_to_bounded_read_only_audit() -> None:
    args = parse_args([])
    assert args.reparse is False
    assert args.limit == 20
    assert args.document_id == []


@pytest.mark.parametrize(
    "argv",
    [
        ["--limit", "0"],
        ["--limit", "101"],
        ["--document-id", "a", "--document-id", "b", "--limit", "1"],
    ],
)
def test_quality_cli_rejects_out_of_bounds_requests(argv) -> None:
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_quality_cli_reparse_requires_explicit_flag() -> None:
    args = parse_args(["--document-id", "a", "--document-id", "b", "--reparse"])
    assert args.reparse is True
    assert args.document_id == ["a", "b"]
