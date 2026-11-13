import httpx
import respx

from insta_manager.api.client import GraphClient
from insta_manager.api import comments, insights


@respx.mock
def test_comments_crud() -> None:
    respx.get(url__regex=r".*/media1/comments.*").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "c1", "text": "hi"}]})
    )
    respx.post(url__regex=r".*/media1/comments.*").mock(return_value=httpx.Response(200, json={"id": "c2"}))
    respx.post(url__regex=r".*/c1/replies.*").mock(return_value=httpx.Response(200, json={"id": "r1"}))
    respx.post(url__regex=r".*/v21\.0/c1\?").mock(return_value=httpx.Response(200, json={"success": True}))
    respx.delete(url__regex=r".*/v21\.0/c1\?").mock(return_value=httpx.Response(200, json={"success": True}))
    respx.post(url__regex=r".*/v21\.0/media1\?").mock(return_value=httpx.Response(200, json={"success": True}))

    client = GraphClient(api_version="v21.0", access_token="tok")
    assert comments.list_comments(client, "media1")["data"][0]["id"] == "c1"
    assert comments.post_comment(client, "media1", "link https://x")["id"] == "c2"
    assert comments.reply_to_comment(client, "c1", "reply")["id"] == "r1"
    comments.hide_comment(client, "c1", hide=True)
    comments.delete_comment(client, "c1")
    comments.set_comments_enabled(client, "media1", enabled=False)


@respx.mock
def test_insights() -> None:
    respx.get(url__regex=r".*/ig/insights.*").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.get(url__regex=r".*/ig-user/insights.*").mock(return_value=httpx.Response(200, json={"data": []}))
    respx.get(url__regex=r".*/media1/insights.*").mock(return_value=httpx.Response(200, json={"data": []}))

    client = GraphClient(api_version="v21.0", access_token="tok")
    insights.account_insights(client, "ig-user")
    insights.media_insights(client, "media1")
