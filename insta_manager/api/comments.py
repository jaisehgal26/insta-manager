from __future__ import annotations

from typing import Any

from insta_manager.api.client import GraphClient


def list_comments(client: GraphClient, media_id: str, *, limit: int = 50) -> dict[str, Any]:
    return client.get(
        f"{media_id}/comments",
        params={"fields": "id,text,username,timestamp,hidden,replies{id,text}", "limit": limit},
    )


def post_comment(client: GraphClient, media_id: str, message: str) -> dict[str, Any]:
    return client.post(f"{media_id}/comments", data={"message": message})


def reply_to_comment(client: GraphClient, comment_id: str, message: str) -> dict[str, Any]:
    return client.post(f"{comment_id}/replies", data={"message": message})


def hide_comment(client: GraphClient, comment_id: str, *, hide: bool = True) -> dict[str, Any]:
    return client.post(f"{comment_id}", data={"hide": "true" if hide else "false"})


def delete_comment(client: GraphClient, comment_id: str) -> dict[str, Any]:
    return client.delete(comment_id)


def set_comments_enabled(client: GraphClient, media_id: str, *, enabled: bool) -> dict[str, Any]:
    return client.post(
        media_id,
        data={"comment_enabled": "true" if enabled else "false"},
    )
