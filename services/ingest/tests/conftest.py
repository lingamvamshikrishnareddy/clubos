import os

import pytest

DATABASE_URL = os.environ.get("CLUBOS_TEST_DATABASE_URL")


@pytest.fixture
def empty_db():
    """A migrated database with every table except reference tables emptied."""
    if not DATABASE_URL:
        pytest.skip("CLUBOS_TEST_DATABASE_URL not set")
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(DATABASE_URL) as conn:
        tables = [r[0] for r in conn.execute(
            "select tablename from pg_tables where schemaname = 'public' and tablename not in ('sports', 'data_sources')")]
        conn.execute(f"truncate {', '.join(tables)} cascade")
        conn.commit()
        yield conn
        conn.rollback()
        conn.execute(f"truncate {', '.join(tables)} cascade")
        conn.commit()
