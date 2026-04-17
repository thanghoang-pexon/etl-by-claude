import os
import psycopg
import polars as pl


def get_conn() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def _infer_ddl(table_name: str, df: pl.DataFrame) -> str:
    """Generiert CREATE TABLE aus Polars-Schema — Fallback wenn Pipeline kein create_table_sql() hat."""
    type_map = {
        pl.Int32: "INTEGER", pl.Int64: "BIGINT",
        pl.Float32: "FLOAT", pl.Float64: "FLOAT",
        pl.Boolean: "BOOLEAN", pl.Utf8: "TEXT", pl.String: "TEXT",
        pl.Date: "DATE", pl.Datetime: "TIMESTAMP",
    }
    cols = ", ".join(
        f"{col} {type_map.get(type(dtype), 'TEXT')}"
        for col, dtype in zip(df.columns, df.dtypes)
    )
    return f"CREATE TABLE IF NOT EXISTS {table_name} ({cols})"


def load(df: pl.DataFrame, table_name: str, create_sql: str = "") -> None:
    print(f"[LOAD] Writing {len(df)} rows to '{table_name}'...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            ddl = create_sql or _infer_ddl(table_name, df)
            cur.execute(ddl)
            cur.execute(f"TRUNCATE TABLE {table_name}")

            placeholders = ", ".join(f"%({col})s" for col in df.columns)
            col_list = ", ".join(df.columns)
            cur.executemany(
                f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})",
                df.to_dicts(),
            )
    print(f"[LOAD] Done.")
