"""04b-2 slice 4, D4 (K-04B-0002 S4 A): VIDEO_TRANSCRIPT_ENABLED is off by default and a video is
recorded at Kapı 0 as `video_disabled` (counted, never dropped silently). This build has no
transcriber (faster-whisper is a separate class-C PR), so switching the flag on stops start-up
with `video_transcriber_unavailable`. The `video` preset selects exactly the video documents,
for the reconversion once a transcriber exists."""

import pytest
from pydantic import ValidationError

from ffcore.core.config import Settings
from tests.dummy import SETTINGS_03A
from tests.integration import test_04a_api as kb_api
from tests.integration.test_04a_api import PROSE, create_kb, kb_url, process_all, upload
from tests.integration.test_04b_api import upload_bytes

queue = kb_api.queue
settings = kb_api.settings
world = kb_api.world


def test_04b_2_d4_flag_off_by_default_and_on_stops_start_up():
    assert (
        Settings(deploy_profile="airgap", offline=True, **SETTINGS_03A).video_transcript_enabled
        is False
    )
    with pytest.raises(ValidationError) as caught:
        Settings(
            deploy_profile="airgap", offline=True, video_transcript_enabled=True, **SETTINGS_03A
        )
    assert "video_transcriber_unavailable" in str(caught.value)


def test_04b_2_d4_video_preset_selects_video_documents(world, settings, queue):
    kb = create_kb(world)
    upload(world, world["admin"], kb["id"], "metin.md", PROSE * 8)
    upload_bytes(world, world["admin"], kb["id"], "egitim.mp4", b"\x00\x00\x00\x18ftypmp42" * 8)
    upload_bytes(world, world["admin"], kb["id"], "kayit.mov", b"\x00\x00\x00\x14ftypqt  " * 8)
    process_all(settings, queue)

    report = world["admin"].get(f"{kb_url(world, kb['id'])}/ingest-report").json()
    video = [d for d in report["rejected_documents"] if d["reason"] == "video_disabled"]
    assert {d["filename"] for d in video} == {"egitim.mp4", "kayit.mov"}

    url = f"{kb_url(world, kb['id'])}/reindex"
    response = world["admin"].post(url, json={"layer": "silver", "preset": "video"})
    assert response.status_code == 202, response.text
    assert response.json()["documents"] == 2 and response.json()["preset"] == "video"
    assert queue.jobs[-1] == ("reindex_job", kb["id"], "silver", False, False, "video")
