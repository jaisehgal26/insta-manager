from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AccountRecord(BaseModel):
    """One Instagram Business/Creator account bound to a Facebook Page token."""

    alias: str = Field(description="Short name used with --account")
    ig_user_id: str
    page_id: str
    page_name: str | None = None
    access_token: str
    token_expires_at: str | None = None  # ISO8601 if known
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AccountRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load_raw(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"accounts": []}
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save_raw(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def list_accounts(self) -> list[AccountRecord]:
        data = self._load_raw()
        return [AccountRecord.model_validate(a) for a in data.get("accounts", [])]

    def get(self, alias: str) -> AccountRecord | None:
        for a in self.list_accounts():
            if a.alias == alias:
                return a
        return None

    def upsert(self, record: AccountRecord) -> None:
        data = self._load_raw()
        accounts = data.get("accounts", [])
        now = datetime.now(timezone.utc).isoformat()
        record.updated_at = now
        replaced = False
        for i, raw in enumerate(accounts):
            if raw.get("alias") == record.alias:
                accounts[i] = record.model_dump()
                replaced = True
                break
        if not replaced:
            accounts.append(record.model_dump())
        data["accounts"] = accounts
        self._save_raw(data)

    def remove(self, alias: str) -> bool:
        data = self._load_raw()
        accounts = data.get("accounts", [])
        new_accounts = [a for a in accounts if a.get("alias") != alias]
        if len(new_accounts) == len(accounts):
            return False
        data["accounts"] = new_accounts
        self._save_raw(data)
        return True

    def redacted_list(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for a in self.list_accounts():
            d = a.model_dump()
            tok = d.get("access_token", "")
            d["access_token"] = f"{tok[:8]}…" if len(tok) > 8 else "…"
            out.append(d)
        return out
