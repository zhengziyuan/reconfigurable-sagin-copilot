from __future__ import annotations

from typing import Any


class S3ArtifactStore:
    """MinIO/S3 production replacement boundary for artifact storage."""

    backend = "s3-compatible"

    def __init__(self, endpoint_url: str, bucket: str) -> None:
        self.endpoint_url = endpoint_url
        self.bucket = bucket

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "status": "not_configured",
            "endpoint_present": bool(self.endpoint_url),
            "bucket": self.bucket,
            "next_step": "Wire boto3 or minio-py and reuse ArtifactStore keys from the local backend.",
        }
