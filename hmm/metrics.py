from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown_from_pnl(pnls: pd.Series, initial_capital: float) -> float:
    equity = initial_capital + pnls.fillna(0.0).cumsum()
    peak = equity.cummax()
    drawdown = (equity - peak) / peak.replace(0, np.nan) * 100
    return float(drawdown.min()) if not drawdown.empty else 0.0


def profit_factor(pnls: pd.Series) -> float:
    wins = pnls[pnls > 0].sum()
    losses = abs(pnls[pnls < 0].sum())
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return float(wins / losses)


def sharpe_ratio(pnls: pd.Series) -> float:
    returns = pnls.astype(float)
    if len(returns) < 2 or returns.std(ddof=0) == 0:
        return 0.0
    return float((returns.mean() / returns.std(ddof=0)) * np.sqrt(len(returns)))


def trade_metrics(trades: pd.DataFrame, initial_capital: float) -> dict[str, float]:
    if trades.empty:
        return {
            "net_profit": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "trades": 0,
            "avg_trade": 0.0,
        }
    pnls = trades["pnl_net"].astype(float)
    return {
        "net_profit": float(pnls.sum()),
        "win_rate": float((pnls > 0).mean() * 100),
        "profit_factor": profit_factor(pnls),
        "max_drawdown": max_drawdown_from_pnl(pnls, initial_capital),
        "sharpe_ratio": sharpe_ratio(pnls),
        "trades": int(len(trades)),
        "avg_trade": float(pnls.mean()),
    }


def metrics_by_regime(trades: pd.DataFrame, initial_capital: float) -> pd.DataFrame:
    if trades.empty or "regime" not in trades.columns:
        return pd.DataFrame()
    rows = []
    for regime, group in trades.groupby("regime", dropna=False):
        metrics = trade_metrics(group, initial_capital)
        label = group["regime_label"].dropna().iloc[0] if "regime_label" in group and group["regime_label"].notna().any() else ""
        rows.append({"regime": regime, "label": label, **metrics})
    return pd.DataFrame(rows).sort_values("regime").reset_index(drop=True)

