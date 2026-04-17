import os
import time
import polars as pl
import psycopg
from dotenv import load_dotenv
from nba_api.stats.endpoints import leagueleaders

load_dotenv()

def get_conn() -> psycopg.Connection:
    return psycopg.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def extract() -> pl.DataFrame:
    print("[EXTRACT] Fetching NBA season leaders from NBA API...")
    # nba_api has rate limiting, small delay avoids 429s
    time.sleep(1)
    response = leagueleaders.LeagueLeaders(
        league_id="00",
        per_mode48="PerGame",
        scope="S",
        season="2024-25",
        season_type_all_star="Regular Season",
        stat_category_abbreviation="PTS",
    )
    headers = response.league_leaders.get_dict()["headers"]
    rows = response.league_leaders.get_dict()["data"]
    df = pl.DataFrame(rows, schema=headers, orient="row")
    print(f"[EXTRACT] {len(df)} players fetched.")
    return df


def transform(df: pl.DataFrame) -> pl.DataFrame:
    print("[TRANSFORM] Cleaning and enriching data...")
    df = df.rename({col: col.lower() for col in df.columns})

    df = df.select([
        "player_id",
        "player",
        "team",
        "gp",       # games played
        "pts",      # points per game
        "ast",      # assists per game
        "reb",      # rebounds per game
        "stl",      # steals per game
        "blk",      # blocks per game
        "tov",      # turnovers per game
        "fg_pct",   # field goal %
        "fg3_pct",  # 3-point %
        "ft_pct",   # free throw %
    ])

    # efficiency score: simple composite metric
    df = df.with_columns([
        (pl.col("pts") + pl.col("ast") * 1.5 + pl.col("reb") * 1.2
         + pl.col("stl") * 2.0 + pl.col("blk") * 2.0 - pl.col("tov"))
        .round(2)
        .alias("efficiency_score")
    ])

    df = df.sort("efficiency_score", descending=True)
    print(f"[TRANSFORM] Top player: {df['player'][0]} ({df['efficiency_score'][0]} efficiency)")
    return df


def load(df: pl.DataFrame) -> None:
    print("[LOAD] Writing to Postgres (DIH)...")
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nba_player_stats (
                player_id        INTEGER PRIMARY KEY,
                player           TEXT,
                team             TEXT,
                gp               INTEGER,
                pts              FLOAT,
                ast              FLOAT,
                reb              FLOAT,
                stl              FLOAT,
                blk              FLOAT,
                tov              FLOAT,
                fg_pct           FLOAT,
                fg3_pct          FLOAT,
                ft_pct           FLOAT,
                efficiency_score FLOAT
            )
        """)
        conn.execute("TRUNCATE TABLE nba_player_stats")

        rows = df.to_dicts()
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO nba_player_stats
                    (player_id, player, team, gp, pts, ast, reb, stl, blk, tov,
                     fg_pct, fg3_pct, ft_pct, efficiency_score)
                VALUES
                    (%(player_id)s, %(player)s, %(team)s, %(gp)s, %(pts)s, %(ast)s,
                     %(reb)s, %(stl)s, %(blk)s, %(tov)s,
                     %(fg_pct)s, %(fg3_pct)s, %(ft_pct)s, %(efficiency_score)s)
                """,
                rows,
            )
    print(f"[LOAD] {len(df)} rows written to nba_player_stats.")


if __name__ == "__main__":
    raw = extract()
    transformed = transform(raw)
    load(transformed)
    print("[DONE] ETL pipeline completed successfully.")
