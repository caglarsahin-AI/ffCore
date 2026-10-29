"""03b egress with the real system resolver (moved from the unit tests, DRIFT-85).

An RFC 6761 `.invalid` name never resolves, so the call is a failed request with
`egress_dns_failed`. Docker's embedded DNS forwards unknown names to the host's resolver and may
answer slowly; the budget is wide, and a lookup that still does not finish is reported as
NOT_RUN with its reason, never as a pass (a timeout is not the expected result).

The lookup leaves the stack (host or institution DNS), so the test runs only with
RUN_DNS_TESTS=1 (review r1 MAJOR-1); without it the root conftest skips it as NOT_RUN before any
fixture or lookup runs.
"""

import anyio
import pytest

from ffcore.core import egress
from ffcore.core.egress import EgressRequestFailed, EgressTimeout, EgressTimeoutError

pytestmark = pytest.mark.dns

UNRESOLVABLE = "no-such-provider.invalid"
LOOKUP_BUDGET_S = 30


async def _get(client, url):
    async with client:
        return await client.request("GET", url)


def test_03b_2_unresolvable_host_is_request_failed_with_the_system_resolver(app_settings):
    settings = app_settings.model_copy(update={"allowed_internal_hosts": [UNRESOLVABLE]})
    budget = EgressTimeout(connect=LOOKUP_BUDGET_S, read=2, total=LOOKUP_BUDGET_S + 5)
    client = egress.SafeOutboundClient(
        timeout=budget, settings=settings, resolver=egress.system_resolver
    )
    try:
        anyio.run(_get, client, f"http://{UNRESOLVABLE}:11434/api/tags")
    except EgressRequestFailed as exc:
        assert exc.code == "egress_dns_failed"
        assert UNRESOLVABLE in str(exc) and "/api/tags" not in str(exc)
        return
    except EgressTimeoutError:
        pytest.skip(f"NOT_RUN: the system resolver did not answer within {LOOKUP_BUDGET_S} s")
    pytest.fail("an unresolvable host returned a response")
