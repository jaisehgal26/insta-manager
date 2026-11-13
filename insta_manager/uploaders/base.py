from __future__ import annotations

import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path

from insta_manager.config import Settings


class ImageUploader(ABC):
    name: str

    @abstractmethod
    def upload(self, path: Path) -> str:
        """Return a public HTTPS URL suitable for image_url."""


class DirectPassthroughUploader(ImageUploader):
    """Use path only when user passes --image-url; upload() not supported."""

    name = "direct"

    def upload(self, path: Path) -> str:
        raise NotImplementedError("Use --image-url with a public URL, or pick catbox/s3 uploader")


class CatboxUploader(ImageUploader):
    """
    Free anonymous host (catbox.moe). Good for dev; files are public and retention not guaranteed.
    Trade-off: third-party service, no SLA, do not use for sensitive images.
    """

    name = "catbox"

    def upload(self, path: Path) -> str:
        import httpx

        mime, _ = mimetypes.guess_type(path)
        with path.open("rb") as f:
            resp = httpx.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (path.name, f, mime or "application/octet-stream")},
                timeout=120.0,
            )
        resp.raise_for_status()
        url = resp.text.strip()
        if not url.startswith("http"):
            raise RuntimeError(f"catbox upload failed: {resp.text}")
        return url


class S3CompatibleUploader(ImageUploader):
    """Upload to S3/R2/MinIO with public or configured base URL."""

    name = "s3"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def upload(self, path: Path) -> str:
        import boto3
        from botocore.client import Config

        if not self.settings.s3_bucket:
            raise RuntimeError("S3_BUCKET not configured")
        session = boto3.session.Session()
        client = session.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url,
            aws_access_key_id=self.settings.s3_access_key_id,
            aws_secret_access_key=self.settings.s3_secret_access_key,
            config=Config(signature_version="s3v4"),
        )
        key = f"insta-manager/{path.name}"
        content_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
        client.upload_file(
            str(path),
            self.settings.s3_bucket,
            key,
            ExtraArgs={"ContentType": content_type, "ACL": "public-read"},
        )
        base = (self.settings.s3_public_base_url or "").rstrip("/")
        if base:
            return f"{base}/{key}"
        if self.settings.s3_endpoint_url:
            return f"{self.settings.s3_endpoint_url.rstrip('/')}/{self.settings.s3_bucket}/{key}"
        return f"https://{self.settings.s3_bucket}.s3.amazonaws.com/{key}"


def get_uploader(settings: Settings) -> ImageUploader:
    name = settings.insta_manager_image_uploader.lower()
    if name == "catbox":
        return CatboxUploader()
    if name == "s3":
        return S3CompatibleUploader(settings)
    return DirectPassthroughUploader()
