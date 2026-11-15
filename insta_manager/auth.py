from __future__ import annotations

import secrets
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from insta_manager.api.client import GraphClient
from insta_manager.api.tokens import (
    debug_token,
    discover_pages_with_ig,
    exchange_long_lived_user_token,
    parse_token_expiry,
)
from insta_manager.registry import AccountRecord, AccountRegistry


def store_pages_from_user_token(
    registry: AccountRegistry,
    client: GraphClient,
    *,
    app_id: str,
    app_secret: str,
    user_token: str,
    exchange: bool = True,
) -> list[AccountRecord]:
    token = user_token
    user_expires: str | None = None
    if exchange:
        exchanged = exchange_long_lived_user_token(
            client,
            app_id=app_id,
            app_secret=app_secret,
            short_lived_token=user_token,
        )
        token = exchanged["access_token"]
        expires_in = exchanged.get("expires_in")
        if expires_in:
            from datetime import datetime, timedelta, timezone

            user_expires = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()

    client.access_token = token
    pages = discover_pages_with_ig(client)
    stored: list[AccountRecord] = []
    for page in pages:
        ig = page.get("instagram_business_account")
        if not ig:
            continue
        ig_id = str(ig.get("id"))
        page_token = page.get("access_token")
        if not page_token:
            continue
        dbg = debug_token(
            GraphClient(api_version=client.api_version),
            app_id=app_id,
            app_secret=app_secret,
            input_token=page_token,
        )
        page_exp = parse_token_expiry(dbg)
        alias_base = ig.get("username") or page.get("name") or ig_id
        alias = _sanitize_alias(str(alias_base))
        alias = _unique_alias(registry, alias)
        rec = AccountRecord(
            alias=alias,
            ig_user_id=ig_id,
            page_id=str(page["id"]),
            page_name=page.get("name"),
            access_token=page_token,
            token_expires_at=page_exp or user_expires,
        )
        registry.upsert(rec)
        stored.append(rec)
    return stored


def _sanitize_alias(s: str) -> str:
    out = "".join(c if c.isalnum() or c in "-_" else "-" for c in s.lower())
    return out.strip("-") or "account"


def _unique_alias(registry: AccountRegistry, base: str) -> str:
    if not registry.get(base):
        return base
    i = 2
    while registry.get(f"{base}-{i}"):
        i += 1
    return f"{base}-{i}"


def oauth_login_url(
    *,
    app_id: str,
    redirect_uri: str,
    api_version: str = "v21.0",
    scopes: list[str] | None = None,
) -> tuple[str, str]:
    scope = ",".join(
        scopes
        or [
            "instagram_basic",
            "instagram_content_publish",
            "instagram_manage_comments",
            "instagram_manage_insights",
            "instagram_manage_contents",
            "pages_show_list",
            "pages_read_engagement",
            "business_management",
        ]
    )
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "response_type": "code",
        "state": state,
    }
    ver = api_version if api_version.startswith("v") else f"v{api_version}"
    return f"https://www.facebook.com/{ver}/dialog/oauth?" + urllib.parse.urlencode(params), state


def run_local_oauth(
    *,
    app_id: str,
    app_secret: str,
    redirect_uri: str,
    api_version: str,
) -> str:
    """Start local server, open browser, return authorization code."""
    url, state = oauth_login_url(app_id=app_id, redirect_uri=redirect_uri, api_version=api_version)
    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8765
    path = parsed.path or "/callback"
    code_holder: dict[str, str] = {}
    error_holder: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            req = urllib.parse.urlparse(self.path)
            if req.path != path:
                self.send_error(404)
                return
            qs = urllib.parse.parse_qs(req.query)
            if qs.get("state", [""])[0] != state:
                error_holder["error"] = "state mismatch"
                self._respond("State mismatch. Close this window.")
                return
            if "error" in qs:
                error_holder["error"] = qs["error"][0]
                self._respond(f"Error: {qs['error'][0]}")
                return
            code = qs.get("code", [""])[0]
            if not code:
                error_holder["error"] = "no code"
                self._respond("No code received.")
                return
            code_holder["code"] = code
            self._respond("Authorization successful. You can close this window.")

        def _respond(self, body: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><p>{body}</p></body></html>".encode())

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer((host, port), Handler)
    webbrowser.open(url)
    server.handle_request()
    server.server_close()
    if error_holder:
        raise RuntimeError(error_holder.get("error", "oauth failed"))
    if "code" not in code_holder:
        raise RuntimeError("No authorization code received")
    client = GraphClient(api_version=api_version)
    token_resp = client.get(
        "oauth/access_token",
        params={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code_holder["code"],
        },
    )
    return str(token_resp["access_token"])


def check_and_refresh_accounts(
    registry: AccountRegistry,
    *,
    app_id: str,
    app_secret: str,
    api_version: str,
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    client = GraphClient(api_version=api_version)
    for acct in registry.list_accounts():
        dbg = debug_token(client, app_id=app_id, app_secret=app_secret, input_token=acct.access_token)
        data = dbg.get("data", {})
        expires = parse_token_expiry(dbg)
        is_valid = data.get("is_valid", False)
        entry = {
            "alias": acct.alias,
            "ig_user_id": acct.ig_user_id,
            "valid": is_valid,
            "expires_at": expires or acct.token_expires_at,
            "type": data.get("type"),
            "refreshed": False,
        }
        if expires and expires != acct.token_expires_at:
            acct.token_expires_at = expires
            registry.upsert(acct)
        report.append(entry)
    return report
