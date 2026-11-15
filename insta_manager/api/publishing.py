from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

from insta_manager.api.client import GraphAPIError, GraphClient

MediaType = Literal["IMAGE", "VIDEO", "REELS", "STORIES", "CAROUSEL"]

CONTAINER_TERMINAL = {"FINISHED", "ERROR", "EXPIRED"}


def get_content_publishing_limit(client: GraphClient, ig_user_id: str) -> dict[str, Any]:
    return client.get(
        f"{ig_user_id}/content_publishing_limit",
        params={"fields": "quota_usage,config"},
    )


def assert_can_publish(limit_response: dict[str, Any]) -> None:
    data = limit_response.get("data", [])
    if not data:
        return
    usage = data[0].get("quota_usage", 0)
    config = data[0].get("config", {})
    quota_total = config.get("quota_total", 100)
    if usage >= quota_total:
        raise GraphAPIError(
            f"Content publishing limit exhausted ({usage}/{quota_total}). Try again later."
        )


def create_media_container(client: GraphClient, ig_user_id: str, params: dict[str, Any]) -> str:
    resp = client.post(f"{ig_user_id}/media", data=params)
    creation_id = resp.get("id")
    if not creation_id:
        raise GraphAPIError("No container id returned from media create", body=resp)
    return str(creation_id)


def publish_container(client: GraphClient, ig_user_id: str, creation_id: str) -> str:
    resp = client.post(
        f"{ig_user_id}/media_publish",
        data={"creation_id": creation_id},
    )
    media_id = resp.get("id")
    if not media_id:
        raise GraphAPIError("No media id returned from publish", body=resp)
    return str(media_id)


def get_container_status(client: GraphClient, container_id: str) -> dict[str, Any]:
    return client.get(container_id, params={"fields": "status_code,status"})


