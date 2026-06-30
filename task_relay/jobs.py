from __future__ import annotations

import json
import os
import signal
import asyncio
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

from task_relay import worktree

JOB_STATUS_CREATED = "created"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_SUCCEEDED = "succeeded"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_TIMEOUT = "timeout"
JOB_STATUS_STALLED = "stalled"
JOB_STATUS_KILLED = "killed"
TERMINAL_STATUSES = {
    JOB_STATUS_SUCCEEDED,
    JOB_STATUS_FAILED,
    JOB_STATUS_TIMEOUT,
    JOB_STATUS_KILLED,
}

DEFAULT_STALL_TIMEOUT = 900.0
_BACKGROUND_PROCS: dict[int, subprocess.Popen[str]] = {}


@dataclass(frozen=True)
class JobSpec:
    command: list[str]
    stdin_input: str = ""
    cwd: str | None = None
    env: dict[str, str] | None = None
    encoding: str = "utf-8"
    timeout: float | None = 1800
    target: str | None = None
    model: str | None = None
    role: str | None = None
    change: str | None = None
    task: str | None = None
    branch: str | None = None
    session: str | None = None
    expected_outputs: list[str] = field(default_factory=list)
    stall_timeout: float | None = None
    job_id: str | None = None


@dataclass(frozen=True)
class JobRunResult:
    stdout: str
    stderr: str
    returncode: int | None
    status: str
    job_id: str
    log_path: str
    stdout_log_path: str
    stderr_log_path: str


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    status: str
    pid: int | None
    returncode: int | None
    started_at: float | None
    ended_at: float | None
    updated_at: float
    target: str | None
    model: str | None
    role: str | None
    change: str | None
    task: str | None
    log_path: str
    stdout_log_path: str
    stderr_log_path: str
    expected_outputs: list[str]
    error: str | None = None
    last_output_at: float | None = None


def runtime_root(cwd: str | None = None) -> Path:
    repo_root = worktree.git_repo_root(cwd)
    base = repo_root or (Path(cwd).resolve() if cwd else Path.cwd())
    return base / ".task_relay" / "jobs"


def new_job_id(prefix: str | None = None) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    raw = f"{prefix or 'job'}-{stamp}-{suffix}"
    return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in raw)


def create_metadata(spec: JobSpec) -> dict:
    job_id = spec.job_id or new_job_id(spec.target or "job")
    job_dir = runtime_root(spec.cwd) / job_id
    stdout_log = job_dir / "stdout.log"
    stderr_log = job_dir / "stderr.log"
    combined_log = job_dir / "combined.log"
    now = time.time()
    return {
        "id": job_id,
        "command": spec.command,
        "cwd": spec.cwd,
        "target": spec.target,
        "model": spec.model,
        "role": spec.role,
        "change": spec.change,
        "task": spec.task,
        "branch": spec.branch,
        "session": spec.session,
        "pid": None,
        "pgid": None,
        "status": JOB_STATUS_CREATED,
        "returncode": None,
        "created_at": now,
        "started_at": None,
        "ended_at": None,
        "updated_at": now,
        "last_output_at": None,
        "timeout": spec.timeout,
        "stall_timeout": _stall_timeout(spec),
        "expected_outputs": list(spec.expected_outputs),
        "stdout_log_path": str(stdout_log),
        "stderr_log_path": str(stderr_log),
        "log_path": str(combined_log),
        "error": None,
    }


