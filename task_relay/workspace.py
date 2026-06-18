import os
import shutil
import uuid
from pathlib import Path


KEEP_IO_ENV = "TASK_RELAY_KEEP_IO"


def create_workspace(base_dir: str | None) -> tuple[str, Path]:
    job_id = uuid.uuid4().hex[:8]
    base = Path(base_dir) if base_dir else Path.cwd()
    workspace = base / ".task_relay" / job_id
    workspace.mkdir(parents=True, exist_ok=True)
    return job_id, workspace


def cleanup_workspace(workspace: Path) -> None:
    if os.getenv(KEEP_IO_ENV, "0").strip() == "1":
        return
    shutil.rmtree(workspace, ignore_errors=True)
