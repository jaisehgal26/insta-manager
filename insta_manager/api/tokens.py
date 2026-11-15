from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from insta_manager.api.client import GraphClient


def exchange_long_lived_user_token(
    client: GraphClient,
    *,
    app_id: str,
    app_secret: str,
    short_lived_token: str,
) -> dict[str, Any]:
    """GET /oauth/access_token?grant_type=fb_exchange_token"""
    # OAuth endpoint uses graph without version prefix in some docs; versioned works.
    return client.get(
        "oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_lived_token,
        },
    )


def debug_token(
    client: GraphClient,
    *,
    app_id: str,
    app_secret: str,
    input_token: str,
) -> dict[str, Any]:
    app_token = client.get(
        "oauth/access_token",
        params={
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": app_secret,
        },
    )
    return client.get(
        "debug_token",
        params={
            "input_token": input_token,
            "access_token": app_token["access_token"],
        },
    )


def parse_token_expiry(debug_data: dict[str, Any]) -> str | None:
    data = debug_data.get("data", debug_data)
    exp = data.get("expires_at")
    if exp is None or exp == 0:
        return None
    return datetime.fromtimestamp(int(exp), tz=timezone.utc).isoformat()


def discover_pages_with_ig(client: GraphClient) -> list[dict[str, Any]]:
    """GET /me/accounts with instagram_business_account field."""
    pages: list[dict[str, Any]] = []
    params: dict[str, Any] = {
        "fields": "id,name,access_token,instagram_business_account{id,username}",
        "limit": 100,
    }
    next_url: str | None = "me/accounts"
    first = True
    while next_url:
        if first:
            resp = client.get(next_url, params=params)
            first = False
        else:
            resp = client.request("GET", "", absolute_url=next_url)
        pages.extend(resp.get("data", []))
        next_url = resp.get("paging", {}).get("next")
    return pages