def run_blocking(spec: JobSpec) -> JobRunResult:
    meta = create_metadata(spec)
    job_dir = Path(meta["log_path"]).parent
    job_dir.mkdir(parents=True, exist_ok=True)
    _write_metadata(job_dir, meta)

    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            spec.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding=spec.encoding,
            errors="replace",
            cwd=spec.cwd,
            env=spec.env,
            start_new_session=(os.name != "nt"),
        )
        meta.update({
            "pid": proc.pid,
            "pgid": _safe_getpgid(proc.pid),
            "status": JOB_STATUS_RUNNING,
            "started_at": time.time(),
            "updated_at": time.time(),
        })
        _write_metadata(job_dir, meta)

        if proc.stdin is not None:
            proc.stdin.write(spec.stdin_input)
            proc.stdin.close()

        threads = [
            threading.Thread(
                target=_pump_stream,
                args=(proc.stdout, Path(meta["stdout_log_path"]), Path(meta["log_path"]), stdout_parts, job_dir),
                daemon=True,
            ),
            threading.Thread(
                target=_pump_stream,
                args=(proc.stderr, Path(meta["stderr_log_path"]), Path(meta["log_path"]), stderr_parts, job_dir),
                daemon=True,
            ),
        ]
        for thread in threads:
            thread.start()

        try:
            returncode = proc.wait(timeout=spec.timeout)
            status = JOB_STATUS_SUCCEEDED if returncode == 0 else JOB_STATUS_FAILED
        except subprocess.TimeoutExpired:
            terminate_process_tree(proc.pid)
            returncode = proc.wait(timeout=5)
            status = JOB_STATUS_TIMEOUT

        for thread in threads:
            thread.join(timeout=5)

        error = None
        if status == JOB_STATUS_SUCCEEDED:
            missing_error = _expected_output_error(spec.expected_outputs, spec.cwd)
            if missing_error:
                status = JOB_STATUS_FAILED
                error = missing_error
        elif status == JOB_STATUS_FAILED:
            error = "process exited with non-zero status"

        meta.update({
            "status": status,
            "returncode": returncode,
            "ended_at": time.time(),
            "updated_at": time.time(),
            "last_output_at": _last_output_at(meta),
            "error": error,
        })
        _write_metadata(job_dir, meta)
        return JobRunResult(
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            returncode=returncode,
            status=status,
            job_id=str(meta["id"]),
            log_path=str(meta["log_path"]),
            stdout_log_path=str(meta["stdout_log_path"]),
            stderr_log_path=str(meta["stderr_log_path"]),
        )
    except FileNotFoundError:
        meta.update({
            "status": JOB_STATUS_FAILED,
            "ended_at": time.time(),
            "updated_at": time.time(),
            "error": "command not found",
        })
        _write_metadata(job_dir, meta)
        raise


async def run_async(spec: JobSpec) -> JobRunResult:
    meta = create_metadata(spec)
    job_dir = Path(meta["log_path"]).parent
    job_dir.mkdir(parents=True, exist_ok=True)
    _write_metadata(job_dir, meta)
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    proc = await asyncio.create_subprocess_exec(
        *spec.command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=spec.cwd,
        env=spec.env,
        start_new_session=(os.name != "nt"),
    )
    now = time.time()
    meta.update({
        "pid": proc.pid,
        "pgid": _safe_getpgid(proc.pid),
        "status": JOB_STATUS_RUNNING,
        "started_at": now,
        "updated_at": now,
    })
    _write_metadata(job_dir, meta)
    if proc.stdin is not None:
        proc.stdin.write(spec.stdin_input.encode(spec.encoding))
        await proc.stdin.drain()
        proc.stdin.close()

    pumps = [
        asyncio.create_task(_pump_async_stream(proc.stdout, Path(meta["stdout_log_path"]), Path(meta["log_path"]), stdout_parts, job_dir, spec.encoding)),
        asyncio.create_task(_pump_async_stream(proc.stderr, Path(meta["stderr_log_path"]), Path(meta["log_path"]), stderr_parts, job_dir, spec.encoding)),
    ]
    status_value = JOB_STATUS_FAILED
    try:
        try:
            returncode = await asyncio.wait_for(proc.wait(), timeout=spec.timeout)
            status_value = JOB_STATUS_SUCCEEDED if returncode == 0 else JOB_STATUS_FAILED
        except asyncio.TimeoutError:
            terminate_process_tree(proc.pid)
            returncode = await proc.wait()
            status_value = JOB_STATUS_TIMEOUT
        await asyncio.gather(*pumps, return_exceptions=True)
        error = None
        if status_value == JOB_STATUS_SUCCEEDED:
            missing_error = _expected_output_error(spec.expected_outputs, spec.cwd)
            if missing_error:
                status_value = JOB_STATUS_FAILED
                error = missing_error
        elif status_value == JOB_STATUS_FAILED:
            error = "process exited with non-zero status"
        meta.update({
            "status": status_value,
            "returncode": returncode,
            "ended_at": time.time(),
            "updated_at": time.time(),
            "last_output_at": _last_output_at(meta),
            "error": error,
        })
        _write_metadata(job_dir, meta)
        return JobRunResult(
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            returncode=returncode,
            status=status_value,
            job_id=str(meta["id"]),
            log_path=str(meta["log_path"]),
            stdout_log_path=str(meta["stdout_log_path"]),
            stderr_log_path=str(meta["stderr_log_path"]),
        )
    except Exception as exc:
        for pump in pumps:
            pump.cancel()
        meta.update({
            "status": JOB_STATUS_FAILED,
            "ended_at": time.time(),
            "updated_at": time.time(),
            "error": str(exc)[:500],
        })
        _write_metadata(job_dir, meta)
        raise
    except Exception as exc:
        meta.update({
            "status": JOB_STATUS_FAILED,
            "ended_at": time.time(),
            "updated_at": time.time(),
            "error": str(exc)[:500],
        })
        _write_metadata(job_dir, meta)
        raise


