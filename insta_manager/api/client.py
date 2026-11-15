from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx


class GraphAPIError(Exception):
    def __init__(self, message: str, *, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class GraphClient:
    """HTTP client for graph.facebook.com and rupload.facebook.com."""

    GRAPH_HOST = "https://graph.facebook.com"
    RUPLOAD_HOST = "https://rupload.facebook.com"

    def __init__(
        self,
        *,
        api_version: str,
        access_token: str | None = None,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        ver = api_version.strip()
        if not ver.startswith("v"):
            ver = f"v{ver}"
        self.api_version = ver
        self.access_token = access_token
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._async_client: httpx.AsyncClient | None = None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> GraphClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _graph_url(self, path: str) -> str:
        path = path.lstrip("/")
        if path.startswith("http"):
            return path
        return f"{self.GRAPH_HOST}/{self.api_version}/{path}"

    def _params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        p: dict[str, Any] = {}
        if self.access_token:
            p["access_token"] = self.access_token
        if extra:
            p.update(extra)
        return p

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        files: Any = None,
        absolute_url: str | None = None,
    ) -> dict[str, Any]:
        url = absolute_url or self._graph_url(path)
        merged = self._params(params)
        resp = self._client.request(
            method,
            url,
            params=merged if not absolute_url else params,
            data=data,
            json=json,
            headers=headers,
            files=files,
        )
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        if resp.status_code >= 400:
            msg = body.get("error", {}).get("message", resp.text) if isinstance(body, dict) else resp.text
            raise GraphAPIError(str(msg), status=resp.status_code, body=body)
        if isinstance(body, dict):
            return body
        return {"data": body}

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        return self.request("DELETE", path, **kwargs)

    def rupload(
        self,
        session_id: str,
        *,
        file_bytes: bytes,
        file_size: int,
        content_type: str = "application/octet-stream",
        access_token: str | None = None,
    ) -> dict[str, Any]:
        token = access_token or self.access_token
        if not token:
            raise GraphAPIError("access_token required for rupload")
        url = f"{self.RUPLOAD_HOST}/{self.api_version}/{session_id}"
        headers = {
            "Authorization": f"OAuth {token}",
            "offset": "0",
            "file_size": str(file_size),
            "Content-Type": content_type,
        }
        resp = self._client.post(url, content=file_bytes, headers=headers)
        try:
            body = resp.json()
        except Exception:
            body = {"raw": resp.text}
        if resp.status_code >= 400:
            msg = body.get("error", {}).get("message", resp.text) if isinstance(body, dict) else resp.text
            raise GraphAPIError(str(msg), status=resp.status_code, body=body)
        return body if isinstance(body, dict) else {"data": body}
