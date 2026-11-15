from __future__ import annotations

from typing import Any

from insta_manager.api.client import GraphClient

DEFAULT_ACCOUNT_METRICS = [
    "impressions",
    "reach",
    "profile_views",
    "accounts_engaged",
    "total_interactions",
]

DEFAULT_MEDIA_METRICS = [
    "impressions",
    "reach",
    "saved",
    "likes",
    "comments",
    "shares",
]


def account_insights(
    client: GraphClient,
    ig_user_id: str,
    *,
    metrics: list[str] | None = None,
    period: str = "day",
) -> dict[str, Any]:
    m = ",".join(metrics or DEFAULT_ACCOUNT_METRICS)
    return client.get(
        f"{ig_user_id}/insights",
        params={"metric": m, "period": period},
    )


def media_insights(
    client: GraphClient,
    media_id: str,
    *,
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    m = ",".join(metrics or DEFAULT_MEDIA_METRICS)
    return client.get(
        f"{media_id}/insights",
        params={"metric": m},
    )