def start_background(spec: JobSpec) -> JobStatus:
    meta = create_metadata(spec)
    job_dir = Path(meta["log_path"]).parent
    job_dir.mkdir(parents=True, exist_ok=True)
    with open(meta["stdout_log_path"], "a", encoding=spec.encoding):
        pass
    with open(meta["stderr_log_path"], "a", encoding=spec.encoding):
        pass
    with open(meta["log_path"], "a", encoding=spec.encoding):
        pass
    stdout_handle = open(meta["stdout_log_path"], "a", encoding=spec.encoding)
    stderr_handle = open(meta["stderr_log_path"], "a", encoding=spec.encoding)
    try:
        proc = subprocess.Popen(
            spec.command,
            stdin=subprocess.PIPE,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            encoding=spec.encoding,
            errors="replace",
            cwd=spec.cwd,
            env=spec.env,
            start_new_session=(os.name != "nt"),
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    if proc.stdin is not None:
        proc.stdin.write(spec.stdin_input)
        proc.stdin.close()
    now = time.time()
    meta.update({
        "pid": proc.pid,
        "pgid": _safe_getpgid(proc.pid),
        "status": JOB_STATUS_RUNNING,
        "started_at": now,
        "updated_at": now,
    })
    _BACKGROUND_PROCS[proc.pid] = proc
    _write_metadata(job_dir, meta)
    return status(str(meta["id"]), cwd=spec.cwd)


def list_jobs(*, cwd: str | None = None) -> list[JobStatus | dict]:
    root = runtime_root(cwd)
    if not root.exists():
        return []
    items: list[JobStatus | dict] = []
    for meta_path in root.glob("*/meta.json"):
        try:
            items.append(status(meta_path.parent.name, cwd=cwd))
        except Exception as exc:
            items.append({"id": meta_path.parent.name, "status": "unreadable", "error": str(exc)})
    return sorted(items, key=lambda item: getattr(item, "started_at", None) or 0, reverse=True)


def status(job_id: str, *, cwd: str | None = None) -> JobStatus:
    meta = load_metadata(job_id, cwd=cwd)
    current = str(meta.get("status") or JOB_STATUS_CREATED)
    if current not in TERMINAL_STATUSES:
        current = _live_status(meta, cwd=cwd)
        meta["status"] = current
        meta["updated_at"] = time.time()
        meta["last_output_at"] = _last_output_at(meta)
        _write_metadata(Path(str(meta["log_path"])).parent, meta)
    return _status_from_meta(meta)


def load_metadata(job_id: str, *, cwd: str | None = None) -> dict:
    path = runtime_root(cwd) / job_id / "meta.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def logs(job_id: str, *, cwd: str | None = None, stream: str = "combined", tail: int | None = None) -> str:
    meta = load_metadata(job_id, cwd=cwd)
    path = _log_path_for_stream(meta, stream)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if stream == "combined" and not text:
        text = (
            Path(str(meta["stdout_log_path"])).read_text(encoding="utf-8", errors="replace")
            + Path(str(meta["stderr_log_path"])).read_text(encoding="utf-8", errors="replace")
        )
    if tail is None:
        return text
    lines = text.splitlines()
    return "\n".join(lines[-tail:]) + ("\n" if lines[-tail:] else "")


def follow_logs(job_id: str, *, cwd: str | None = None, stream: str = "combined", poll: float = 0.5) -> Iterator[str]:
    meta = load_metadata(job_id, cwd=cwd)
    path = _log_path_for_stream(meta, stream)
    position = 0
    while True:
        chunk = ""
        if path.exists():
            with path.open(encoding="utf-8", errors="replace") as handle:
                handle.seek(position)
                chunk = handle.read()
                position = handle.tell()
            if chunk:
                yield chunk
        current = status(job_id, cwd=cwd)
        if current.status in TERMINAL_STATUSES:
            if not chunk:
                break
        time.sleep(poll)


def stop(job_id: str, *, cwd: str | None = None) -> JobStatus:
    meta = load_metadata(job_id, cwd=cwd)
    pid = meta.get("pid")
    if pid and _pid_alive(int(pid)):
        terminate_process_tree(int(pid))
        _wait_dead(int(pid), timeout=2.0)
        proc = _BACKGROUND_PROCS.pop(int(pid), None)
        if proc is not None:
            try:
                proc.wait(timeout=0)
            except Exception:
                pass
    now = time.time()
    meta.update({
        "status": JOB_STATUS_KILLED,
        "ended_at": meta.get("ended_at") or now,
        "updated_at": now,
    })
    _write_metadata(Path(str(meta["log_path"])).parent, meta)
    return _status_from_meta(meta)


def cleanup(*, cwd: str | None = None, older_than_days: float = 7, status_filter: str | None = None) -> int:
    root = runtime_root(cwd)
    if not root.exists():
        return 0
    cutoff = time.time() - older_than_days * 86400
    removed = 0
    for meta_path in root.glob("*/meta.json"):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status_filter and meta.get("status") != status_filter:
            continue
        timestamp = meta.get("ended_at") or meta.get("started_at") or meta.get("created_at") or 0
        if float(timestamp) > cutoff:
            continue
        _remove_tree(meta_path.parent)
        removed += 1
    return removed


def terminate_process_tree(pid: int) -> None:
    if os.name != "nt":
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            return
        except ProcessLookupError:
            return
        except Exception:
            pass
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def _wait_dead(pid: int, *, timeout: float) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.05)
    if os.name != "nt":
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except Exception:
            pass
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def _write_metadata(job_dir: Path, meta: dict) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    tmp = job_dir / "meta.json.tmp"
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(job_dir / "meta.json")


