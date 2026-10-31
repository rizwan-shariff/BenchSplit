import hashlib
from pathlib import Path
from typing import Optional


def download_public_s3_object(
    bucket: str, key: str, destination: str | Path, region: str = "ap-south-1"
) -> tuple[Path, str]:
    try:
        import boto3
        from botocore import UNSIGNED
        from botocore.config import Config
    except ImportError as error:
        raise RuntimeError("boto3 is required for public S3 ingestion") from error
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    client = boto3.client("s3", region_name=region, config=Config(signature_version=UNSIGNED))
    client.download_file(bucket, key, str(path))
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    return path, digest


def s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key.lstrip('/')}"
