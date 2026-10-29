"""02 review r1 (K-02-0010): the ingest worker process uses the central log configuration; arq's
own handler, installed by its CLI, writes scrubbed records too."""

import asyncio
import logging
import logging.config
import os

import pytest
from arq.logs import default_log_config
from pydantic import SecretStr

from ffcore.core.config import Settings
from ffcore.knowledge import worker
from tests.dummy import SETTINGS_03A

SECRET = "dummy-not-secret-02r1-worker-0123"
EMAIL = "worker.user@example.test"


@pytest.fixture
def worker_settings(monkeypatch):
    if not os.environ.get("REDIS_URL"):
        pytest.fail("REDIS_URL is not set; run in the tools container with redis up")
    settings = Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token=SecretStr(SECRET),
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        fake_embed=True,
        redis_url=os.environ["REDIS_URL"],
        **SETTINGS_03A,
    )
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    return settings


def test_02_r1_worker_startup_configures_logging(worker_settings, capsys):
    # The arq CLI: dictConfig with its own stderr handler, then the worker's startup hook.
    logging.config.dictConfig(default_log_config(verbose=False))
    asyncio.run(worker.startup({}))
    log = logging.getLogger("arq.worker")
    log.info("job for %s with %s", EMAIL, SECRET)
    err = capsys.readouterr().err
    assert "job for" in err
    assert SECRET not in err and EMAIL not in err
