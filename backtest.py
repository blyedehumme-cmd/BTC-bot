#!/usr/bin/env python3
"""
Backtester historico para Lesly BTC Bot.

Ejecuta la estrategia swing multi-timeframe sobre velas reales de Kraken:
1H para entrada, 4H/1D como confirmacion obligatoria y 1W como contexto.
El SHORT aqui es una simulacion de margen para evaluar la estrategia.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import os
from typing import Any, Optional

import pandas as pd

from data_loader import load_all_timeframes
from indicators import add_indicators
from report import generate_outputs


BACKTEST_PROFILE = os.getenv("BACKTEST_PROFILE", "improved").lower().strip()
INITIAL_CAPITAL = float(os.getenv("BACKTEST_INITIAL_CAPITAL", "5000"))
MIN_CONFIDENCE = float(os.getenv("BACKTEST_MIN_CONFIDENCE", "0.70"))
ADX_THRESHOLD = float(os.getenv("BACKTEST_ADX_THRESHOLD", "20.0"))
VOLUME_HEALTH_MIN = float(os.getenv("BACKTEST_VOLUME_HEALTH_MIN", "0.65"))
MIN_MINUTES_BETWEEN_TRADES = int(os.getenv("BACKTEST_MIN_MINUTES_BETWEEN_TRADES", "60"))
MAX_TRADES_PER_DAY = int(os.getenv("BACKTEST_MAX_TRADES_PER_DAY", "3"))
MAX_RISK_PER_TRADE = float(os.getenv("BACKTEST_MAX_RISK_PER_TRADE", "0.0125"))
MAX_POSITION_BALANCE_PCT = float(os.getenv("BACKTEST_MAX_POSITION_BALANCE_PCT", "0.25"))
KRAKEN_FEE_RATE = float(os.getenv("BACKTEST_FEE_RATE", "0.0026"))
ATR_STOP_MULTIPLIER = float(os.getenv("BACKTEST_ATR_STOP_MULTIPLIER", "1.5"))
ATR_TAKE_PROFIT_MULTIPLIER = float(os.getenv("BACKTEST_ATR_TAKE_PROFIT_MULTIPLIER", "3.0"))
ATR_TRAILING_MULTIPLIER = float(os.getenv("BACKTEST_ATR_TRAILING_MULTIPLIER", "1.5"))
REQUIRE_MTF_MACD_CONFIRM = os.getenv("BACKTEST_REQUIRE_MTF_MACD_CONFIRM", "false").lower().strip() == "true"

if BACKTEST_PROFILE == "improved":
    ADX_THRESHOLD = float(os.getenv("BACKTEST_ADX_THRESHOLD", "25.0"))
    VOLUME_HEALTH_MIN = float(os.getenv("BACKTEST_VOLUME_HEALTH_MIN", "0.75"))
    MIN_MINUTES_BETWEEN_TRADES = int(os.getenv("BACKTEST_MIN_MINUTES_BETWEEN_TRADES", "360"))
    MAX_TRADES_PER_DAY = int(os.getenv("BACKTEST_MAX_TRADES_PER_DAY", "1"))
    ATR_TRAILING_MULTIPLIER = float(os.getenv("BACKTEST_ATR_TRAILING_MULTIPLIER", "3.0"))
    REQUIRE_MTF_MACD_CONFIRM = os.getenv("BACKTEST_REQUIRE_MTF_MACD_CONFIRM", "true").lower().strip() == "true"
EMA_SLOW = 100
MACD_SIGNAL = 10
MIN_REQUIRED_CANDLES = EMA_SLOW + MACD_SIGNAL


@dataclass
class Position:
    side: str
    entry_time: pd.Timestamp
    entry_price: float
    size: float
    stop_loss: float
    initial_stop_loss: float
    take_profit: float
    entry_fee: float
    highest_price: float
    lowest_price: float
    signal_reason: str


def prepare_data(refresh: bool = False) -> dict[str, pd.DataFrame]:
    raw_data = load_all_timeframes(refresh=refresh)
    data: dict[str, pd.DataFrame] = {}
    for label, frame in raw_data.items():
        if frame.empty:
            print(f"ADVERTENCIA: {label} no tiene datos. Se continuara si es posible.")
            data[label] = frame
            continue
        enriched = add_indicators(frame)
        data[label] = enriched.dropna(subset=["ema100", "atr"]).reset_index(drop=True)
        if len(data[label]) < MIN_REQUIRED_CANDLES:
            print(f"ADVERTENCIA: {label} tiene pocas velas utiles: {len(data[label])}.")
    return data


def aligned_slice(frame: pd.DataFrame, timestamp: int) -> pd.DataFrame:
    return frame[frame["time"] <= timestamp]


def latest_row(frame: pd.DataFrame, timestamp: int) -> Optional[pd.Series]:
    historical = aligned_slice(frame, timestamp)
    if len(historical) < MIN_REQUIRED_CANDLES:
        return None
    return historical.iloc[-1]


def row_to_analysis(row: pd.Series) -> dict[str, Any]:
    return {
        "trend": str(row["trend"]),
        "price": float(row["close"]),
        "ema21": float(row["ema21"]),
        "ema50": float(row["ema50"]),
        "ema100": float(row["ema100"]),
        "macd": {
            "macd": float(row["macd"]),
            "signal": float(row["macd_signal"]),
            "hist": float(row["macd_hist"]),
        },
        "adx": float(row["adx"]),
        "volume_ratio": float(row["volume_ratio"]),
        "atr": float(row["atr"]),
    }


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


def build_aligned_frame(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base = data["1H"].sort_values("time").reset_index(drop=True).copy()
    indicator_cols = [
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
    for label, prefix in [("4H", "fourh"), ("1D", "daily"), ("1W", "weekly")]:
        right = data[label][indicator_cols].sort_values("time").reset_index(drop=True).copy()
        right = right.rename(columns={col: f"{prefix}_{col}" for col in indicator_cols if col != "time"})
        base = pd.merge_asof(base, right, on="time", direction="backward")
    return base


def build_signal_from_aligned(row: pd.Series) -> dict[str, Any]:
    required = [
        "weekly_trend",
        "daily_trend",
        "fourh_trend",
        "weekly_ema100",
        "daily_ema100",
        "fourh_ema100",
    ]
    if any(pd.isna(row.get(col)) for col in required):
        return {
            "signal": "WAIT",
            "confidence": 0.0,
            "reason": "No hay suficientes velas alineadas en todos los timeframes.",
            "price": float(row["close"]),
            "atr": float(row["atr"]) if not pd.isna(row["atr"]) else 0.0,
        }

    weekly = prefixed_analysis(row, "weekly")
    daily = prefixed_analysis(row, "daily")
    fourh = prefixed_analysis(row, "fourh")
    hourly = row_to_analysis(row)
    return build_signal_from_analyses(weekly, daily, fourh, hourly)


def build_signal_at(data: dict[str, pd.DataFrame], timestamp: int) -> dict[str, Any]:
    rows = {
        label: latest_row(frame, timestamp)
        for label, frame in data.items()
    }
    if any(row is None for row in rows.values()):
        return {
            "signal": "WAIT",
            "confidence": 0.0,
            "reason": "No hay suficientes velas alineadas en todos los timeframes.",
            "price": 0.0,
            "atr": 0.0,
        }

    weekly = row_to_analysis(rows["1W"])
    daily = row_to_analysis(rows["1D"])
    fourh = row_to_analysis(rows["4H"])
    hourly = row_to_analysis(rows["1H"])

    return build_signal_from_analyses(weekly, daily, fourh, hourly)


def build_signal_from_analyses(weekly: dict[str, Any], daily: dict[str, Any], fourh: dict[str, Any], hourly: dict[str, Any]) -> dict[str, Any]:
    weekly_long_context = weekly["trend"] != "bear" and weekly["price"] >= weekly["ema100"]
    weekly_short_context = weekly["trend"] != "bull" and weekly["price"] <= weekly["ema100"]

    quality_ok = hourly["adx"] >= ADX_THRESHOLD and hourly["volume_ratio"] >= VOLUME_HEALTH_MIN and hourly["atr"] > 0

    long_checks = {
        "1D bullish": daily["trend"] == "bull",
        "4H bullish": fourh["trend"] == "bull",
        "1H bullish": hourly["trend"] == "bull",
        "MACD 1H positivo": hourly["macd"]["hist"] > 0,
        "ADX fuerte": hourly["adx"] >= ADX_THRESHOLD,
        "Volumen saludable": hourly["volume_ratio"] >= VOLUME_HEALTH_MIN,
    }
    short_checks = {
        "1D bearish": daily["trend"] == "bear",
        "4H bearish": fourh["trend"] == "bear",
        "1H bearish": hourly["trend"] == "bear",
        "MACD 1H negativo": hourly["macd"]["hist"] < 0,
        "ADX fuerte": hourly["adx"] >= ADX_THRESHOLD,
        "Volumen saludable": hourly["volume_ratio"] >= VOLUME_HEALTH_MIN,
    }
    weights = [0.24, 0.24, 0.12, 0.12, 0.14, 0.14]
    long_confidence = sum(weight for weight, passed in zip(weights, long_checks.values()) if passed)
    short_confidence = sum(weight for weight, passed in zip(weights, short_checks.values()) if passed)
    mtf_macd_long = daily["macd"]["hist"] > 0 and fourh["macd"]["hist"] > 0
    mtf_macd_short = daily["macd"]["hist"] < 0 and fourh["macd"]["hist"] < 0

    if (
        weekly_long_context
        and quality_ok
        and all(long_checks.values())
        and (mtf_macd_long or not REQUIRE_MTF_MACD_CONFIRM)
        and long_confidence >= MIN_CONFIDENCE
    ):
        return {
            "signal": "LONG",
            "confidence": long_confidence,
            "reason": "Confirmacion 1H/4H/1D alcista, 1W contexto, ADX/volumen OK y MACD MTF confirmado.",
            "price": hourly["price"],
            "atr": hourly["atr"],
            "hourly": hourly,
        }

    if (
        weekly_short_context
        and quality_ok
        and all(short_checks.values())
        and (mtf_macd_short or not REQUIRE_MTF_MACD_CONFIRM)
        and short_confidence >= MIN_CONFIDENCE
    ):
        return {
            "signal": "SHORT",
            "confidence": short_confidence,
            "reason": "Confirmacion 1H/4H/1D bajista, 1W contexto, ADX/volumen OK y MACD MTF confirmado.",
            "price": hourly["price"],
            "atr": hourly["atr"],
            "hourly": hourly,
        }

    return {
        "signal": "WAIT",
        "confidence": max(long_confidence, short_confidence),
        "reason": "Faltan confirmaciones de tendencia, ADX, volumen, contexto 1W o MACD MTF.",
        "price": hourly["price"],
        "atr": hourly["atr"],
        "hourly": hourly,
    }


def calculate_position_size(balance: float, price: float, atr_value: float) -> float:
    if balance <= 0 or price <= 0 or atr_value <= 0:
        return 0.0
    risk_amount = balance * MAX_RISK_PER_TRADE
    stop_distance = atr_value * ATR_STOP_MULTIPLIER
    btc_size = risk_amount / stop_distance
    usd_size = min(btc_size * price, balance * MAX_POSITION_BALANCE_PCT)
    return usd_size / price if usd_size > 0 else 0.0


class Backtester:
    def __init__(self, data: dict[str, pd.DataFrame]) -> None:
        self.data = data
        self.aligned = build_aligned_frame(data)
        self.balance = INITIAL_CAPITAL
        self.position: Optional[Position] = None
        self.trades: list[dict[str, Any]] = []
        self.equity_curve: list[dict[str, Any]] = []
        self.last_trade_time: Optional[pd.Timestamp] = None
        self.daily_trades: dict[date, int] = {}

    def can_open_trade(self, timestamp: pd.Timestamp, ignore_cooldown: bool = False) -> bool:
        day = timestamp.date()
        if self.daily_trades.get(day, 0) >= MAX_TRADES_PER_DAY:
            return False
        if ignore_cooldown:
            return True
        if self.last_trade_time is None:
            return True
        elapsed_minutes = (timestamp - self.last_trade_time).total_seconds() / 60
        return elapsed_minutes >= MIN_MINUTES_BETWEEN_TRADES

    def register_open(self, timestamp: pd.Timestamp) -> None:
        self.last_trade_time = timestamp
        day = timestamp.date()
        self.daily_trades[day] = self.daily_trades.get(day, 0) + 1

    def open_position(self, signal: dict[str, Any], candle: pd.Series) -> None:
        side = signal["signal"]
        entry_price = float(candle["close"])
        atr_value = float(signal["atr"])
        size = calculate_position_size(self.balance, entry_price, atr_value)
        if size <= 0:
            return

        if side == "LONG":
            stop_loss = entry_price - atr_value * ATR_STOP_MULTIPLIER
            take_profit = entry_price + atr_value * ATR_TAKE_PROFIT_MULTIPLIER
        else:
            stop_loss = entry_price + atr_value * ATR_STOP_MULTIPLIER
            take_profit = entry_price - atr_value * ATR_TAKE_PROFIT_MULTIPLIER

        self.position = Position(
            side=side,
            entry_time=candle["datetime"],
            entry_price=entry_price,
            size=size,
            stop_loss=stop_loss,
            initial_stop_loss=stop_loss,
            take_profit=take_profit,
            entry_fee=entry_price * size * KRAKEN_FEE_RATE,
            highest_price=entry_price,
            lowest_price=entry_price,
            signal_reason=signal["reason"],
        )
        self.register_open(candle["datetime"])

    def update_trailing_stop(self, candle: pd.Series) -> None:
        if self.position is None or float(candle["adx"]) < ADX_THRESHOLD:
            return
        atr_value = float(candle["atr"])
        if atr_value <= 0:
            return
        if self.position.side == "LONG":
            self.position.highest_price = max(self.position.highest_price, float(candle["high"]))
            trailing_stop = self.position.highest_price - atr_value * ATR_TRAILING_MULTIPLIER
            self.position.stop_loss = max(self.position.stop_loss, trailing_stop)
        else:
            self.position.lowest_price = min(self.position.lowest_price, float(candle["low"]))
            trailing_stop = self.position.lowest_price + atr_value * ATR_TRAILING_MULTIPLIER
            self.position.stop_loss = min(self.position.stop_loss, trailing_stop)

    def check_price_exit(self, candle: pd.Series) -> tuple[Optional[str], Optional[float]]:
        if self.position is None:
            return None, None
        high = float(candle["high"])
        low = float(candle["low"])
        if self.position.side == "LONG":
            if low <= self.position.stop_loss:
                reason = "TRAILING_STOP" if self.position.stop_loss > self.position.initial_stop_loss else "STOP_LOSS"
                return reason, self.position.stop_loss
            if high >= self.position.take_profit:
                return "TAKE_PROFIT", self.position.take_profit
        else:
            if high >= self.position.stop_loss:
                reason = "TRAILING_STOP" if self.position.stop_loss < self.position.initial_stop_loss else "STOP_LOSS"
                return reason, self.position.stop_loss
            if low <= self.position.take_profit:
                return "TAKE_PROFIT", self.position.take_profit
        return None, None

    def close_position(self, candle: pd.Series, exit_price: float, reason: str) -> None:
        if self.position is None:
            return
        pos = self.position
        gross_pnl = (exit_price - pos.entry_price) * pos.size if pos.side == "LONG" else (pos.entry_price - exit_price) * pos.size
        exit_fee = exit_price * pos.size * KRAKEN_FEE_RATE
        fee_total = pos.entry_fee + exit_fee
        net_pnl = gross_pnl - fee_total
        self.balance += net_pnl
        exit_time = candle["datetime"]
        duration_hours = (exit_time - pos.entry_time).total_seconds() / 3600

        self.trades.append({
            "entry_time": pos.entry_time,
            "exit_time": exit_time,
            "side": pos.side,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "size": pos.size,
            "pnl_gross": gross_pnl,
            "pnl_net": net_pnl,
            "fee_total": fee_total,
            "exit_reason": reason,
            "duration_hours": duration_hours,
            "signal_reason": pos.signal_reason,
        })
        self.position = None
        self.last_trade_time = exit_time

    def current_equity(self, close_price: float) -> float:
        if self.position is None:
            return self.balance
        unrealized = (
            (close_price - self.position.entry_price) * self.position.size
            if self.position.side == "LONG"
            else (self.position.entry_price - close_price) * self.position.size
        )
        return self.balance + unrealized

    def record_equity(self, candle: pd.Series) -> None:
        equity = self.current_equity(float(candle["close"]))
        peak = max([row["equity"] for row in self.equity_curve], default=INITIAL_CAPITAL)
        peak = max(peak, equity)
        drawdown_pct = ((equity - peak) / peak * 100) if peak else 0.0
        self.equity_curve.append({
            "time": candle["datetime"],
            "equity": equity,
            "peak": peak,
            "drawdown_pct": drawdown_pct,
        })

    def run(self) -> tuple[pd.DataFrame, pd.DataFrame, float]:
        candles_1h = self.aligned
        for _, candle in candles_1h.iterrows():
            exit_reason, exit_price = self.check_price_exit(candle)
            if exit_reason and exit_price is not None:
                self.close_position(candle, exit_price, exit_reason)
            if self.position is not None:
                self.update_trailing_stop(candle)

            signal = build_signal_from_aligned(candle)
            allow_immediate_reversal = False
            if self.position is not None:
                opposite = (
                    self.position.side == "LONG" and signal["signal"] == "SHORT"
                    or self.position.side == "SHORT" and signal["signal"] == "LONG"
                )
                if opposite and signal["confidence"] >= MIN_CONFIDENCE:
                    self.close_position(candle, float(candle["close"]), f"REVERSAL_TO_{signal['signal']}")
                    allow_immediate_reversal = True

            if (
                self.position is None
                and signal["signal"] in {"LONG", "SHORT"}
                and self.can_open_trade(candle["datetime"], ignore_cooldown=allow_immediate_reversal)
            ):
                self.open_position(signal, candle)

            self.record_equity(candle)

        if self.position is not None and not candles_1h.empty:
            final_candle = candles_1h.iloc[-1]
            self.close_position(final_candle, float(final_candle["close"]), "END_OF_BACKTEST")
            self.record_equity(final_candle)

        return pd.DataFrame(self.trades), pd.DataFrame(self.equity_curve), self.balance


def main() -> None:
    refresh_data = os.getenv("BACKTEST_REFRESH_DATA", "false").lower().strip() == "true"
    data = prepare_data(refresh=refresh_data)
    if any(frame.empty for frame in data.values()):
        print("ADVERTENCIA: faltan datos en uno o mas timeframes. El resultado puede ser incompleto.")
    backtester = Backtester(data)
    trades, equity_curve, final_capital = backtester.run()
    metadata = {
        "perfil": BACKTEST_PROFILE,
        "fee_rate": KRAKEN_FEE_RATE,
        "adx_threshold": ADX_THRESHOLD,
        "volume_min": VOLUME_HEALTH_MIN,
        "max_trades_per_day": MAX_TRADES_PER_DAY,
        "cooldown_minutes": MIN_MINUTES_BETWEEN_TRADES,
        "trailing_atr": ATR_TRAILING_MULTIPLIER,
        "require_mtf_macd": REQUIRE_MTF_MACD_CONFIRM,
    }
    generate_outputs(trades, equity_curve, data["1H"], INITIAL_CAPITAL, final_capital, metadata=metadata)


if __name__ == "__main__":
    main()
