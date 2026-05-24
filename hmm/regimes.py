from __future__ import annotations

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS, build_hmm_features, feature_matrix, merge_context_features
from .model import HMMFitResult, fit_best_hmm, predict_ordered_states


def train_and_assign_regimes(
    primary: pd.DataFrame,
    context: pd.DataFrame | None = None,
    context_prefix: str = "context",
    min_states: int = 2,
    max_states: int = 5,
) -> tuple[pd.DataFrame, HMMFitResult]:
    """Entrena HMM y devuelve velas primarias con regimen ordenado por volatilidad."""
    features = build_hmm_features(primary)
    if context is not None and not context.empty:
        features = merge_context_features(features, context, context_prefix)
    matrix, columns = feature_matrix(features)
    clean = features.dropna(subset=columns).copy().reset_index(drop=True)
    result = fit_best_hmm(matrix, columns, min_states=min_states, max_states=max_states)
    clean["regime"] = predict_ordered_states(result, matrix)
    clean["regime_label"] = clean.apply(label_regime, axis=1)
    return clean, result


def label_regime(row: pd.Series) -> str:
    volatility = float(row.get("rolling_volatility", 0.0))
    momentum = float(row.get("rolling_return", row.get("momentum", 0.0)))
    regime = int(row["regime"])
    if momentum > 0.03:
        direction = "tendencia alcista"
    elif momentum < -0.03:
        direction = "tendencia bajista"
    else:
        direction = "lateral/mixto"
    return f"Regimen {regime} - {direction}"


def classify_trades_by_regime(trades: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    trades_sorted = trades.copy().sort_values("entry_time").reset_index(drop=True)
    trades_sorted["entry_dt"] = pd.to_datetime(trades_sorted["entry_time"], utc=True)
    regime_lookup = regimes[["datetime", "regime", "regime_label"]].copy()
    regime_lookup["regime_dt"] = pd.to_datetime(regime_lookup["datetime"], utc=True)
    regime_lookup = regime_lookup.dropna(subset=["regime_dt"]).sort_values("regime_dt").reset_index(drop=True)
    classified = pd.merge_asof(
        trades_sorted.sort_values("entry_dt"),
        regime_lookup,
        left_on="entry_dt",
        right_on="regime_dt",
        direction="backward",
    )
    return classified.drop(columns=["datetime", "regime_dt"], errors="ignore")


def transition_matrix(regimes: pd.DataFrame) -> pd.DataFrame:
    states = sorted(int(state) for state in regimes["regime"].dropna().unique())
    matrix = pd.DataFrame(0.0, index=states, columns=states)
    values = regimes["regime"].astype(int).to_numpy()
    for prev, current in zip(values[:-1], values[1:]):
        matrix.loc[int(prev), int(current)] += 1.0
    row_sums = matrix.sum(axis=1).replace(0, np.nan)
    return matrix.div(row_sums, axis=0).fillna(0.0)


def regime_distribution(regimes: pd.DataFrame) -> pd.DataFrame:
    counts = regimes["regime"].value_counts().sort_index()
    total = counts.sum()
    return pd.DataFrame({
        "regime": counts.index,
        "bars": counts.values,
        "time_pct": counts.values / total * 100 if total else 0.0,
    })
