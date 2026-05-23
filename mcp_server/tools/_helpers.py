

import duckdb


def fetch_one_strict(conn: duckdb.DuckDBPyConnection, sql: str, params: tuple = ()) -> tuple:
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise RuntimeError(f"Expected one row but got zero for query: {sql} with params {params}")
    return row