def _pump_stream(stream, path: Path, combined_path: Path, parts: list[str], job_dir: Path) -> None:
    if stream is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="replace") as out, combined_path.open("a", encoding="utf-8", errors="replace") as combined:
        for line in iter(stream.readline, ""):
            parts.append(line)
            out.write(line)
            out.flush()
            combined.write(line)
            combined.flush()
            _touch_last_output(job_dir)
    stream.close()


async def _pump_async_stream(stream, path: Path, combined_path: Path, parts: list[str], job_dir: Path, encoding: str) -> None:
    if stream is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding=encoding, errors="replace") as out, combined_path.open("a", encoding=encoding, errors="replace") as combined:
        while True:
            raw = await stream.readline()
            if not raw:
                break
            text = raw.decode(encoding, errors="replace")
            parts.append(text)
            out.write(text)
            out.flush()
            combined.write(text)
            combined.flush()
            _touch_last_output(job_dir)


def _touch_last_output(job_dir: Path) -> None:
    marker = job_dir / ".last_output"
    marker.write_text(str(time.time()), encoding="utf-8")


def _last_output_at(meta: dict) -> float | None:
    candidates: list[float] = []
    for key in ("stdout_log_path", "stderr_log_path", "log_path"):
        path = Path(str(meta.get(key) or ""))
        if path.exists() and path.stat().st_size > 0:
            candidates.append(path.stat().st_mtime)
    marker = Path(str(meta.get("log_path") or "")).parent / ".last_output"
    if marker.exists():
        try:
            candidates.append(float(marker.read_text(encoding="utf-8")))
        except ValueError:
            pass
    for expected in meta.get("expected_outputs") or []:
        path = Path(expected)
        if not path.is_absolute():
            base = Path(str(meta.get("cwd") or Path.cwd()))
            path = base / path
        if path.exists():
            candidates.append(path.stat().st_mtime)
    return max(candidates) if candidates else None


