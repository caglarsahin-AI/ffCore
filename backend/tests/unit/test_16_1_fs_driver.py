"""16-1: the network-folder driver (C5), the driver registry (C14) and the deployment wiring
(sync worker, settings, .env.example). The engine around them is tested in integration."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from ffcore.sources import registry
from ffcore.sources.base import SourceError, SourceSpec
from ffcore.sources.fs import FsDriver

REPO = Path(__file__).resolve().parents[3]


def driver(settings, base, root=".", **config):
    settings = settings.model_copy(update={"fs_sources_base": str(base)})
    spec = SourceSpec(id="s", kind="fs", deployment=None, config={"root": root, **config})
    return FsDriver(spec, None, None, settings)


async def listed(d, since=None):
    return [item async for item in d.list_changes(since)]


@pytest.fixture
def tree(tmp_path):
    base = tmp_path / "base"
    (base / "paylasim" / "yonetim").mkdir(parents=True)
    (base / "paylasim" / "genel").mkdir(parents=True)
    (base / "paylasim" / "genel" / "el-kitabi.md").write_text("# El kitabı\n", encoding="utf-8")
    (base / "paylasim" / "yonetim" / "kurul.md").write_text("# Kurul\n", encoding="utf-8")
    (base / "paylasim" / "notlar.txt").write_text("not", encoding="utf-8")
    (base / "baska").mkdir()
    (base / "baska" / "gizli.md").write_text("# başka kaynak\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.env").write_text("X=1", encoding="utf-8")
    return base, outside


def test_16_1_fs_lists_relative_ids_sorted_and_counts(settings, tree):
    base, _ = tree
    d = driver(settings, base, "paylasim")
    items = asyncio.run(listed(d))
    assert [i.external_id for i in items] == [
        "genel/el-kitabi.md",
        "notlar.txt",
        "yonetim/kurul.md",
    ]
    assert asyncio.run(d.count()) == 3
    assert items[0].size == len("# El kitabı\n".encode()) and items[0].updated_at.tzinfo
    assert all(i.refused is None for i in items)


def test_16_1_fs_globs(settings, tree):
    base, _ = tree
    d = driver(settings, base, "paylasim", include_globs=["*.md"], exclude_globs=["yonetim/*"])
    assert [i.external_id for i in asyncio.run(listed(d))] == ["genel/el-kitabi.md"]
    assert asyncio.run(d.count()) == 1


def test_16_1_fs_delta_by_mtime(settings, tree):
    base, _ = tree
    old = datetime(2026, 1, 1, tzinfo=UTC).timestamp()
    for path in (base / "paylasim").rglob("*"):
        if path.is_file():
            os.utime(path, (old, old))
    changed = base / "paylasim" / "notlar.txt"
    changed.write_text("yeni not", encoding="utf-8")
    since = datetime.now(UTC) - timedelta(minutes=5)
    d = driver(settings, base, "paylasim")
    assert [i.external_id for i in asyncio.run(listed(d, since))] == ["notlar.txt"]


def test_16_1_fs_symlinks_are_refused_per_entry(settings, tree):
    base, outside = tree
    root = base / "paylasim"
    (root / "dis.env").symlink_to(outside / "secret.env")
    (root / "ic.md").symlink_to(root / "genel" / "el-kitabi.md")
    (root / "dis-klasor").symlink_to(outside, target_is_directory=True)
    d = driver(settings, base, "paylasim")
    refused = {i.external_id: i.refused for i in asyncio.run(listed(d)) if i.refused}
    assert refused == {
        "dis.env": "path_outside_base",
        "ic.md": "symlink_refused",
        "dis-klasor": "path_outside_base",
    }
    assert asyncio.run(d.count()) == 3  # refused entries are not counted (nor seen)


def test_16_1_fs_fetch_render_acl(settings, tree):
    base, _ = tree
    d = driver(settings, base, "paylasim")
    item = next(i for i in asyncio.run(listed(d)) if i.external_id == "yonetim/kurul.md")
    raw = asyncio.run(d.fetch_raw(item))
    assert raw.content == b"# Kurul\n" and raw.ext == "md"
    rendered = d.render(item, raw)
    assert rendered.filename == "kurul.md" and rendered.breadcrumb == ("yonetim", "kurul.md")
    groups = asyncio.run(d.acl(item, raw)).groups
    assert groups == ("folder:/", "folder:/yonetim")


def test_16_1_fs_fetch_refuses_a_file_swapped_for_a_symlink(settings, tree):
    base, outside = tree
    d = driver(settings, base, "paylasim")
    item = next(i for i in asyncio.run(listed(d)) if i.external_id == "notlar.txt")
    target = base / "paylasim" / "notlar.txt"
    target.unlink()
    target.symlink_to(outside / "secret.env")  # changed between listing and fetch
    with pytest.raises(SourceError) as error:
        asyncio.run(d.fetch_raw(item))
    assert error.value.code == "path_outside_base"


def test_16_1_fs_test_connection(settings, tree):
    base, _ = tree
    ok = asyncio.run(driver(settings, base, "paylasim").test_connection())
    assert ok.reachable and ok.count == 3
    missing = asyncio.run(driver(settings, base, "yok").test_connection())
    assert not missing.reachable and missing.error_code == "fs_root_missing"


def test_16_1_fs_config_refuses_paths_out_of_the_base(settings, tree):
    base, _ = tree
    for root in ("/", "../..", "/etc/passwd"):
        with pytest.raises(ValueError, match="path_outside_base"):
            driver(settings, base, root)


# --- registry ------------------------------------------------------------------------------


def test_16_1_registry_builtin_fs_and_profile_rule(settings):
    assert registry.driver_for("fs", None, settings) is FsDriver
    # A network folder works offline (airgap): it needs no outbound HTTP.
    offline = settings.model_copy(update={"offline": True})
    assert registry.driver_for("fs", None, offline) is FsDriver
    with pytest.raises(SourceError) as deployment:
        registry.driver_for("fs", "cloud", settings)
    assert deployment.value.code == "deployment_invalid"
    with pytest.raises(SourceError) as unknown:
        registry.driver_for("notion", None, settings)
    assert unknown.value.code == "source_kind_unavailable"


def test_16_1_registry_internet_deployment_is_refused_offline(settings, monkeypatch):
    class CloudOnly(FsDriver):
        kind = "cloudy"
        deployments = ("server", "cloud")
        internet_deployments = ("cloud",)

    drivers = registry.build(registry.BUILTIN, [("cloudy", CloudOnly)])
    monkeypatch.setattr(registry, "drivers", lambda: drivers)
    offline = settings.model_copy(update={"offline": True})
    # Server/Data Center sits on an internal host: allowed in airgap (OFFLINE=true).
    assert registry.driver_for("cloudy", "server", offline) is CloudOnly
    with pytest.raises(SourceError) as error:
        registry.driver_for("cloudy", "cloud", offline)
    assert error.value.code == "source_kind_unavailable"
    assert registry.driver_for("cloudy", "cloud", settings) is CloudOnly


def test_16_1_registry_refuses_duplicates_and_non_drivers():
    class Again(FsDriver):
        pass

    with pytest.raises(registry.RegistryError, match="served twice"):
        registry.build(registry.BUILTIN, [("again", Again)])
    with pytest.raises(registry.RegistryError, match="not a source driver"):
        registry.build(registry.BUILTIN, [("broken", object())])


def test_16_1_ffcore_never_imports_a_consumer():
    # C14: consumers register through the entry point group; FFCore code names none of them.
    for path in (REPO / "backend" / "ffcore").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "import paycore" not in text and "from paycore" not in text, path


# --- wiring -----------------------------------------------------------------------------


def _compose():
    return yaml.safe_load((REPO / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))


def test_16_1_sync_worker_service():
    services = _compose()["services"]
    worker = services["sync-worker"]
    assert worker["command"] == ["arq", "ffcore.sources.worker.SyncWorkerSettings"]
    assert worker["image"] == services["worker"]["image"]  # no new image (K-16-0002 S1)
    assert "build" not in worker and "profiles" not in worker
    # 16-1 r1 MINOR-2: the whole file is read into memory (Kapı 0 limit 500 MB), two jobs at once.
    assert worker["mem_limit"] == "${SYNC_WORKER_MEM_LIMIT:-2g}"
    assert (
        worker["environment"]["DATABASE_URL"] == services["backend"]["environment"]["DATABASE_URL"]
    )
    assert "knowledge_storage:/data/storage" in worker["volumes"]
    assert "${FS_SOURCES_HOST_DIR:-./data/sources}:/data/sources:ro" in worker["volumes"]
    assert (
        "${FS_SOURCES_HOST_DIR:-./data/sources}:/data/sources:ro" in services["backend"]["volumes"]
    )
    for dependency in ("postgres", "redis"):
        assert worker["depends_on"][dependency]["condition"] == "service_healthy"
    # Nothing publishes the worker; it only talks to Postgres, Redis and the sources.
    assert "ports" not in worker


def test_16_1_settings_and_env_example(settings):
    assert settings.fs_sources_base == "/data/sources"
    assert settings.prune_max_ratio == 0.2 and settings.attachment_min_date is None
    assert settings.arq_queue_sync == "sync"
    env = settings.model_validate(
        {**settings.model_dump(), "attachment_min_date": "", "prune_max_ratio": 0.5}
    )
    assert env.attachment_min_date is None and env.prune_max_ratio == 0.5
    with pytest.raises(ValueError):
        settings.model_validate({**settings.model_dump(), "prune_max_ratio": 0})
    example = (REPO / ".env.example").read_text(encoding="utf-8")
    for name in (
        "FS_SOURCES_HOST_DIR",
        "FS_SOURCES_BASE",
        "PRUNE_MAX_RATIO",
        "ATTACHMENT_MIN_DATE",
        "ARQ_QUEUE_SYNC",
        "SYNC_WORKER_MEM_LIMIT",
    ):
        assert f"\n{name}=" in example, name
    app_env = _compose()["services"]["backend"]["environment"]
    assert app_env["FS_SOURCES_BASE"] == "${FS_SOURCES_BASE:-/data/sources}"
    assert app_env["ARQ_QUEUE_SYNC"] == "${ARQ_QUEUE_SYNC:-sync}"


def test_16_1_ingest_worker_runs_source_layers():
    source = (REPO / "backend" / "ffcore" / "knowledge" / "worker.py").read_text(encoding="utf-8")
    assert "functions = [ingest_document_job, reindex_job, source_layer_job]" in source
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "python -m ffcore.sources.cli sync --project $(PROJECT) --source $(SOURCE)" in makefile


def test_16_1_smoke_sees_the_sync_worker(monkeypatch):
    import importlib.util

    import redis

    spec = importlib.util.spec_from_file_location("smoke16", REPO / "scripts" / "smoke.py")
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    assert smoke.check_sync_worker in smoke.CHECKS
    stored = {}

    class FakeRedis:
        def get(self, key):
            return stored.get(key)

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(lambda url, **kw: FakeRedis()))
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.delenv("ARQ_QUEUE_SYNC", raising=False)
    with pytest.raises(smoke.SmokeError, match="sync-worker not running"):
        smoke.check_sync_worker()
    stored["sync:health-check"] = b"j_complete=1"
    assert smoke.check_sync_worker() == "sync-worker sync:health-check present"
