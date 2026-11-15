from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from insta_manager import __version__
from insta_manager.api import comments, insights, publishing
from insta_manager.api.client import GraphAPIError, GraphClient
from insta_manager.auth import (
    check_and_refresh_accounts,
    run_local_oauth,
    store_pages_from_user_token,
)
from insta_manager.config import Settings, get_settings
from insta_manager.output import emit, error_exit
from insta_manager.registry import AccountRecord, AccountRegistry
from insta_manager.scheduler.db import SchedulerStore
from insta_manager.scheduler.runner import daemon_loop, run_due
from insta_manager.uploaders import get_uploader

app = typer.Typer(
    name="insta-manager",
    help="Manage and publish to multiple Instagram Business accounts via the official Graph API.",
    no_args_is_help=True,
)
account_app = typer.Typer(help="Account registry")
auth_app = typer.Typer(help="Authentication and tokens")
publish_app = typer.Typer(help="Publishing")
comment_app = typer.Typer(help="Comment management")
insights_app = typer.Typer(help="Insights")
schedule_app = typer.Typer(help="Local scheduler (no native IG scheduling)")

app.add_typer(account_app, name="account")
app.add_typer(auth_app, name="auth")
app.add_typer(publish_app, name="publish")
app.add_typer(comment_app, name="comment")
app.add_typer(insights_app, name="insights")
app.add_typer(schedule_app, name="schedule")


def _settings() -> Settings:
    s = get_settings()
    s.ensure_home()
    return s


def _registry() -> AccountRegistry:
    s = _settings()
    return AccountRegistry(s.registry_path())


def _resolve_account(alias: str) -> AccountRecord:
    reg = _registry()
    acct = reg.get(alias)
    if not acct:
        error_exit(f"Unknown account '{alias}'. Use: insta-manager account list")
    return acct


def _client_for(alias: str) -> tuple[AccountRecord, GraphClient, Settings]:
    s = _settings()
    acct = _resolve_account(alias)
    client = GraphClient(api_version=s.insta_manager_api_version, access_token=acct.access_token)
    return acct, client, s


def _json_flag(json_output: bool) -> bool:
    return json_output


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version"),
    ] = None,
) -> None:
    pass


@account_app.command("list")
def account_list(
    json_output: Annotated[bool, typer.Option("--json", help="JSON output")] = False,
) -> None:
    reg = _registry()
    emit({"accounts": reg.redacted_list()}, json_mode=json_output)


