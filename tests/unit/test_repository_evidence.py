"""Reject encoding damage that can silently change published formulas."""

import pytest

from scripts import verify_repository_evidence as verifier


@pytest.mark.parametrize(
    "content",
    [
        "# Reproducci?n\n",
        "`basis = futures_close / spot_close ? 1`\n",
        "Drawdown: ?0,2062 %\n",
        "Un car\ufffdcter perdido.\n",
    ],
)
def test_document_encoding_rejects_lost_characters(content):
    with pytest.raises(ValueError, match="Encoding damage"):
        verifier.check_document_encoding(content, "README.md")


def test_document_encoding_preserves_questions_and_url_queries():
    verifier.check_document_encoding(
        "# Reproducción\n¿Verificado? Sí.\n"
        "`basis = futures_close / spot_close − 1`\n"
        "[Fuente](https://example.org/rules?RuleID=9025&Section=9).\n",
        "README.md",
    )
