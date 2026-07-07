"""Canonical team-name mapping.

Every join between data sources goes through here. The table lives in
data/reference/team_names.csv (canonical_id, canonical_name, alias) and covers the
name variants across aussportsbetting, uselessnrlstats and NRL.com — the
St George Illawarra / St. George class of landmine called out in the Build Spec.

Coverage is validated at ingest time: `to_canonical` raises on any unmapped name so
a new variant can never silently create a phantom team.
"""
from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd

REF_PATH = Path(__file__).resolve().parents[2] / "data" / "reference" / "team_names.csv"


@functools.lru_cache(maxsize=1)
def alias_table() -> pd.DataFrame:
    df = pd.read_csv(REF_PATH)
    dupes = df[df.duplicated("alias", keep=False)]
    if not dupes.empty:
        raise ValueError(f"duplicate aliases in team_names.csv:\n{dupes}")
    return df


@functools.lru_cache(maxsize=1)
def alias_to_id() -> dict[str, str]:
    df = alias_table()
    return dict(zip(df["alias"].str.strip(), df["canonical_id"]))


@functools.lru_cache(maxsize=1)
def id_to_name() -> dict[str, str]:
    df = alias_table()
    return dict(df.drop_duplicates("canonical_id")[["canonical_id", "canonical_name"]].values)


def to_canonical(series: pd.Series, source: str = "?") -> pd.Series:
    """Map a series of raw team names to canonical IDs; raise on unmapped names."""
    mapped = series.str.strip().map(alias_to_id())
    missing = sorted(series[mapped.isna() & series.notna()].unique())
    if missing:
        raise KeyError(
            f"unmapped team names from {source}: {missing} — add them to {REF_PATH}"
        )
    return mapped