@account_app.command("add")
def account_add(
    alias: Annotated[str, typer.Option("--alias", help="Unique account name")],
    ig_user_id: Annotated[str, typer.Option("--ig-user-id")],
    page_id: Annotated[str, typer.Option("--page-id")],
    token: Annotated[str, typer.Option("--token", help="Long-lived Page access token")],
    page_name: Annotated[Optional[str], typer.Option("--page-name")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    reg = _registry()
    if reg.get(alias):
        error_exit(f"Alias already exists: {alias}", json_mode=json_output)
    reg.upsert(
        AccountRecord(
            alias=alias,
            ig_user_id=ig_user_id,
            page_id=page_id,
            page_name=page_name,
            access_token=token,
        )
    )
    emit({"ok": True, "alias": alias}, json_mode=json_output)


@account_app.command("remove")
def account_remove(
    alias: Annotated[str, typer.Option("--alias")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    reg = _registry()
    if not reg.remove(alias):
        error_exit(f"Unknown alias: {alias}", json_mode=json_output)
    emit({"ok": True, "removed": alias}, json_mode=json_output)


@auth_app.command("exchange")
def auth_exchange(
    token: Annotated[str, typer.Option("--token", help="Short-lived user access token")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    s = _settings()
    if not s.meta_app_id or not s.meta_app_secret:
        error_exit("Set META_APP_ID and META_APP_SECRET in .env", json_mode=json_output)
    if dry_run:
        emit({"dry_run": True, "action": "exchange_and_discover_pages"}, json_mode=json_output)
        return
    client = GraphClient(api_version=s.insta_manager_api_version)
    stored = store_pages_from_user_token(
        _registry(),
        client,
        app_id=s.meta_app_id,
        app_secret=s.meta_app_secret,
        user_token=token,
    )
    emit(
        {
            "ok": True,
            "stored": [{"alias": a.alias, "ig_user_id": a.ig_user_id} for a in stored],
        },
        json_mode=json_output,
    )


@auth_app.command("login")
def auth_login(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    s = _settings()
    if not s.meta_app_id or not s.meta_app_secret:
        error_exit("Set META_APP_ID and META_APP_SECRET in .env", json_mode=json_output)
    if dry_run:
        emit({"dry_run": True, "redirect": s.insta_manager_oauth_redirect_uri}, json_mode=json_output)
        return
    short = run_local_oauth(
        app_id=s.meta_app_id,
        app_secret=s.meta_app_secret,
        redirect_uri=s.insta_manager_oauth_redirect_uri,
        api_version=s.insta_manager_api_version,
    )
    client = GraphClient(api_version=s.insta_manager_api_version)
    stored = store_pages_from_user_token(
        _registry(),
        client,
        app_id=s.meta_app_id,
        app_secret=s.meta_app_secret,
        user_token=short,
    )
    emit(
        {"ok": True, "stored": [{"alias": a.alias, "ig_user_id": a.ig_user_id} for a in stored]},
        json_mode=json_output,
    )


@auth_app.command("check-tokens")
def auth_check_tokens(
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    s = _settings()
    if not s.meta_app_id or not s.meta_app_secret:
        error_exit("Set META_APP_ID and META_APP_SECRET in .env", json_mode=json_output)
    report = check_and_refresh_accounts(
        _registry(),
        app_id=s.meta_app_id,
        app_secret=s.meta_app_secret,
        api_version=s.insta_manager_api_version,
    )
    emit({"accounts": report}, json_mode=json_output)


def _publish_preflight(client: GraphClient, ig_user_id: str, *, dry_run: bool, json_output: bool) -> None:
    if dry_run:
        return
    limit = publishing.get_content_publishing_limit(client, ig_user_id)
    try:
        publishing.assert_can_publish(limit)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=limit)


@publish_app.command("image")
def publish_image(
    account: Annotated[str, typer.Option("--account")],
    image_url: Annotated[Optional[str], typer.Option("--image-url")] = None,
    image_file: Annotated[Optional[Path], typer.Option("--image-file", exists=True)] = None,
    caption: Annotated[Optional[str], typer.Option("--caption")] = None,
    alt_text: Annotated[Optional[str], typer.Option("--alt-text")] = None,
    location_id: Annotated[Optional[str], typer.Option("--location-id")] = None,
    first_comment: Annotated[Optional[str], typer.Option("--first-comment")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    acct, client, s = _client_for(account)
    _publish_preflight(client, acct.ig_user_id, dry_run=dry_run, json_output=json_output)
    url = image_url
    if not url and image_file:
        if dry_run:
            url = f"(would-upload:{image_file})"
        else:
            url = get_uploader(s).upload(image_file)
    if not url or url.startswith("(would-upload"):
        if dry_run and image_file:
            emit(
                {
                    "dry_run": True,
                    "type": "image",
                    "account": account,
                    "image_file": str(image_file),
                    "caption": caption,
                },
                json_mode=json_output,
            )
            return
        error_exit("Provide --image-url or --image-file", json_mode=json_output)
    if dry_run:
        emit({"dry_run": True, "type": "image", "image_url": url, "caption": caption}, json_mode=json_output)
        return
    try:
        _, mid = publishing.publish_single_image(
            client,
            acct.ig_user_id,
            image_url=url,
            caption=caption,
            alt_text=alt_text,
            location_id=location_id,
        )
        if first_comment:
            comments.post_comment(client, mid, first_comment)
        emit({"ok": True, "media_id": mid}, json_mode=json_output)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=e.body)


@publish_app.command("reel")
def publish_reel_cmd(
    account: Annotated[str, typer.Option("--account")],
    video_file: Annotated[Path, typer.Option("--video-file", exists=True)],
    caption: Annotated[Optional[str], typer.Option("--caption")] = None,
    share_to_feed: Annotated[bool, typer.Option("--share-to-feed/--no-share-to-feed")] = True,
    cover_url: Annotated[Optional[str], typer.Option("--cover-url")] = None,
    thumb_offset: Annotated[Optional[int], typer.Option("--thumb-offset")] = None,
    first_comment: Annotated[Optional[str], typer.Option("--first-comment")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    acct, client, _s = _client_for(account)
    _publish_preflight(client, acct.ig_user_id, dry_run=dry_run, json_output=json_output)
    if dry_run:
        emit(
            {"dry_run": True, "type": "reel", "video_file": str(video_file), "share_to_feed": share_to_feed},
            json_mode=json_output,
        )
        return
    try:
        _, mid = publishing.publish_reel(
            client,
            acct.ig_user_id,
            video_path=video_file,
            caption=caption,
            share_to_feed=share_to_feed,
            cover_url=cover_url,
            thumb_offset=thumb_offset,
        )
        if first_comment:
            comments.post_comment(client, mid, first_comment)
        emit({"ok": True, "media_id": mid}, json_mode=json_output)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=e.body)


@publish_app.command("story")
def publish_story_cmd(
    account: Annotated[str, typer.Option("--account")],
    image_url: Annotated[Optional[str], typer.Option("--image-url")] = None,
    image_file: Annotated[Optional[Path], typer.Option("--image-file", exists=True)] = None,
    video_file: Annotated[Optional[Path], typer.Option("--video-file", exists=True)] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    acct, client, s = _client_for(account)
    _publish_preflight(client, acct.ig_user_id, dry_run=dry_run, json_output=json_output)
    if dry_run:
        emit(
            {
                "dry_run": True,
                "type": "story",
                "image_url": image_url,
                "image_file": str(image_file) if image_file else None,
                "video_file": str(video_file) if video_file else None,
            },
            json_mode=json_output,
        )
        return
    try:
        if video_file:
            _, mid = publishing.publish_story_video(client, acct.ig_user_id, video_path=video_file)
        elif image_url or image_file:
            url = image_url or get_uploader(s).upload(image_file)  # type: ignore[arg-type]
            _, mid = publishing.publish_story_image(client, acct.ig_user_id, image_url=url)
        else:
            error_exit("Provide --video-file or --image-url/--image-file", json_mode=json_output)
        emit({"ok": True, "media_id": mid}, json_mode=json_output)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=e.body)


@publish_app.command("carousel")
def publish_carousel_cmd(
    account: Annotated[str, typer.Option("--account")],
    items: Annotated[
        Optional[str],
        typer.Option("--items", help="Comma-separated paths (.jpg/.png/.mp4). 2-10 items."),
    ] = None,
    caption: Annotated[Optional[str], typer.Option("--caption")] = None,
    location_id: Annotated[Optional[str], typer.Option("--location-id")] = None,
    first_comment: Annotated[Optional[str], typer.Option("--first-comment")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    acct, client, s = _client_for(account)
    if not items:
        error_exit("--items required (comma-separated local paths)", json_mode=json_output)
    paths = [Path(p.strip()) for p in items.split(",") if p.strip()]
    if len(paths) < 2 or len(paths) > 10:
        error_exit("Carousel must have 2–10 items", json_mode=json_output)
    for p in paths:
        if not p.exists():
            error_exit(f"Missing file: {p}", json_mode=json_output)
    _publish_preflight(client, acct.ig_user_id, dry_run=dry_run, json_output=json_output)
    if dry_run:
        emit({"dry_run": True, "type": "carousel", "items": [str(p) for p in paths]}, json_mode=json_output)
        return
    children: list[str] = []
    try:
        for p in paths:
            ext = p.suffix.lower()
            if ext in {".mp4", ".mov", ".m4v"}:
                children.append(publishing.create_carousel_child_video(client, acct.ig_user_id, video_path=p))
            elif ext in {".jpg", ".jpeg", ".png", ".webp"}:
                url = get_uploader(s).upload(p)
                children.append(publishing.create_carousel_child_image(client, acct.ig_user_id, image_url=url))
            else:
                error_exit(f"Unsupported carousel item: {p}", json_mode=json_output)
        _, mid = publishing.publish_carousel(
            client, acct.ig_user_id, children_ids=children, caption=caption, location_id=location_id
        )
        if first_comment:
            comments.post_comment(client, mid, first_comment)
        emit({"ok": True, "media_id": mid, "children": children}, json_mode=json_output)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=e.body)


@publish_app.command("container-status")
def container_status(
    account: Annotated[str, typer.Option("--account")],
    container_id: Annotated[str, typer.Option("--container-id")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    emit(publishing.get_container_status(client, container_id), json_mode=json_output)


@publish_app.command("limit")
def publish_limit(
    account: Annotated[str, typer.Option("--account")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    acct, client, _s = _client_for(account)
    emit(publishing.get_content_publishing_limit(client, acct.ig_user_id), json_mode=json_output)


@publish_app.command("delete")
def publish_delete(
    account: Annotated[str, typer.Option("--account")],
    media_id: Annotated[str, typer.Option("--media-id")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    if dry_run:
        emit({"dry_run": True, "delete": media_id}, json_mode=json_output)
        return
    try:
        emit(publishing.delete_media(client, media_id), json_mode=json_output)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=e.body)


@comment_app.command("list")
def comment_list(
    account: Annotated[str, typer.Option("--account")],
    media_id: Annotated[str, typer.Option("--media-id")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    emit(comments.list_comments(client, media_id), json_mode=json_output)


@comment_app.command("add")
def comment_add(
    account: Annotated[str, typer.Option("--account")],
    media_id: Annotated[str, typer.Option("--media-id")],
    message: Annotated[str, typer.Option("--message")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    if dry_run:
        emit({"dry_run": True, "comment": message}, json_mode=json_output)
        return
    emit(comments.post_comment(client, media_id, message), json_mode=json_output)


@comment_app.command("reply")
def comment_reply(
    account: Annotated[str, typer.Option("--account")],
    comment_id: Annotated[str, typer.Option("--comment-id")],
    message: Annotated[str, typer.Option("--message")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    if dry_run:
        emit({"dry_run": True, "reply": message}, json_mode=json_output)
        return
    emit(comments.reply_to_comment(client, comment_id, message), json_mode=json_output)


@comment_app.command("hide")
def comment_hide(
    account: Annotated[str, typer.Option("--account")],
    comment_id: Annotated[str, typer.Option("--comment-id")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    if dry_run:
        emit({"dry_run": True, "hide": comment_id}, json_mode=json_output)
        return
    emit(comments.hide_comment(client, comment_id, hide=True), json_mode=json_output)


@comment_app.command("unhide")
def comment_unhide(
    account: Annotated[str, typer.Option("--account")],
    comment_id: Annotated[str, typer.Option("--comment-id")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    if dry_run:
        emit({"dry_run": True, "unhide": comment_id}, json_mode=json_output)
        return
    emit(comments.hide_comment(client, comment_id, hide=False), json_mode=json_output)


@comment_app.command("delete")
def comment_delete(
    account: Annotated[str, typer.Option("--account")],
    comment_id: Annotated[str, typer.Option("--comment-id")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    if dry_run:
        emit({"dry_run": True, "delete_comment": comment_id}, json_mode=json_output)
        return
    emit(comments.delete_comment(client, comment_id), json_mode=json_output)


@comment_app.command("toggle")
def comment_toggle(
    account: Annotated[str, typer.Option("--account")],
    media_id: Annotated[str, typer.Option("--media-id")],
    enabled: Annotated[bool, typer.Option("--enabled/--disabled")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    if dry_run:
        emit({"dry_run": True, "comment_enabled": enabled}, json_mode=json_output)
        return
    emit(comments.set_comments_enabled(client, media_id, enabled=enabled), json_mode=json_output)


@insights_app.command("account")
def insights_account(
    account: Annotated[str, typer.Option("--account")],
    metrics: Annotated[Optional[str], typer.Option("--metrics", help="Comma-separated")] = None,
    period: Annotated[str, typer.Option("--period")] = "day",
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    acct, client, _s = _client_for(account)
    mlist = [m.strip() for m in metrics.split(",")] if metrics else None
    try:
        emit(insights.account_insights(client, acct.ig_user_id, metrics=mlist, period=period), json_mode=json_output)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=e.body)


@insights_app.command("media")
def insights_media(
    account: Annotated[str, typer.Option("--account")],
    media_id: Annotated[str, typer.Option("--media-id")],
    metrics: Annotated[Optional[str], typer.Option("--metrics")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    _acct, client, _s = _client_for(account)
    mlist = [m.strip() for m in metrics.split(",")] if metrics else None
    try:
        emit(insights.media_insights(client, media_id, metrics=mlist), json_mode=json_output)
    except GraphAPIError as e:
        error_exit(str(e), json_mode=json_output, detail=e.body)


@schedule_app.command("add")
def schedule_add(
    account: Annotated[str, typer.Option("--account")],
    run_at: Annotated[str, typer.Option("--run-at", help="ISO8601 datetime (UTC recommended)")],
    job_type: Annotated[str, typer.Option("--type", help="image | reel")],
    payload_json: Annotated[str, typer.Option("--payload", help="JSON object with paths/urls/caption")],
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    s = _settings()
    if not _registry().get(account):
        error_exit(f"Unknown account: {account}", json_mode=json_output)
    try:
        when = datetime.fromisoformat(run_at.replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
    except ValueError as e:
        error_exit(f"Invalid --run-at: {e}", json_mode=json_output)
    payload = json.loads(payload_json)
    if dry_run:
        emit({"dry_run": True, "would_schedule": {"account": account, "run_at": run_at, "type": job_type}}, json_mode=json_output)
        return
    store = SchedulerStore(s.scheduler_db_path())
    job = store.add_job(account_alias=account, run_at=when, job_type=job_type, payload=payload)
    emit({"ok": True, "job": job.__dict__}, json_mode=json_output)


@schedule_app.command("list")
def schedule_list(
    account: Annotated[Optional[str], typer.Option("--account")] = None,
    status: Annotated[Optional[str], typer.Option("--status")] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    s = _settings()
    store = SchedulerStore(s.scheduler_db_path())
    jobs = store.list_jobs(status=status, account=account)
    emit({"jobs": [j.__dict__ for j in jobs]}, json_mode=json_output)


@schedule_app.command("run-due")
def schedule_run_due(
    json_output: Annotated[bool, typer.Option("--json")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    s = _settings()
    store = SchedulerStore(s.scheduler_db_path())
    results = run_due(store, registry=_registry(), settings=s, dry_run=dry_run)
    emit({"results": results}, json_mode=json_output)


@schedule_app.command("daemon")
def schedule_daemon(
    interval: Annotated[float, typer.Option("--interval", help="Poll seconds")] = 30.0,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
) -> None:
    s = _settings()
    store = SchedulerStore(s.scheduler_db_path())
    typer.echo(f"Scheduler daemon (interval={interval}s). Ctrl+C to stop.")
    try:
        daemon_loop(store, registry=_registry(), settings=s, interval=interval, dry_run=dry_run)
    except KeyboardInterrupt:
        typer.echo("Stopped.")


if __name__ == "__main__":
    app()
