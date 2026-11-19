"""FOLLOWUP-197 (R-10C2-0008 MINOR-1 `ozet-skaler-500`): a stored summary that is not a mapping at
all (a bare number, `true`, a list, a string) is answered like any other summary that does not fit
`EvalSummary` (10c-2 r1 NOTE-2): `summary: null` and one `eval_summary_invalid` warning, never a
500 from building the missing-key set out of a non-mapping.
"""

import logging

import pytest

from ffcore.api.eval import run_out
from tests.unit.test_10c2_r2_summary_invalid import _row


@pytest.mark.parametrize("summary", [7, 0.5, True, False, 0, [1, 2], "summary"])
def test_10c3_0_non_mapping_summary_is_null_and_logged(caplog, summary):
    with caplog.at_level(logging.WARNING):
        out = run_out(_row(summary))
    assert out.summary is None
    lines = [r.getMessage() for r in caplog.records if "eval_summary_invalid" in r.getMessage()]
    assert len(lines) == 1
    assert "abcdefab-cdef-4abc-8def-abcdefabcdef" in lines[0]
    # Every contract key is missing from a value that is not a mapping.
    assert "scored" in lines[0] and "worst" in lines[0]
