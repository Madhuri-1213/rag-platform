import pytest

from src.common.s3 import BUCKET, get_s3_client, object_exists, put_object_if_absent

KEY = "test/pytest_object.txt"


@pytest.fixture()
def s3():
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=BUCKET)
    except Exception:
        pytest.skip("MinIO not reachable, bucket missing, or MINIO_ROOT_PASSWORD not set")
    client.delete_object(Bucket=BUCKET, Key=KEY)
    yield client
    client.delete_object(Bucket=BUCKET, Key=KEY)


def test_first_write_then_skip(s3):
    assert put_object_if_absent(KEY, b"hello", client=s3) is True
    assert put_object_if_absent(KEY, b"changed", client=s3) is False
    body = s3.get_object(Bucket=BUCKET, Key=KEY)["Body"].read()
    assert body == b"hello"  # the second call did not overwrite


def test_object_exists(s3):
    assert object_exists(KEY, client=s3) is False
    put_object_if_absent(KEY, b"x", client=s3)
    assert object_exists(KEY, client=s3) is True