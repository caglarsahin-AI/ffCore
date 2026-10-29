"""Opt-in test groups (handbook ENVIRONMENT_AND_COMMANDS "Bayraklar").

`-m models`: real bge-m3, reranker, Docling layout and PaddleOCR weights (RUN_MODEL_TESTS=1,
`make test-models`). `-m vectorstore`: a Qdrant container (RUN_QDRANT_TESTS=1). Without the flag
they are skipped with the reason shown, so a run lists them as not run instead of hiding them.
"""

import os

import pytest

FLAGS = {"models": "RUN_MODEL_TESTS", "vectorstore": "RUN_QDRANT_TESTS"}


def pytest_collection_modifyitems(config, items):
    for item in items:
        for marker, flag in FLAGS.items():
            if marker in item.keywords and os.environ.get(flag) != "1":
                item.add_marker(pytest.mark.skip(reason=f"NOT_RUN: needs {flag}=1"))
