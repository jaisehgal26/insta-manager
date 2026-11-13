import httpx
import respx

from insta_manager.api.client import GraphClient
from insta_manager.api.tokens import discover_pages_with_ig, exchange_long_lived_user_token
from insta_manager.auth import store_pages_from_user_token
from insta_manager.registry import AccountRegistry


@respx.mock
def test_exchange_and_discover(tmp_path) -> None:
    respx.get(url__regex=r".*/oauth/access_token.*").mock(
        side_effect=[
            httpx.Response(200, json={"access_token": "long-user", "expires_in": 5184000}),
            httpx.Response(200, json={"access_token": "app|token"}),
        ]
    )
    respx.get(url__regex=r".*/me/accounts.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "99",
                        "name": "My Page",
                        "access_token": "page-long",
                        "instagram_business_account": {"id": "1789", "username": "myshop"},
                    }
                ]
            },
        )
    )
    respx.get(url__regex=r".*/debug_token.*").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"is_valid": True, "expires_at": 0, "type": "PAGE"}},
        )
    )

    client = GraphClient(api_version="v21.0")
    out = exchange_long_lived_user_token(
        client, app_id="app", app_secret="sec", short_lived_token="short"
    )
    assert out["access_token"] == "long-user"

    client.access_token = "long-user"
    pages = discover_pages_with_ig(client)
    assert len(pages) == 1

    reg = AccountRegistry(tmp_path / "accounts.json")
    client.access_token = "long-user"
    stored = store_pages_from_user_token(
        reg, client, app_id="app", app_secret="sec", user_token="long-user", exchange=False
    )
    assert stored[0].alias == "myshop"
