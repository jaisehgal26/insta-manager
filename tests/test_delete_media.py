import httpx
import respx

from insta_manager.api.client import GraphClient
from insta_manager.api import publishing


@respx.mock
def test_delete_media() -> None:
    respx.delete(url__regex=r".*/v21\.0/media123\?").mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    client = GraphClient(api_version="v21.0", access_token="tok")
    assert publishing.delete_media(client, "media123")["success"] is True
