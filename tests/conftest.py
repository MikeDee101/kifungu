from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kifungu.corpus import Corpus  # noqa: E402
from kifungu.ingest.index import build_index  # noqa: E402
from kifungu.ingest.pdf import ingest_pdf  # noqa: E402
from tests.fixtures import mock_statute  # noqa: E402


@pytest.fixture(scope="session")
def statute_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return mock_statute.build(tmp_path_factory.mktemp("source") / "mock_statute.pdf")


@pytest.fixture(scope="session")
def corpus(statute_pdf: Path, tmp_path_factory: pytest.TempPathFactory) -> Corpus:
    root = tmp_path_factory.mktemp("corpus") / "mock-statute"
    result = ingest_pdf(statute_pdf, "mock-statute", root, "kenya_statute", dpi=150)
    build_index(result, root)
    return result
