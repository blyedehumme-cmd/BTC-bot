from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    "log_return",
    "rolling_volatility",
    "momentum",
    "rolling_return",
    "range_pct",
    "atr_pct",
]


def build_hmm_features(candles: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Construye features estadisticas para HMM sin mirar hacia el futuro."""
    frame = candles.copy().sort_values("time").reset_index(drop=True)
    close = frame["close"].astype(float)
    high = frame["high"].astype(float)
    low = frame["low"].astype(float)

    frame["log_return"] = np.log(close / close.shift(1))
    frame["rolling_volatility"] = frame["log_return"].rolling(window).std()
    frame["momentum"] = close.pct_change(5)
    frame["rolling_return"] = close.pct_change(window)
    frame["range_pct"] = (high - low) / close.replace(0, np.nan)
    if "atr" in frame.columns:
        frame["atr_pct"] = frame["atr"].astype(float) / close.replace(0, np.nan)
    else:
        true_range = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        frame["atr_pct"] = true_range.rolling(14).mean() / close.replace(0, np.nan)

    frame = frame.replace([np.inf, -np.inf], np.nan)
    return frame.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)


def merge_context_features(primary: pd.DataFrame, context: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Agrega features de un timeframe superior alineadas por timestamp."""
    primary_sorted = primary.sort_values("time").reset_index(drop=True)
    context_features = build_hmm_features(context)
    keep = ["time", *FEATURE_COLUMNS]
    context_features = context_features[keep].rename(
        columns={col: f"{prefix}_{col}" for col in FEATURE_COLUMNS}
    )
    return pd.merge_asof(primary_sorted, context_features.sort_values("time"), on="time", direction="backward")


def feature_matrix(features: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    cols = [col for col in features.columns if col in FEATURE_COLUMNS or any(col.endswith(f"_{base}") for base in FEATURE_COLUMNS)]
    clean = features.dropna(subset=cols).copy()
    matrix = clean[cols].astype(float).to_numpy()
    return matrix, cols

