import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pgvector")
np = pytest.importorskip("numpy")

from src.embedding.store import connect, existing_embed_keys, retire_old_versions, upsert_chunks  # noqa: E402

ARXIV = "9999.00001"
MODEL = "test-model"


def fake_row(version, index=0):
    return {
        "chunk_id": f"testchunk-v{version}-{index}", "paper_key": f"testpaper-v{version}",
        "arxiv_id": ARXIV, "version": version, "title": "Test paper", "section": "Method",
        "published_at": "2026-10-15T10:00:00+00:00", "chunk_index": index,
        "text": "Some text for the test.", "text_hash": "h" * 64, "n_words": 5,
        "bronze_pdf_path": "bronze/test.pdf", "chunk_strategy": "section",
        "pipeline_version": "0.0.0", "embedding": np.full(384, 0.05, dtype=np.float32),
        "embed_key": f"key-v{version}-{index}",
    }


@pytest.fixture()
def conn():
    try:
        c = connect()
        c.execute("SELECT 1 FROM chunks LIMIT 1")  # fails if the table does not exist yet
    except Exception:
        pytest.skip("Postgres or the chunks table is not available")
    c.execute("DELETE FROM chunks WHERE arxiv_id = %s", (ARXIV,))
    c.commit()
    yield c
    c.rollback()
    c.execute("DELETE FROM chunks WHERE arxiv_id = %s", (ARXIV,))
    c.commit()
    c.close()


def test_upsert_is_idempotent_and_cache_lookup_works(conn):
    upsert_chunks(conn, [fake_row(1)], MODEL)
    upsert_chunks(conn, [fake_row(1)], MODEL)  # same chunk again: updates, never duplicates
    n = conn.execute("SELECT count(*) FROM chunks WHERE arxiv_id = %s", (ARXIV,)).fetchone()[0]
    assert n == 1
    assert existing_embed_keys(conn, ["testchunk-v1-0", "nope"]) == {"testchunk-v1-0": "key-v1-0"}
    assert existing_embed_keys(conn, []) == {}


def test_old_versions_are_retired(conn):
    upsert_chunks(conn, [fake_row(1), fake_row(2)], MODEL)
    assert retire_old_versions(conn) >= 1
    rows = dict(conn.execute("SELECT version, is_deleted FROM chunks WHERE arxiv_id = %s", (ARXIV,)).fetchall())
    assert rows == {1: True, 2: False}
    assert retire_old_versions(conn) == 0  # running it again retires nothing more
    rows2 = dict(conn.execute("SELECT version, is_deleted FROM chunks WHERE arxiv_id = %s", (ARXIV,)).fetchall())
    assert rows2 == rows