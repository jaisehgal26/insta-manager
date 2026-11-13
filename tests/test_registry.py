from pathlib import Path

from insta_manager.registry import AccountRecord, AccountRegistry


def test_registry_upsert_list_remove(tmp_path: Path) -> None:
    path = tmp_path / "accounts.json"
    reg = AccountRegistry(path)
    rec = AccountRecord(
        alias="shop",
        ig_user_id="178414",
        page_id="1122",
        access_token="page-token-secret",
        page_name="Shop Page",
    )
    reg.upsert(rec)
    assert len(reg.list_accounts()) == 1
    assert reg.get("shop") is not None
    redacted = reg.redacted_list()[0]["access_token"]
    assert "page-tok" in redacted or "…" in redacted
    assert reg.remove("shop") is True
    assert reg.remove("shop") is False
