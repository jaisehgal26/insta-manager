from pathlib import Path

import httpx
import respx

from insta_manager.api.client import GraphClient
from insta_manager.api import publishing as pub


def _mock_container_flow(container_id: str = "c1", media_id: str = "m1") -> None:
    respx.post(url__regex=r".*/v21\.0/ig-user/media\?").mock(
        return_value=httpx.Response(200, json={"id": container_id})
    )
    respx.get(url__regex=rf".*/v21\.0/{container_id}.*").mock(
        return_value=httpx.Response(200, json={"id": container_id, "status_code": "FINISHED"})
    )
    respx.post(url__regex=r".*/v21\.0/ig-user/media_publish\?").mock(
        return_value=httpx.Response(200, json={"id": media_id})
    )


@respx.mock
def test_publish_single_image() -> None:
    _mock_container_flow()
    client = GraphClient(api_version="v21.0", access_token="page")
    cid, mid = pub.publish_single_image(
        client, "ig-user", image_url="https://example.com/a.jpg", caption="hi"
    )
    assert cid == "c1"
    assert mid == "m1"


@respx.mock
def test_content_publishing_limit_blocks() -> None:
    respx.get(url__regex=r".*/content_publishing_limit.*").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"quota_usage": 100, "config": {"quota_total": 100}}]},
        )
    )
    client = GraphClient(api_version="v21.0", access_token="page")
    resp = pub.get_content_publishing_limit(client, "ig-user")
    try:
        pub.assert_can_publish(resp)
        assert False
    except Exception as e:
        assert "exhausted" in str(e).lower()


@respx.mock
def test_resumable_upload_and_reel(tmp_path: Path) -> None:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"\x00\x00\x00\x20ftypmp42")

    def media_post(request: httpx.Request) -> httpx.Response:
        if "upload_type" in request.content.decode():
            return httpx.Response(200, json={"id": "upload_sess"})
        return httpx.Response(200, json={"id": "container_reel"})

    respx.post(url__regex=r".*/ig-user/media\?").mock(side_effect=media_post)
    respx.post(url__regex=r".*rupload\.facebook\.com.*").mock(return_value=httpx.Response(200, json={"success": True}))
    respx.get(url__regex=r".*/container_reel.*").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    respx.post(url__regex=r".*/media_publish.*").mock(return_value=httpx.Response(200, json={"id": "reel_media"}))

    client = GraphClient(api_version="v21.0", access_token="page")
    cid, mid = pub.publish_reel(client, "ig-user", video_path=video, caption="reel")
    assert mid == "reel_media"


@respx.mock
def test_wait_for_container_error() -> None:
    respx.get(url__regex=r".*/c-err.*").mock(
        return_value=httpx.Response(200, json={"status_code": "ERROR", "status": "Failed"})
    )
    client = GraphClient(api_version="v21.0", access_token="page")
    try:
        pub.wait_for_container(client, "c-err", poll_interval=0.01, timeout=1.0)
        assert False
    except Exception as e:
        assert "failed" in str(e).lower() or "Container" in str(e)
