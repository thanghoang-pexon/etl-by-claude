import polars as pl
import pytest

from etl import transform
from validate import validate, DQResult


def make_raw_df(n: int = 3, **overrides) -> pl.DataFrame:
    """Minimal raw NBA dataframe matching the API schema."""
    base = {
        "PLAYER_ID": list(range(1, n + 1)),
        "PLAYER": [f"Player {i}" for i in range(1, n + 1)],
        "TEAM": ["LAL"] * n,
        "GP": [60] * n,
        "PTS": [25.0] * n,
        "AST": [8.0] * n,
        "REB": [7.5] * n,
        "STL": [1.2] * n,
        "BLK": [0.5] * n,
        "TOV": [3.5] * n,
        "FG_PCT": [0.54] * n,
        "FG3_PCT": [0.41] * n,
        "FT_PCT": [0.75] * n,
    }
    base.update(overrides)
    return pl.DataFrame(base)


def make_nba_trio(**overrides) -> pl.DataFrame:
    """Three real players for tests that check player-specific logic."""
    base = {
        "PLAYER_ID": [1, 2, 3],
        "PLAYER": ["LeBron James", "Nikola Jokić", "Giannis Antetokounmpo"],
        "TEAM": ["LAL", "DEN", "MIL"],
        "GP": [60, 58, 62],
        "PTS": [25.0, 29.6, 30.4],
        "AST": [8.0, 9.0, 6.5],
        "REB": [7.5, 12.8, 11.5],
        "STL": [1.2, 1.3, 1.2],
        "BLK": [0.5, 0.7, 1.1],
        "TOV": [3.5, 3.0, 3.2],
        "FG_PCT": [0.54, 0.58, 0.61],
        "FG3_PCT": [0.41, 0.35, 0.27],
        "FT_PCT": [0.75, 0.65, 0.65],
    }
    base.update(overrides)
    return pl.DataFrame(base)


class TestTransform:
    def test_columns_renamed_to_lowercase(self):
        df = transform(make_nba_trio())
        assert all(col == col.lower() for col in df.columns)

    def test_efficiency_score_is_computed(self):
        df = transform(make_nba_trio())
        assert "efficiency_score" in df.columns
        assert df["efficiency_score"].null_count() == 0

    def test_sorted_by_efficiency_descending(self):
        df = transform(make_nba_trio())
        scores = df["efficiency_score"].to_list()
        assert scores == sorted(scores, reverse=True)

    def test_jokic_beats_lebron(self):
        df = transform(make_nba_trio())
        players = df["player"].to_list()
        assert players.index("Nikola Jokić") < players.index("LeBron James")

    def test_only_expected_columns_present(self):
        df = transform(make_nba_trio())
        expected = {
            "player_id", "player", "team", "gp", "pts", "ast", "reb",
            "stl", "blk", "tov", "fg_pct", "fg3_pct", "ft_pct", "efficiency_score",
        }
        assert set(df.columns) == expected

    def test_efficiency_formula(self):
        """pts + ast*1.5 + reb*1.2 + stl*2 + blk*2 - tov, rounded to 2."""
        df = transform(make_nba_trio())
        row = df.filter(pl.col("player") == "Nikola Jokić").row(0, named=True)
        expected = round(
            row["pts"] + row["ast"] * 1.5 + row["reb"] * 1.2
            + row["stl"] * 2.0 + row["blk"] * 2.0 - row["tov"],
            2,
        )
        assert row["efficiency_score"] == expected


class TestValidate:
    def test_valid_dataframe_passes(self):
        df = transform(make_raw_df(n=100))
        result = validate(df)
        assert result.passed

    def test_fails_on_too_few_rows(self):
        df = transform(make_nba_trio())
        result = validate(df)
        assert not result.passed
        assert any("Too few rows" in f for f in result.failures)

    def test_fails_on_duplicate_player_ids(self):
        df = transform(make_raw_df(n=100))
        df = df.with_columns(pl.lit(1).alias("player_id"))
        result = validate(df)
        assert not result.passed
        assert any("Duplicate" in f for f in result.failures)

    def test_fails_on_negative_pts(self):
        df = transform(make_raw_df(n=100))
        df = df.with_columns(pl.lit(-1.0).alias("pts"))
        result = validate(df)
        assert not result.passed
        assert any("Negative pts" in f for f in result.failures)

    def test_fails_on_out_of_range_pct(self):
        df = transform(make_raw_df(n=100))
        df = df.with_columns(pl.lit(1.5).alias("fg_pct"))
        result = validate(df)
        assert not result.passed
        assert any("fg_pct" in f for f in result.failures)

    def test_dqresult_str_on_pass(self):
        result = DQResult(passed=True, failures=[])
        assert "passed" in str(result)

    def test_dqresult_str_on_fail(self):
        result = DQResult(passed=False, failures=["Something broke"])
        assert "FAILED" in str(result)
        assert "Something broke" in str(result)