def wait_for_container(
    client: GraphClient,
    container_id: str,
    *,
    poll_interval: float = 2.0,
    timeout: float = 600.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = get_container_status(client, container_id)
        code = last.get("status_code")
        if code in CONTAINER_TERMINAL:
            if code == "ERROR":
                raise GraphAPIError(f"Container failed: {last}")
            if code == "EXPIRED":
                raise GraphAPIError(f"Container expired: {last}")
            return last
        time.sleep(poll_interval)
    raise GraphAPIError(f"Timed out waiting for container {container_id}", body=last)


def init_resumable_upload(client: GraphClient, ig_user_id: str, *, media_type: str = "VIDEO") -> str:
    resp = client.post(
        f"{ig_user_id}/media",
        data={
            "upload_type": "resumable",
            "media_type": media_type,
        },
    )
    upload_id = resp.get("id")
    if not upload_id:
        raise GraphAPIError("Resumable session id missing", body=resp)
    return str(upload_id)


def upload_video_resumable(
    client: GraphClient,
    session_id: str,
    video_path: Path,
    *,
    content_type: str = "video/mp4",
) -> dict[str, Any]:
    data = video_path.read_bytes()
    return client.rupload(session_id, file_bytes=data, file_size=len(data), content_type=content_type)


def build_user_tags_param(tags: list[dict[str, Any]] | None) -> str | None:
    if not tags:
        return None
    return json.dumps(tags)


def publish_single_image(
    client: GraphClient,
    ig_user_id: str,
    *,
    image_url: str,
    caption: str | None = None,
    alt_text: str | None = None,
    location_id: str | None = None,
    user_tags: list[dict[str, Any]] | None = None,
    collaborators: list[str] | None = None,
) -> tuple[str, str]:
    params: dict[str, Any] = {"image_url": image_url}
    if caption:
        params["caption"] = caption
    if alt_text:
        params["alt_text"] = alt_text
    if location_id:
        params["location_id"] = location_id
    tags = build_user_tags_param(user_tags)
    if tags:
        params["user_tags"] = tags
    if collaborators:
        params["collaborators"] = json.dumps([{"username": c} for c in collaborators])
    cid = create_media_container(client, ig_user_id, params)
    wait_for_container(client, cid)
    mid = publish_container(client, ig_user_id, cid)
    return cid, mid


def publish_story_image(
    client: GraphClient,
    ig_user_id: str,
    *,
    image_url: str,
) -> tuple[str, str]:
    params = {"image_url": image_url, "media_type": "STORIES"}
    cid = create_media_container(client, ig_user_id, params)
    wait_for_container(client, cid)
    mid = publish_container(client, ig_user_id, cid)
    return cid, mid


def publish_story_video(
    client: GraphClient,
    ig_user_id: str,
    *,
    video_path: Path,
) -> tuple[str, str]:
    session = init_resumable_upload(client, ig_user_id, media_type="STORIES")
    upload_video_resumable(client, session, video_path)
    params = {"video_id": session, "media_type": "STORIES"}
    cid = create_media_container(client, ig_user_id, params)
    wait_for_container(client, cid, timeout=900)
    mid = publish_container(client, ig_user_id, cid)
    return cid, mid


def publish_reel(
    client: GraphClient,
    ig_user_id: str,
    *,
    video_path: Path,
    caption: str | None = None,
    share_to_feed: bool = True,
    cover_url: str | None = None,
    thumb_offset: int | None = None,
    location_id: str | None = None,
    collaborators: list[str] | None = None,
) -> tuple[str, str]:
    session = init_resumable_upload(client, ig_user_id, media_type="REELS")
    upload_video_resumable(client, session, video_path)
    params: dict[str, Any] = {
        "video_id": session,
        "media_type": "REELS",
        "share_to_feed": "true" if share_to_feed else "false",
    }
    if caption:
        params["caption"] = caption
    if cover_url:
        params["cover_url"] = cover_url
    if thumb_offset is not None:
        params["thumb_offset"] = str(thumb_offset)
    if location_id:
        params["location_id"] = location_id
    if collaborators:
        params["collaborators"] = json.dumps([{"username": c} for c in collaborators])
    cid = create_media_container(client, ig_user_id, params)
    wait_for_container(client, cid, timeout=900)
    mid = publish_container(client, ig_user_id, cid)
    return cid, mid


def publish_carousel(
    client: GraphClient,
    ig_user_id: str,
    *,
    children_ids: list[str],
    caption: str | None = None,
    location_id: str | None = None,
) -> tuple[str, str]:
    if len(children_ids) < 2 or len(children_ids) > 10:
        raise GraphAPIError("Carousel must have 2–10 items")
    params: dict[str, Any] = {
        "media_type": "CAROUSEL",
        "children": ",".join(children_ids),
    }
    if caption:
        params["caption"] = caption
    if location_id:
        params["location_id"] = location_id
    cid = create_media_container(client, ig_user_id, params)
    wait_for_container(client, cid)
    mid = publish_container(client, ig_user_id, cid)
    return cid, mid


def create_carousel_child_image(
    client: GraphClient,
    ig_user_id: str,
    *,
    image_url: str,
    alt_text: str | None = None,
) -> str:
    params: dict[str, Any] = {
        "is_carousel_item": "true",
        "image_url": image_url,
    }
    if alt_text:
        params["alt_text"] = alt_text
    cid = create_media_container(client, ig_user_id, params)
    wait_for_container(client, cid)
    return cid


def create_carousel_child_video(
    client: GraphClient,
    ig_user_id: str,
    *,
    video_path: Path,
) -> str:
    session = init_resumable_upload(client, ig_user_id, media_type="VIDEO")
    upload_video_resumable(client, session, video_path)
    params = {
        "is_carousel_item": "true",
        "media_type": "VIDEO",
        "video_id": session,
    }
    cid = create_media_container(client, ig_user_id, params)
    wait_for_container(client, cid, timeout=900)
    return cid


def delete_media(client: GraphClient, media_id: str) -> dict[str, Any]:
    return client.delete(media_id)
