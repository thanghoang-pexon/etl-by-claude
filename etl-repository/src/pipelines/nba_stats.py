import time
import polars as pl
from nba_api.stats.endpoints import leagueleaders

from pipelines.base import BasePipeline
from validate import DQResult, validate as default_validate


class NbaStatsPipeline(BasePipeline):

    @property
    def name(self) -> str:
        return "nba_stats"

    @property
    def table_name(self) -> str:
        return "nba_player_stats"

    def extract(self) -> pl.DataFrame:
        print("[EXTRACT] Fetching NBA season leaders from NBA API...")
        time.sleep(1)  # rate limiting
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

    def transform(self, df: pl.DataFrame) -> pl.DataFrame:
        print("[TRANSFORM] Cleaning and enriching data...")
        df = df.rename({col: col.lower() for col in df.columns})

        df = df.select([
            "player_id", "player", "team", "gp",
            "pts", "ast", "reb", "stl", "blk", "tov",
            "fg_pct", "fg3_pct", "ft_pct",
        ])

        df = df.with_columns([
            (pl.col("pts") + pl.col("ast") * 1.5 + pl.col("reb") * 1.2
             + pl.col("stl") * 2.0 + pl.col("blk") * 2.0 - pl.col("tov"))
            .round(2)
            .alias("efficiency_score")
        ])

        df = df.sort("efficiency_score", descending=True)
        print(f"[TRANSFORM] Top player: {df['player'][0]} ({df['efficiency_score'][0]} efficiency)")
        return df

    def validate(self, df: pl.DataFrame) -> DQResult:
        result = default_validate(df)
        # NBA-spezifische Zusatzprüfung: mindestens 200 Spieler in einer vollen Saison
        if len(df) < 200:
            result.failures.append(f"NBA: expected ≥ 200 players, got {len(df)}")
            result.passed = False
        return result

    def create_table_sql(self) -> str:
        return """
            CREATE TABLE IF NOT EXISTS nba_player_stats (
                player_id        INTEGER PRIMARY KEY,
                player           TEXT NOT NULL,
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
        """
