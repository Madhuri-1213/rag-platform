import os

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

BUCKET = os.getenv("S3_BUCKET", "arxiv-lake")


def get_s3_client():
    """S3 client for MinIO.

    On your laptop the endpoint is http://localhost:9000. Inside the Airflow
    containers, S3_ENDPOINT=http://minio:9000 comes from your .env file.
    """
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.getenv("MINIO_ROOT_USER", "minio"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "minio_root"),
        region_name="us-east-1",
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def object_exists(key: str, client=None, bucket: str = BUCKET) -> bool:
    client = client or get_s3_client()
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise  # a real problem (auth, network...) should not be hidden


def put_object_if_absent(
    key: str,
    data: bytes,
    content_type: str | None = None,
    client=None,
    bucket: str = BUCKET,
) -> bool:
    """Upload only if the key does not exist yet.

    Returns True if it wrote the object, False if it skipped (already there).
    This is what makes re-running a DAG safe.
    """
    client = client or get_s3_client()
    if object_exists(key, client=client, bucket=bucket):
        return False
    extra = {"ContentType": content_type} if content_type else {}
    client.put_object(Bucket=bucket, Key=key, Body=data, **extra)
    return True