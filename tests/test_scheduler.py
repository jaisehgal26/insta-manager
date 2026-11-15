from datetime import datetime, timedelta, timezone
from pathlib import Path

from insta_manager.scheduler.db import SchedulerStore


def test_scheduler_add_and_due(tmp_path: Path) -> None:
    db = tmp_path / "sched.sqlite"
    store = SchedulerStore(db)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    j1 = store.add_job(account_alias="a1", run_at=past, job_type="image", payload={"image_url": "https://x"})
    store.add_job(account_alias="a1", run_at=future, job_type="image", payload={})
    due = store.due_jobs()
    assert len(due) == 1
    assert due[0].id == j1.id
    store.update_status(j1.id, status="done", result={"media_id": "m"})
    assert store.list_jobs(status="done")[0].result["media_id"] == "m"
