import os

import psycopg


def get_conn() -> psycopg.Connection:
    """Open a Postgres connection using environment variables.

    On your laptop the host is localhost. Inside the Airflow containers it is
    the service name `postgres` (set POSTGRES_HOST=postgres in docker-compose).
    """
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "rag_user"),
        password=os.getenv("POSTGRES_PASSWORD", "rag_password"),
        dbname=os.getenv("POSTGRES_DB", "rag_db"),
    )