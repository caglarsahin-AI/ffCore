"""Convert workers that can be stopped: one process each, killed when a file runs out of time.

Adapted from PayCore `convert/workers.BoundedPool` (brief 04 D2, step 5): a thread cannot be
stopped from outside, so every file converts in a long-lived worker process (models load once
per worker, not per file) with a deadline. Past it the worker's whole process group is killed,
the file is recorded as `timeout` (not retried by a plain run) and a fresh worker takes the
next file. Workers never touch the database; the parent records every result.

Each worker also runs under resource limits (review r1 MAJOR-5): RLIMIT_AS bounds its address
space (a MemoryError is the file's `convert_memory_limit`, the worker lives on) and RLIMIT_CPU
bounds each file's CPU seconds (SIGXCPU kills the worker: `convert_cpu_limit`). The timeout
alone does not stop a file from taking all memory before it runs out.
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
from dataclasses import dataclass
from multiprocessing.connection import Connection
from pathlib import Path

from ffcore.knowledge.convert.types import ERROR, TIMEOUT, ConversionResult

log = logging.getLogger("ffcore.knowledge.convert")

Target = Callable[[Path, float], ConversionResult]
OnStart = Callable[[Path], None]
OnResult = Callable[[Path, ConversionResult, float], None]


@dataclass(frozen=True)
class Limits:
    memory_mb: int | None = None
    cpu_seconds: int | None = None


NO_LIMITS = Limits()

# The one message a worker sends before its first file (FOLLOWUP-97): a file's time starts only
# after it, so spawning and importing never count against the file's timeout. Models load
# lazily in the converters, so the first document's model load still counts (K-04aWR-0002 A).
READY = "ready"
# Spawn + imports, bounded on its own: the default is wide, a slow start is not a slow file.
DEFAULT_START_TIMEOUT = 60.0


def _apply_memory_limit(limits: Limits) -> None:
    if limits.memory_mb is None:
        return
    import resource

    size = limits.memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (size, size))


def _apply_cpu_budget(limits: Limits) -> None:
    """The CPU limit is per process; a long-lived worker gets `cpu_seconds` more per file."""
    if limits.cpu_seconds is None:
        return
    import resource

    used = resource.getrusage(resource.RUSAGE_SELF)
    spent = int(used.ru_utime + used.ru_stime)
    resource.setrlimit(resource.RLIMIT_CPU, (spent + limits.cpu_seconds, resource.RLIM_INFINITY))


def _resolve(target: str) -> Target:
    module, _, name = target.partition(":")
    return getattr(importlib.import_module(module), name)


def _worker_main(target: str, conn: Connection, limits: Limits = NO_LIMITS) -> None:
    if hasattr(os, "setsid"):
        # Own process group: a kill also takes children a converter started.
        with contextlib.suppress(OSError):
            os.setsid()
    fn = _resolve(target)
    # After the imports: the limit is for the files, measured on a worker with its models.
    _apply_memory_limit(limits)
    conn.send(READY)
    while True:
        try:
            job = conn.recv()
        except EOFError:
            return
        if job is None:
            return
        path, deadline = job
        _apply_cpu_budget(limits)
        try:
            result = fn(Path(path), deadline)
        except MemoryError:
            result = ConversionResult(
                "",
                "worker",
                status=ERROR,
                warnings=[f"memory limit {limits.memory_mb} MB"],
                error_code="convert_memory_limit",
            )
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
    def __init__(self, target: str, name: str, limits: Limits = NO_LIMITS):
        _spawn_safe_sys_path()
        ctx = multiprocessing.get_context("spawn")
        self.conn, child = ctx.Pipe()
        self.process = ctx.Process(target=_worker_main, args=(target, child, limits), name=name)
        self.process.start()
        child.close()
        self.ready = False

    def wait_ready(self, timeout: float) -> bool:
        """True once the worker said `ready`; False if it did not within `timeout`. A worker
        that dies first raises EOFError (the caller records `worker_died`)."""
        if self.ready:
            return True
        if not self.conn.poll(timeout):
            return False
        message = self.conn.recv()
        if message != READY:
            raise OSError(f"unexpected first message from worker: {message!r}")
        self.ready = True
        return True

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
    """`size` worker processes; each file gets `timeout` seconds once its worker is ready, a
    fresh worker gets `start_timeout` seconds to become ready."""

    def __init__(
        self,
        size: int,
        timeout: float,
        name: str,
        target: str,
        limits: Limits = NO_LIMITS,
        start_timeout: float = DEFAULT_START_TIMEOUT,
    ):
        self.size = max(1, size)
        self.timeout = timeout
        self.name = name
        self.target = target
        self.limits = limits
        self.start_timeout = start_timeout

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
                    worker = _Worker(self.target, f"{self.name}-worker-{index}", self.limits)
                on_start(path)
                started = time.time()
                result, worker = self._one(worker, path)
                on_result(path, result, time.time() - started)
        finally:
            if worker is not None:
                worker.stop()

    def _one(self, worker: _Worker, path: Path):
        try:
            if not worker.wait_ready(self.start_timeout):
                return self._start_timeout(worker, path), None
            worker.conn.send((str(path), time.time() + self.timeout))
            if worker.conn.poll(self.timeout):
                return worker.conn.recv(), worker
        except (EOFError, OSError) as exc:
            worker.process.join(5)
            exitcode = worker.process.exitcode
            worker.kill()
            cpu = exitcode == -getattr(signal, "SIGXCPU", -1)
            code = "convert_cpu_limit" if cpu else "worker_died"
            log.error(
                "convert_worker_died path=%s pool=%s code=%s exitcode=%s error=%s",
                path,
                self.name,
                code,
                exitcode,
                exc,
            )
            message = f"cpu limit {self.limits.cpu_seconds} s" if cpu else f"worker died: {exc}"
            return (
                ConversionResult("", "worker", status=ERROR, warnings=[message], error_code=code),
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

    def _start_timeout(self, worker: _Worker, path: Path) -> ConversionResult:
        log.error(
            "convert_worker_start_timeout path=%s pool=%s seconds=%s",
            path,
            self.name,
            self.start_timeout,
        )
        worker.kill()
        return ConversionResult(
            "",
            "worker",
            status=ERROR,
            warnings=[f"worker not ready in {int(self.start_timeout)} s"],
            error_code="convert_worker_start_timeout",
        )


class PersistentPool(BoundedPool):
    """One long-lived worker process for the ingest worker's jobs: Docling and PaddleOCR load
    once per process, not once per document (PayCore's design; A-04a-0020 measured 66 s of a
    131 s ingest in a freshly spawned process). A timeout or a crash replaces the process."""

    def __init__(
        self,
        timeout: float,
        name: str,
        target: str,
        limits: Limits = NO_LIMITS,
        start_timeout: float = DEFAULT_START_TIMEOUT,
    ):
        super().__init__(
            size=1,
            timeout=timeout,
            name=name,
            target=target,
            limits=limits,
            start_timeout=start_timeout,
        )
        self._worker: _Worker | None = None
        self._lock = threading.Lock()

    def convert(self, path: Path) -> ConversionResult:
        with self._lock:
            if self._worker is None:
                self._worker = _Worker(self.target, f"{self.name}-worker", self.limits)
            result, self._worker = self._one(self._worker, path)
            return result

    def close(self) -> None:
        with self._lock:
            if self._worker is not None:
                self._worker.stop()
                self._worker = None
