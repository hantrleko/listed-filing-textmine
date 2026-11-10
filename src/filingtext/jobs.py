"""后台抓取。任务状态写在磁盘上，页面刷新后还能看到。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from filingtext.config import ROOT, WORKSPACE_DIR

JOB_DIR = WORKSPACE_DIR / "jobs"


def create_job(spec: dict) -> str:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    payload = {
        "id": job_id,
        "status": "queued",
        "spec": {key: value for key, value in spec.items() if key != "edgar_contact"},
        "summary": {},
        "error": "",
    }
    _write(job_id, payload)
    return job_id


def spawn(job_id: str, edgar_contact: str = "") -> None:
    env = os.environ.copy()
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    if edgar_contact.strip():
        env["EDGAR_USER_AGENT"] = f"filingtext-research {edgar_contact.strip()}"
    log_path = JOB_DIR / f"{job_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("a", encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    subprocess.Popen(
        [sys.executable, "-m", "filingtext.jobs", "run", job_id],
        cwd=str(ROOT),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        creationflags=flags,
    )


def execute(job_id: str) -> dict:
    from filingtext.workspace import build_from_codes

    job = read_job(job_id)
    job["status"] = "running"
    _write(job_id, job)
    spec = job["spec"]

    def _on_event(event: dict) -> None:
        with (JOB_DIR / f"{job_id}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    try:
        result = build_from_codes(
            spec["market"],
            spec["codes"],
            int(spec["start"]),
            int(spec["end"]),
            edgar_contact=_contact_from_env(),
            forms=spec.get("forms") or None,
            confirm_large=bool(spec.get("confirm_large")),
            on_event=_on_event,
        )
    except Exception as exc:
        job = read_job(job_id)
        job["status"] = "failed"
        job["error"] = str(exc)
        _write(job_id, job)
        raise
    summary = result.get("summary") or {}
    job = read_job(job_id)
    job["status"] = "done"
    job["summary"] = {
        "downloaded": len(result.get("downloaded") or []),
        "n_found": summary.get("n_found"),
        "n_firms": summary.get("n_firms"),
    }
    _write(job_id, job)
    return job


def read_job(job_id: str) -> dict:
    path = JOB_DIR / f"{job_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def read_events(job_id: str) -> list[dict]:
    path = JOB_DIR / f"{job_id}.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def latest_job() -> dict | None:
    if not JOB_DIR.exists():
        return None
    files = sorted(JOB_DIR.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _contact_from_env() -> str:
    raw = os.environ.get("EDGAR_USER_AGENT") or ""
    parts = raw.split()
    return parts[-1] if parts else ""


def _write(job_id: str, payload: dict) -> None:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    (JOB_DIR / f"{job_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "run":
        execute(sys.argv[2])
        return
    raise SystemExit("用法：python -m filingtext.jobs run <job_id>")


if __name__ == "__main__":
    main()
