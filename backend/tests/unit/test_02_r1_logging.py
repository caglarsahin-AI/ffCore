"""02 review r1, logging: MAJOR-1 (every handler, whenever installed), MAJOR-2 (the scrubber
never raises), MAJOR-5 (personal data: access log without query, 08-lite recognizers)."""

import io
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from ffcore.core.logging import configure_logging, scrub
from ffcore.guardrails.recognizers.regex import tc_valid

SECRET = "dummy-not-secret-02r1-SENTINEL-0123"
EMAIL = "ayse.yilmaz@example.test"
TCKN = "12345678950"  # synthetic, passes the TC checksum


@pytest.fixture
def lf_secret(settings):
    settings.service_token = SecretStr(SECRET)
    yield settings
    configure_logging(settings, level="WARNING", stream=io.StringIO())


def _handler(target):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    target.addHandler(handler)
    return handler, stream


def test_02_r1_synthetic_tckn_is_valid():
    assert tc_valid(TCKN)


# --- MAJOR-1: handlers installed before and after configure_logging ---


def test_02_r1_m1_prior_and_later_handlers_scrubbed(lf_secret):
    root = logging.getLogger()
    prior, prior_out = _handler(root)
    try:
        configure_logging(lf_secret, level="DEBUG", stream=io.StringIO())
        later, later_out = _handler(logging.getLogger("arq.worker"))  # arq's dictConfig comes later
        try:
            log = logging.getLogger("arq.worker")
            log.info("job with %s", SECRET)
            try:
                raise RuntimeError(f"failed with {SECRET}")
            except RuntimeError:
                log.exception("boom")
        finally:
            logging.getLogger("arq.worker").removeHandler(later)
    finally:
        root.removeHandler(prior)
    for out in (prior_out.getvalue(), later_out.getvalue()):
        assert "job with ***" in out and "boom" in out and "RuntimeError" in out
        assert SECRET not in out


# --- MAJOR-2: no input makes the logging call raise ---


@pytest.mark.parametrize(
    ("msg", "args"),
    [
        (f"50% done token={SECRET}", ()),
        (f"GET /a%20b?api_key={SECRET} %s", ()),
        ("mapping %(who)s token=%(tok)s", ({"who": "x", "tok": SECRET},)),
        ("literal %s", (f"Bearer {SECRET}",)),
    ],
)
def test_02_r1_m2_percent_inputs_never_raise(lf_secret, msg, args):
    out = io.StringIO()
    configure_logging(lf_secret, level="DEBUG", stream=out)
    logging.getLogger("ffcore.test02r1").info(msg, *args)
    text = out.getvalue()
    assert SECRET not in text and "***" in text
    assert "Logging error" not in text


class _Broken:
    def __str__(self):
        raise ValueError(f"cannot render {SECRET}")


def test_02_r1_m2_scrub_failure_counted_not_raw(lf_secret):
    out = io.StringIO()
    configure_logging(lf_secret, level="DEBUG", stream=out)
    logging.getLogger("ffcore.test02r1").info("value %s", _Broken())
    text = out.getvalue()
    assert "log_scrub_failed logger=ffcore.test02r1 error=ValueError" in text
    assert SECRET not in text


# --- MAJOR-5: personal data ---


def test_02_r1_m5_personal_data_masked_everywhere(lf_secret):
    root = logging.getLogger()
    prior, prior_out = _handler(root)
    try:
        configure_logging(lf_secret, level="DEBUG", stream=io.StringIO())
        log = logging.getLogger("ffcore.test02r1")
        log.info(f"user {EMAIL} tc {TCKN}")
        log.info("user %s tc %s", EMAIL, TCKN)
        try:
            raise LookupError(f"no row for {EMAIL} / {TCKN}")
        except LookupError:
            log.exception("lookup")
    finally:
        root.removeHandler(prior)
    text = prior_out.getvalue()
    assert EMAIL not in text and TCKN not in text
    assert text.count("@example.test") == 3  # mask_value keeps the domain


def test_02_r1_m5_scrub_masks_personal_data():
    text = scrub(f"mail={EMAIL} id {TCKN}", ())
    assert EMAIL not in text and TCKN not in text


def test_02_r1_m5_access_log_without_query(lf_secret):
    from ffcore.core.logging import AccessLogMiddleware

    out = io.StringIO()
    configure_logging(lf_secret, level="INFO", stream=out)
    app = FastAPI()
    app.add_middleware(AccessLogMiddleware)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    with TestClient(app) as client:
        assert client.get(f"/healthz?email={EMAIL}&tc={TCKN}").status_code == 200
        assert client.get("/missing").status_code == 404
    text = out.getvalue()
    assert "access method=GET path=/healthz status=200 ms=" in text
    assert "access method=GET path=/missing status=404 ms=" in text
    assert "?" not in text and EMAIL not in text and TCKN not in text
    assert logging.getLogger("uvicorn.access").disabled