def _live_status(meta: dict, *, cwd: str | None) -> str:
    pid = meta.get("pid")
    if pid and int(pid) in _BACKGROUND_PROCS:
        proc = _BACKGROUND_PROCS[int(pid)]
        returncode = proc.poll()
        if returncode is not None:
            meta["returncode"] = returncode
            meta["ended_at"] = time.time()
            _BACKGROUND_PROCS.pop(int(pid), None)
            if returncode != 0:
                meta["error"] = "process exited with non-zero status"
                return JOB_STATUS_FAILED
            error = _expected_output_error(meta.get("expected_outputs") or [], meta.get("cwd") or cwd)
            if error:
                meta["error"] = error
                return JOB_STATUS_FAILED
            return JOB_STATUS_SUCCEEDED
    if not pid or not _pid_alive(int(pid)):
        return JOB_STATUS_SUCCEEDED if not _expected_output_error(meta.get("expected_outputs") or [], meta.get("cwd") or cwd) else JOB_STATUS_FAILED
    started_at = meta.get("started_at")
    timeout = meta.get("timeout")
    now = time.time()
    if started_at and timeout and now - float(started_at) >= float(timeout):
        terminate_process_tree(int(pid))
        return JOB_STATUS_TIMEOUT
    stall_timeout = meta.get("stall_timeout")
    last_output = _last_output_at(meta) or started_at
    if stall_timeout and last_output and now - float(last_output) >= float(stall_timeout):
        return JOB_STATUS_STALLED
    return JOB_STATUS_RUNNING


def _expected_output_error(expected_outputs: list[str], cwd: str | None) -> str | None:
    base = Path(cwd) if cwd else Path.cwd()
    for name in expected_outputs:
        path = Path(name)
        if not path.is_absolute():
            path = base / path
        if not path.exists():
            return f"expected output '{name}' was not created at {path}"
        try:
            if not path.read_text(encoding="utf-8", errors="replace").strip():
                return f"expected output '{name}' is empty at {path}"
        except OSError as exc:
            return f"expected output '{name}' could not be read: {exc}"
    return None


def _status_from_meta(meta: dict) -> JobStatus:
    return JobStatus(
        job_id=str(meta.get("id")),
        status=str(meta.get("status")),
        pid=int(meta["pid"]) if meta.get("pid") is not None else None,
        returncode=int(meta["returncode"]) if meta.get("returncode") is not None else None,
        started_at=float(meta["started_at"]) if meta.get("started_at") is not None else None,
        ended_at=float(meta["ended_at"]) if meta.get("ended_at") is not None else None,
        updated_at=float(meta.get("updated_at") or time.time()),
        target=meta.get("target"),
        model=meta.get("model"),
        role=meta.get("role"),
        change=meta.get("change"),
        task=meta.get("task"),
        log_path=str(meta.get("log_path")),
        stdout_log_path=str(meta.get("stdout_log_path")),
        stderr_log_path=str(meta.get("stderr_log_path")),
        expected_outputs=list(meta.get("expected_outputs") or []),
        error=meta.get("error"),
        last_output_at=meta.get("last_output_at"),
    )


def _log_path_for_stream(meta: dict, stream: str) -> Path:
    if stream == "stdout":
        return Path(str(meta["stdout_log_path"]))
    if stream == "stderr":
        return Path(str(meta["stderr_log_path"]))
    if stream == "combined":
        return Path(str(meta["log_path"]))
    raise ValueError("stream must be stdout, stderr, or combined")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _safe_getpgid(pid: int) -> int | None:
    if os.name == "nt":
        return None
    try:
        return os.getpgid(pid)
    except Exception:
        return None


def _stall_timeout(spec: JobSpec) -> float:
    if spec.stall_timeout is not None:
        return spec.stall_timeout
    raw = os.getenv("TASK_RELAY_STALL_TIMEOUT")
    if raw:
        try:
            return float(raw)
        except ValueError:
            return DEFAULT_STALL_TIMEOUT
    return DEFAULT_STALL_TIMEOUT


def _remove_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            child.rmdir()
    path.rmdir()
