from pathlib import Path

from typer.testing import CliRunner

from insta_manager.cli import app
from insta_manager.registry import AccountRecord, AccountRegistry


def test_cli_account_list_json(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("INSTA_MANAGER_HOME", str(tmp_path))
    reg = AccountRegistry(tmp_path / "accounts.json")
    reg.upsert(
        AccountRecord(
            alias="demo",
            ig_user_id="1",
            page_id="2",
            access_token="secret-token-value",
        )
    )
    runner = CliRunner()
    result = runner.invoke(app, ["account", "list", "--json"])
    assert result.exit_code == 0
    assert "demo" in result.stdout
    assert "secret-token-value" not in result.stdout


def test_cli_dry_run_publish_image(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("INSTA_MANAGER_HOME", str(tmp_path))
    reg = AccountRegistry(tmp_path / "accounts.json")
    reg.upsert(
        AccountRecord(
            alias="demo",
            ig_user_id="1",
            page_id="2",
            access_token="tok",
        )
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "publish",
            "image",
            "--account",
            "demo",
            "--image-url",
            "https://example.com/i.jpg",
            "--dry-run",
            "--json",
        ],
    )
    assert result.exit_code == 0
    assert "dry_run" in result.stdout
