#!/usr/bin/env python3
"""
Analisis HMM de regimenes para Lesly BTC Bot.

Este script NO cambia la estrategia principal ni activa trading real. Ejecuta
backtests historicos y clasifica cada trade por regimen HMM para comparar
Swing Trading contra una variante Day Trading de investigacion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from pathlib import Path
from typing import Any

import pandas as pd

from backtest import (
    ADX_THRESHOLD,
    ATR_STOP_MULTIPLIER,
    ATR_TAKE_PROFIT_MULTIPLIER,
    ATR_TRAILING_MULTIPLIER,
    INITIAL_CAPITAL,
    KRAKEN_FEE_RATE,
    MIN_CONFIDENCE,
    MIN_MINUTES_BETWEEN_TRADES,
    MIN_REQUIRED_CANDLES,
    MAX_TRADES_PER_DAY,
    build_signal_from_analyses,
    calculate_position_size,
    row_to_analysis,
)
from data_loader import INTERVALS, load_all_timeframes, load_ohlc
from indicators import add_indicators
from hmm.metrics import metrics_by_regime
from hmm.model import HMMUnavailableError
from hmm.regimes import classify_trades_by_regime, train_and_assign_regimes
from hmm.report import WARNING, generate_hmm_outputs


OUTPUT_DIR = Path(os.getenv("HMM_OUTPUT_DIR", "hmm_reports"))
HMM_MIN_STATES = int(os.getenv("HMM_MIN_STATES", "2"))
HMM_MAX_STATES = int(os.getenv("HMM_MAX_STATES", "5"))


@dataclass
class ResearchProfile:
    name: str
    base_label: str
    fourh_label: str
    daily_label: str
    weekly_label: str
    hmm_primary_label: str
    hmm_context_label: str
    description: str


PROFILES = [
    ResearchProfile(
        name="swing",
        base_label="1H",
        fourh_label="4H",
        daily_label="1D",
        weekly_label="1W",
        hmm_primary_label="4H",
        hmm_context_label="1D",
        description="Bot principal: entrada 1H, confirmacion 4H/1D y contexto 1W.",
    ),
    ResearchProfile(
        name="day",
        base_label="15M",
        fourh_label="1H",
        daily_label="4H",
        weekly_label="1D",
        hmm_primary_label="15M",
        hmm_context_label="1H",
        description="Variante de investigacion: entrada 15M, confirmacion 1H/4H y contexto 1D.",
    ),
]


def prepare_frame(label: str, raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        print(f"ADVERTENCIA: {label} no tiene datos.")
        return raw
    enriched = add_indicators(raw)
    cleaned = enriched.dropna(subset=["ema100", "atr"]).reset_index(drop=True)
    if len(cleaned) < MIN_REQUIRED_CANDLES:
        print(f"ADVERTENCIA: {label} tiene pocas velas utiles para la estrategia: {len(cleaned)}.")
    return cleaned


def load_research_data(refresh: bool = False) -> dict[str, pd.DataFrame]:
    base_data = load_all_timeframes(refresh=refresh)
    data = {label: prepare_frame(label, frame) for label, frame in base_data.items()}
    if "15M" not in data:
        raw_15m = load_ohlc("15M", 15, refresh=refresh)
        data["15M"] = prepare_frame("15M", raw_15m)
    return data


def prefixed_analysis(row: pd.Series, prefix: str) -> dict[str, Any]:
    return {
        "trend": str(row[f"{prefix}_trend"]),
        "price": float(row[f"{prefix}_close"]),
        "ema21": float(row[f"{prefix}_ema21"]),
        "ema50": float(row[f"{prefix}_ema50"]),
        "ema100": float(row[f"{prefix}_ema100"]),
        "macd": {
            "macd": float(row[f"{prefix}_macd"]),
            "signal": float(row[f"{prefix}_macd_signal"]),
            "hist": float(row[f"{prefix}_macd_hist"]),
        },
        "adx": float(row[f"{prefix}_adx"]),
        "volume_ratio": float(row[f"{prefix}_volume_ratio"]),
        "atr": float(row[f"{prefix}_atr"]),
    }


def build_aligned_profile_frame(data: dict[str, pd.DataFrame], profile: ResearchProfile) -> pd.DataFrame:
    base = data[profile.base_label].sort_values("time").reset_index(drop=True).copy()
    cols = [
        "time",
        "trend",
        "close",
        "ema21",
        "ema50",
        "ema100",
        "macd",
        "macd_signal",
        "macd_hist",
        "adx",
        "volume_ratio",
        "atr",
    ]
    for label, prefix in [
        (profile.fourh_label, "fourh"),
        (profile.daily_label, "daily"),
        (profile.weekly_label, "weekly"),
    ]:
        right = data[label][cols].sort_values("time").reset_index(drop=True).copy()
        right = right.rename(columns={col: f"{prefix}_{col}" for col in cols if col != "time"})
        base = pd.merge_asof(base, right, on="time", direction="backward")
    return base


def signal_for_profile(row: pd.Series) -> dict[str, Any]:
    required = ["weekly_trend", "daily_trend", "fourh_trend", "weekly_ema100", "daily_ema100", "fourh_ema100"]
    if any(pd.isna(row.get(col)) for col in required):
        return {"signal": "WAIT", "confidence": 0.0, "reason": "Faltan velas alineadas.", "price": float(row["close"]), "atr": 0.0}
    weekly = prefixed_analysis(row, "weekly")
    daily = prefixed_analysis(row, "daily")
    fourh = prefixed_analysis(row, "fourh")
    base = row_to_analysis(row)
    return build_signal_from_analyses(weekly, daily, fourh, base)


class GenericBacktester:
    def __init__(self, aligned: pd.DataFrame) -> None:
        self.aligned = aligned
        self.balance = INITIAL_CAPITAL
        self.position: dict[str, Any] | None = None
        self.trades: list[dict[str, Any]] = []
        self.equity_curve: list[dict[str, Any]] = []
        self.last_trade_time: pd.Timestamp | None = None
        self.daily_trades: dict[date, int] = {}

    def can_open_trade(self, timestamp: pd.Timestamp, ignore_cooldown: bool = False) -> bool:
        if self.daily_trades.get(timestamp.date(), 0) >= MAX_TRADES_PER_DAY:
            return False
        if ignore_cooldown or self.last_trade_time is None:
            return True
        elapsed_minutes = (timestamp - self.last_trade_time).total_seconds() / 60
        return elapsed_minutes >= MIN_MINUTES_BETWEEN_TRADES

    def register_open(self, timestamp: pd.Timestamp) -> None:
        self.last_trade_time = timestamp
        self.daily_trades[timestamp.date()] = self.daily_trades.get(timestamp.date(), 0) + 1

    def open_position(self, signal: dict[str, Any], candle: pd.Series) -> None:
        side = signal["signal"]
        entry_price = float(candle["close"])
        atr_value = float(signal["atr"])
        adx_value = float(candle["adx"])
        size = calculate_position_size(self.balance, entry_price, atr_value, adx_value)
        if size <= 0:
            return
        if side == "LONG":
            stop = entry_price - atr_value * ATR_STOP_MULTIPLIER
            take = entry_price + atr_value * ATR_TAKE_PROFIT_MULTIPLIER
        else:
            stop = entry_price + atr_value * ATR_STOP_MULTIPLIER
            take = entry_price - atr_value * ATR_TAKE_PROFIT_MULTIPLIER
        self.position = {
            "side": side,
            "entry_time": candle["datetime"],
            "entry_price": entry_price,
            "size": size,
            "stop_loss": stop,
            "initial_stop_loss": stop,
            "take_profit": take,
            "entry_fee": entry_price * size * KRAKEN_FEE_RATE,
            "highest_price": entry_price,
            "lowest_price": entry_price,
            "signal_reason": signal["reason"],
        }
        self.register_open(candle["datetime"])

    def update_trailing_stop(self, candle: pd.Series) -> None:
        if self.position is None or float(candle["adx"]) < ADX_THRESHOLD:
            return
        atr_value = float(candle["atr"])
        if atr_value <= 0:
            return
        if self.position["side"] == "LONG":
            self.position["highest_price"] = max(self.position["highest_price"], float(candle["high"]))
            self.position["stop_loss"] = max(
                self.position["stop_loss"],
                self.position["highest_price"] - atr_value * ATR_TRAILING_MULTIPLIER,
            )
        else:
            self.position["lowest_price"] = min(self.position["lowest_price"], float(candle["low"]))
            self.position["stop_loss"] = min(
                self.position["stop_loss"],
                self.position["lowest_price"] + atr_value * ATR_TRAILING_MULTIPLIER,
            )

    def check_exit(self, candle: pd.Series) -> tuple[str | None, float | None]:
        if self.position is None:
            return None, None
        high = float(candle["high"])
        low = float(candle["low"])
        if self.position["side"] == "LONG":
            if low <= self.position["stop_loss"]:
                reason = "TRAILING_STOP" if self.position["stop_loss"] > self.position["initial_stop_loss"] else "STOP_LOSS"
                return reason, self.position["stop_loss"]
            if high >= self.position["take_profit"]:
                return "TAKE_PROFIT", self.position["take_profit"]
        else:
            if high >= self.position["stop_loss"]:
                reason = "TRAILING_STOP" if self.position["stop_loss"] < self.position["initial_stop_loss"] else "STOP_LOSS"
                return reason, self.position["stop_loss"]
            if low <= self.position["take_profit"]:
                return "TAKE_PROFIT", self.position["take_profit"]
        return None, None

    def close_position(self, candle: pd.Series, exit_price: float, reason: str) -> None:
        if self.position is None:
            return
        pos = self.position
        gross = (
            (exit_price - pos["entry_price"]) * pos["size"]
            if pos["side"] == "LONG"
            else (pos["entry_price"] - exit_price) * pos["size"]
        )
        exit_fee = exit_price * pos["size"] * KRAKEN_FEE_RATE
        fee_total = pos["entry_fee"] + exit_fee
        net = gross - fee_total
        self.balance += net
        exit_time = candle["datetime"]
        self.trades.append({
            "entry_time": pos["entry_time"],
            "exit_time": exit_time,
            "side": pos["side"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "size": pos["size"],
            "pnl_gross": gross,
            "pnl_net": net,
            "fee_total": fee_total,
            "exit_reason": reason,
            "duration_hours": (exit_time - pos["entry_time"]).total_seconds() / 3600,
            "signal_reason": pos["signal_reason"],
        })
        self.position = None
        self.last_trade_time = exit_time

    def current_equity(self, close_price: float) -> float:
        if self.position is None:
            return self.balance
        pos = self.position
        unrealized = (
            (close_price - pos["entry_price"]) * pos["size"]
            if pos["side"] == "LONG"
            else (pos["entry_price"] - close_price) * pos["size"]
        )
        return self.balance + unrealized

    def record_equity(self, candle: pd.Series) -> None:
        equity = self.current_equity(float(candle["close"]))
        peak = max([row["equity"] for row in self.equity_curve], default=INITIAL_CAPITAL)
        peak = max(peak, equity)
        self.equity_curve.append({
            "time": candle["datetime"],
            "equity": equity,
            "peak": peak,
            "drawdown_pct": ((equity - peak) / peak * 100) if peak else 0.0,
        })

    def run(self) -> tuple[pd.DataFrame, pd.DataFrame, float]:
        for _, candle in self.aligned.iterrows():
            exit_reason, exit_price = self.check_exit(candle)
            if exit_reason and exit_price is not None:
                self.close_position(candle, exit_price, exit_reason)
            if self.position is not None:
                self.update_trailing_stop(candle)

            signal = signal_for_profile(candle)
            allow_reversal = False
            if self.position is not None:
                opposite = (
                    self.position["side"] == "LONG" and signal["signal"] == "SHORT"
                    or self.position["side"] == "SHORT" and signal["signal"] == "LONG"
                )
                if opposite and signal["confidence"] >= MIN_CONFIDENCE:
                    self.close_position(candle, float(candle["close"]), f"REVERSAL_TO_{signal['signal']}")
                    allow_reversal = True

            if (
                self.position is None
                and signal["signal"] in {"LONG", "SHORT"}
                and self.can_open_trade(candle["datetime"], ignore_cooldown=allow_reversal)
            ):
                self.open_position(signal, candle)

            self.record_equity(candle)

        if self.position is not None and not self.aligned.empty:
            final_candle = self.aligned.iloc[-1]
            self.close_position(final_candle, float(final_candle["close"]), "END_OF_BACKTEST")
            self.record_equity(final_candle)

        return pd.DataFrame(self.trades), pd.DataFrame(self.equity_curve), self.balance


def run_profile(data: dict[str, pd.DataFrame], profile: ResearchProfile) -> dict[str, Any]:
    print(f"Ejecutando perfil {profile.name}: {profile.description}", flush=True)
    aligned = build_aligned_profile_frame(data, profile).dropna(subset=["weekly_trend", "daily_trend", "fourh_trend"]).reset_index(drop=True)
    max_rows = int(os.getenv(f"HMM_{profile.name.upper()}_MAX_ROWS", "0"))
    if max_rows > 0 and len(aligned) > max_rows:
        print(f"ADVERTENCIA: {profile.name} limitado a las ultimas {max_rows} velas por variable de entorno.", flush=True)
        aligned = aligned.tail(max_rows).reset_index(drop=True)
    backtester = GenericBacktester(aligned)
    trades, equity, final_capital = backtester.run()

    regimes, fit = train_and_assign_regimes(
        data[profile.hmm_primary_label],
        context=data.get(profile.hmm_context_label),
        context_prefix=profile.hmm_context_label.lower(),
        min_states=HMM_MIN_STATES,
        max_states=HMM_MAX_STATES,
    )
    classified = classify_trades_by_regime(trades, regimes)
    metrics = metrics_by_regime(classified, INITIAL_CAPITAL)

    return {
        "profile": profile,
        "trades": trades,
        "equity": equity,
        "final_capital": final_capital,
        "regimes": regimes,
        "fit": fit,
        "classified_trades": classified,
        "metrics": metrics,
    }


def main() -> None:
    print(WARNING, flush=True)
    refresh = os.getenv("HMM_REFRESH_DATA", "false").lower().strip() == "true"
    try:
        data = load_research_data(refresh=refresh)
        selected = {
            name.strip().lower()
            for name in os.getenv("HMM_PROFILES", "swing,day").split(",")
            if name.strip()
        }
        profiles = [profile for profile in PROFILES if profile.name in selected]
        if not profiles:
            raise ValueError("HMM_PROFILES no contiene perfiles validos. Usa swing, day o swing,day.")
        missing = [profile.name for profile in profiles if any(data.get(label, pd.DataFrame()).empty for label in [profile.base_label, profile.fourh_label, profile.daily_label, profile.weekly_label])]
        if missing:
            print(f"ADVERTENCIA: faltan datos para perfiles: {', '.join(missing)}", flush=True)
        results = {profile.name: run_profile(data, profile) for profile in profiles}
        generate_hmm_outputs(OUTPUT_DIR, results, INITIAL_CAPITAL)
    except HMMUnavailableError as exc:
        print(f"HMM deshabilitado: {exc}", flush=True)
        print("El bot y los backtests normales siguen funcionando sin HMM.", flush=True)
        return
    print(f"Reporte HMM generado en: {OUTPUT_DIR / 'hmm_regime_report.txt'}", flush=True)


if __name__ == "__main__":
    main()
