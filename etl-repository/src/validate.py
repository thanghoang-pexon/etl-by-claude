import polars as pl
from dataclasses import dataclass


@dataclass
class DQResult:
    passed: bool
    failures: list[str]

    def __str__(self) -> str:
        if self.passed:
            return "[VALIDATE] All checks passed."
        return "[VALIDATE] FAILED:\n" + "\n".join(f"  ✗ {f}" for f in self.failures)


def validate(df: pl.DataFrame) -> DQResult:
    failures = []

    # --- Vollständigkeit ---
    if len(df) < 100:
        failures.append(f"Too few rows: {len(df)} (expected ≥ 100)")

    # --- Keine doppelten Spieler ---
    dupes = df["player_id"].n_unique()
    if dupes != len(df):
        failures.append(f"Duplicate player_ids: {len(df) - dupes} duplicates found")

    # --- Keine Nullwerte in Pflichtfeldern ---
    for col in ["player_id", "player", "team", "pts", "efficiency_score"]:
        null_count = df[col].null_count()
        if null_count > 0:
            failures.append(f"Nulls in '{col}': {null_count} rows")

    # --- Wertebereich: Punkte müssen positiv sein ---
    negative_pts = df.filter(pl.col("pts") < 0).height
    if negative_pts > 0:
        failures.append(f"Negative pts values: {negative_pts} rows")

    # --- Wertebereich: Prozentwerte zwischen 0 und 1 ---
    for pct_col in ["fg_pct", "fg3_pct", "ft_pct"]:
        out_of_range = df.filter(
            pl.col(pct_col).is_not_null()
            & ((pl.col(pct_col) < 0) | (pl.col(pct_col) > 1))
        ).height
        if out_of_range > 0:
            failures.append(f"Out-of-range values in '{pct_col}': {out_of_range} rows")

    # --- Efficiency Score muss berechnet sein ---
    null_efficiency = df["efficiency_score"].null_count()
    if null_efficiency > 0:
        failures.append(f"Null efficiency_score: {null_efficiency} rows")

    return DQResult(passed=len(failures) == 0, failures=failures)
