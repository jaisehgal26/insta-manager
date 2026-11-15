from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from insta_manager.api.client import GraphClient
from insta_manager.api import publishing as pub
from insta_manager.registry import AccountRegistry
from insta_manager.scheduler.db import ScheduledJob, SchedulerStore
from insta_manager.uploaders import get_uploader
from insta_manager.config import Settings


def execute_job(
    job: ScheduledJob,
    *,
    registry: AccountRegistry,
    settings: Settings,
    dry_run: bool = False,
) -> dict[str, Any]:
    acct = registry.get(job.account_alias)
    if not acct:
        raise RuntimeError(f"Unknown account {job.account_alias}")
    if dry_run:
        return {"dry_run": True, "job_id": job.id, "job_type": job.job_type}

    client = GraphClient(api_version=settings.insta_manager_api_version, access_token=acct.access_token)
    limit = pub.get_content_publishing_limit(client, acct.ig_user_id)
    pub.assert_can_publish(limit)

    payload = job.payload
    jt = job.job_type
    if jt == "image":
        image_url = payload.get("image_url")
        if not image_url and payload.get("image_path"):
            image_url = get_uploader(settings).upload(Path(payload["image_path"]))
        if not image_url:
            raise RuntimeError("image_url or image_path required")
        _, mid = pub.publish_single_image(
            client,
            acct.ig_user_id,
            image_url=image_url,
            caption=payload.get("caption"),
            alt_text=payload.get("alt_text"),
        )
        return {"media_id": mid}
    if jt == "reel":
        video_path = Path(payload["video_path"])
        _, mid = pub.publish_reel(
            client,
            acct.ig_user_id,
            video_path=video_path,
            caption=payload.get("caption"),
            share_to_feed=payload.get("share_to_feed", True),
            cover_url=payload.get("cover_url"),
            thumb_offset=payload.get("thumb_offset"),
        )
        return {"media_id": mid}
    raise RuntimeError(f"Unsupported scheduled job type: {jt}")


def run_due(
    store: SchedulerStore,
    *,
    registry: AccountRegistry,
    settings: Settings,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for job in store.due_jobs():
        store.update_status(job.id, status="running")
        try:
            out = execute_job(job, registry=registry, settings=settings, dry_run=dry_run)
            store.update_status(job.id, status="done", result=out)
            results.append({"id": job.id, "ok": True, "result": out})
        except Exception as e:
            store.update_status(job.id, status="failed", error=str(e))
            results.append({"id": job.id, "ok": False, "error": str(e)})
    return results


def daemon_loop(
    store: SchedulerStore,
    *,
    registry: AccountRegistry,
    settings: Settings,
    interval: float = 30.0,
    dry_run: bool = False,
    stop_after: Callable[[], bool] | None = None,
) -> None:
    while True:
        if stop_after and stop_after():
            break
        run_due(store, registry=registry, settings=settings, dry_run=dry_run)
        time.sleep(interval)
