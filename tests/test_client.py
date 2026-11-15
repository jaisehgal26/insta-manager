import httpx
import respx

from insta_manager.api.client import GraphAPIError, GraphClient


@respx.mock
def test_graph_get_success() -> None:
    route = respx.get("https://graph.facebook.com/v21.0/me").mock(
        return_value=httpx.Response(200, json={"id": "123"})
    )
    with GraphClient(api_version="v21.0", access_token="tok") as client:
        data = client.get("me")
    assert data["id"] == "123"
    assert "access_token" in route.calls[0].request.url.params


@respx.mock
def test_graph_error_raises() -> None:
    respx.get("https://graph.facebook.com/v21.0/bad").mock(
        return_value=httpx.Response(
            400,
            json={"error": {"message": "Invalid", "code": 100}},
        )
    )
    client = GraphClient(api_version="v21.0", access_token="tok")
    try:
        client.get("bad")
        assert False, "expected error"
    except GraphAPIError as e:
        assert "Invalid" in str(e)
