"""10c-1 r2 (K-10C1-0008): an event stream must reach the browser event by event.

The console proxies /api/v1 through Next.js, whose compression buffers a gzip response until it
ends, so a live stream delivered nothing until it closed. `Cache-Control: no-transform` keeps a
proxy from compressing it, `X-Accel-Buffering: no` keeps nginx from buffering it; both are the
defaults of every EventStreamResponse (06a runs, 09 exams).
"""

from ffcore.api.runs import EventStreamResponse


async def _body():
    yield "event: progress\ndata: {}\n\n"


def test_10c1_stream_headers_defaults():
    response = EventStreamResponse(_body())
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.media_type == "text/event-stream"


def test_10c1_stream_headers_extra_kept_with_defaults():
    response = EventStreamResponse(_body(), headers={"X-Extra": "1"})
    assert response.headers["x-extra"] == "1"
    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
