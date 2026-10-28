"""Convert workers that can be stopped: one process each, killed when a file runs out of time.

Adapted from PayCore `convert/workers.BoundedPool` (brief 04 D2, step 5): a thread cannot be
stopped from outside, so every file converts in a long-lived worker process (models load once
per worker, not per file) with a deadline. Past it the worker's whole process group is killed,
the file is recorded as `timeout` (not retried by a plain run) and a fresh worker takes the
next file. Workers never touch the database; the parent records every result.
"""

import contextlib
import importlib
import logging
import multiprocessing
import os
import queue
import signal
import sys
import threading
import time
from collections.abc import Callable, Iterable
from multiprocessing.connection import Connection
from pathlib import Path

from ffcore.knowledge.convert.types import ERROR, TIMEOUT, ConversionResult

log = logging.getLogger("ffcore.knowledge.convert")

Target = Callable[[Path, float], ConversionResult]
OnStart = Callable[[Path], None]
OnResult = Callable[[Path, ConversionResult, float], None]


def _resolve(target: str) -> Target:
    module, _, name = target.partition(":")
    return getattr(importlib.import_module(module), name)


def _worker_main(target: str, conn: Connection) -> None:
    if hasattr(os, "setsid"):
        # Own process group: a kill also takes children a converter started.
        with contextlib.suppress(OSError):
            os.setsid()
    fn = _resolve(target)
    while True:
        try:
            job = conn.recv()
        except EOFError:
            return
        if job is None:
            return
        path, deadline = job
        try:
            result = fn(Path(path), deadline)
        except Exception as exc:  # noqa: BLE001 - the file's error, the worker lives on
            result = ConversionResult(
                "", "worker", status=ERROR, warnings=[str(exc)[:500]], error_code="convert_failed"
            )
        conn.send(result)


def _spawn_safe_sys_path() -> None:
    """OpenCV's import puts site-packages/cv2 on sys.path; a spawned child inherits sys.path and
    then resolves `typing` to cv2/typing and dies on import. Drop that entry before spawning
    (the already imported cv2 package does not need it)."""
    sys.path[:] = [p for p in sys.path if os.path.basename(p.rstrip("/\\")) != "cv2"]


class _Worker:
    def __init__(self, target: str, name: str):
        _spawn_safe_sys_path()
        ctx = multiprocessing.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.process = ctx.Process(target=_worker_main, args=(target, child), name=name)
        self.process.start()
        child.close()

    def kill(self) -> None:
        pid = self.process.pid
        if pid is not None and hasattr(os, "killpg"):
            with contextlib.suppress(OSError):
                os.killpg(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        with contextlib.suppress(Exception):
            self.process.kill()
        self.process.join(10)
        self.conn.close()

    def stop(self) -> None:
        with contextlib.suppress(OSError, BrokenPipeError):
            self.conn.send(None)
        self.process.join(10)
        if self.process.is_alive():
            self.kill()
        else:
            self.conn.close()


class BoundedPool:
    """`size` worker processes; each file gets `timeout` seconds."""

    def __init__(self, size: int, timeout: float, name: str, target: str):
        self.size = max(1, size)
        self.timeout = timeout
        self.name = name
        self.target = target

    def run(self, paths: Iterable[Path], on_start: OnStart, on_result: OnResult) -> None:
        jobs: queue.Queue[Path] = queue.Queue()
        for path in paths:
            jobs.put(path)
        if jobs.empty():
            return
        threads = [
            threading.Thread(target=self._dispatch, args=(jobs, on_start, on_result, i))
            for i in range(min(self.size, jobs.qsize()))
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    def _dispatch(self, jobs, on_start: OnStart, on_result: OnResult, index: int) -> None:
        worker: _Worker | None = None
        try:
            while True:
                try:
                    path = jobs.get_nowait()
                except queue.Empty:
                    return
                if worker is None:
                    worker = _Worker(self.target, f"{self.name}-worker-{index}")
                on_start(path)
                started = time.time()
                result, worker = self._one(worker, path, started)
                on_result(path, result, time.time() - started)
        finally:
            if worker is not None:
                worker.stop()

    def _one(self, worker: _Worker, path: Path, started: float):
        try:
            worker.conn.send((str(path), started + self.timeout))
            if worker.conn.poll(self.timeout):
                return worker.conn.recv(), worker
        except (EOFError, OSError) as exc:
            log.error("convert_worker_died path=%s pool=%s error=%s", path, self.name, exc)
            worker.kill()
            return (
                ConversionResult(
                    "",
                    "worker",
                    status=ERROR,
                    warnings=[f"worker died: {exc}"],
                    error_code="worker_died",
                ),
                None,
            )
        log.warning("convert_timeout path=%s pool=%s seconds=%s", path, self.name, self.timeout)
        worker.kill()
        return (
            ConversionResult(
                "",
                "timeout",
                status=TIMEOUT,
                warnings=[f"exceeded {int(self.timeout)} s"],
                error_code="convert_timeout",
            ),
            None,
        )


class PersistentPool(BoundedPool):
    """One long-lived worker process for the ingest worker's jobs: Docling and PaddleOCR load
    once per process, not once per document (PayCore's design; A-04a-0020 measured 66 s of a
    131 s ingest in a freshly spawned process). A timeout or a crash replaces the process."""

    def __init__(self, timeout: float, name: str, target: str):
        super().__init__(size=1, timeout=timeout, name=name, target=target)
        self._worker: _Worker | None = None
        self._lock = threading.Lock()

    def convert(self, path: Path) -> ConversionResult:
        with self._lock:
            if self._worker is None:
                self._worker = _Worker(self.target, f"{self.name}-worker")
            result, self._worker = self._one(self._worker, path, time.time())
            return result

    def close(self) -> None:
        with self._lock:
            if self._worker is not None:
                self._worker.stop()
                self._worker = None
