"""14 r2 MINOR-2 (K-14-0009): a facade agent run carries the user a key acts for, and its
question is not bound by a console run's input limit; memory recall must not end such a run.
"""

import pytest

from ffcore.api.agents_schemas import RUN_INPUT_MAX
from ffcore.memory import jobs as memory_jobs
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import NET, make_key, project_key
from tests.integration.memory_fixtures import *  # noqa: F403 - fixtures
from tests.integration.memory_support import DirectMemory, enable
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, publish
from tests.integration.runtime_support import Ports, ScriptedModel, definition, run_row, turn


class _Queue:
    def __init__(self) -> None:
        self.jobs: list[str] = []

    async def enqueue(self, run_id: str) -> str:
        self.jobs.append(run_id)
        return "job"


@pytest.fixture
def queue(monkeypatch):
    made = _Queue()
    monkeypatch.setattr(memory_jobs, "get_queue", lambda settings: made)
    return made


def test_14_r2_facade_run_with_a_long_message_recalls_within_the_limit(
    owner, pg, harness, use_queue, facade, make_user, memory_settings, set_ner, queue
):
    project, console = owner
    enable(pg, project)
    publish(pg, project, definition(knowledge=[]))
    user_id, email = make_user(memberships={project: ("user", "edit")})
    key = make_key(console, project, scopes=["agents", "impersonate"], allowed_cidrs=NET)
    ports: list[DirectMemory] = []
    use_queue(
        InlineQueue(
            harness,
            Ports(
                ScriptedModel(turn("Tamam.")), memory=DirectMemory.for_run(memory_settings, ports)
            ),
        )
    )
    question = "uzun soru " * (RUN_INPUT_MAX // 10 + 50)
    assert len(question) > RUN_INPUT_MAX
    response = facade(key).chat(f"agent:{project_key(pg, project)}/asistan", question, user=email)
    assert response.status_code == 200, response.text
    row = run_row(pg, response.headers["X-Run-Id"])
    assert row["user_id"] == user_id and row["status"] == "completed"
    (port,) = ports
    assert port.recalls == [question[:RUN_INPUT_MAX]]
    # 14-2 NOTE-1 (K-14-0020 S6): the shortened recall query is recorded, never silent.
    budget = pg.execute(
        "SELECT payload FROM run_events WHERE run_id = %s AND type = 'budget'",
        (response.headers["X-Run-Id"],),
    ).fetchone()[0]
    assert budget["memory"] == "on" and budget["question_truncated"] is True
