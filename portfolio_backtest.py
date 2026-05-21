#!/usr/bin/env python3
"""Backtest rapido de portafolio multi-cripto para el bot."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from indicators import add_indicators


DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
ASSETS = {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "BCH": "BCH-USD", "LTC": "LTC-USD"}
URL = "https://api.exchange.coinbase.com/products/{}/candles"
START_TS = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())
NOW = int(time.time())

INITIAL = 5000.0
FEE_RATE = float(os.getenv("PORTFOLIO_FEE_RATE", "0.0005"))
MAX_OPEN = 4
MAX_TRADES_DAY = 10
MAX_RISK = 0.0125
MAX_POSITION_PCT = 0.25
LEVERAGE = 3.0
MIN_CONFIDENCE = 0.70
ADX_THRESHOLD = 20.0
VOLUME_MIN = 0.65
COOLDOWN_MINUTES = 60
SL_ATR = 1.5
TP_ATR = 3.0
TRAIL_ATR = 1.5


def csv_path(symbol: str, timeframe: str) -> Path:
    return DATA_DIR / f"coinbase_{ASSETS[symbol].replace('-', '')}_{timeframe}.csv"


def parse_rows(rows: list[list[object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    for col in ["time", "low", "high", "open", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["time", "open", "high", "low", "close"]).drop_duplicates("time")
    frame["time"] = frame["time"].astype(int)
    frame["vwap"] = 0.0
    frame["count"] = 0
    frame["datetime"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    return frame[["time", "open", "high", "low", "close", "vwap", "volume", "count", "datetime"]].sort_values("time").reset_index(drop=True)


def load_1h(symbol: str) -> pd.DataFrame:
    path = csv_path(symbol, "1H")
    if path.exists():
        frame = pd.read_csv(path)
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
        return frame
    rows: list[list[object]] = []
    seen = set()
    start = START_TS
    step = 3600 * 300
    print(f"Descargando {symbol} {ASSETS[symbol]}...")
    while start < NOW:
        end = min(start + step, NOW)
        response = requests.get(
            URL.format(ASSETS[symbol]),
            params={
                "granularity": 3600,
                "start": datetime.fromtimestamp(start, tz=timezone.utc).isoformat(),
                "end": datetime.fromtimestamp(end, tz=timezone.utc).isoformat(),
            },
            timeout=30,
        )
        response.raise_for_status()
        for row in response.json():
            candle_time = int(float(row[0]))
            if candle_time not in seen:
                seen.add(candle_time)
                rows.append(row)
        start = end
        time.sleep(0.25)
    frame = parse_rows(rows)
    frame.to_csv(path, index=False)
    return frame


def resample(frame_1h: pd.DataFrame, symbol: str, timeframe: str) -> pd.DataFrame:
    path = csv_path(symbol, timeframe)
    if path.exists():
        frame = pd.read_csv(path)
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
        return frame
    rule = {"4H": "4h", "1D": "1D", "1W": "1W"}[timeframe]
    source = frame_1h.copy()
    source["datetime"] = pd.to_datetime(source["datetime"], utc=True)
    source = source.set_index("datetime").sort_index()
    out = source.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "count": "sum"})
    out = out.dropna(subset=["open", "high", "low", "close"])
    out["time"] = [int(ts.timestamp()) for ts in out.index]
    out["vwap"] = 0.0
    out["datetime"] = out.index
    out = out[["time", "open", "high", "low", "close", "vwap", "volume", "count", "datetime"]].reset_index(drop=True)
    out.to_csv(path, index=False)
    return out


def prepared_symbol(symbol: str) -> pd.DataFrame:
    raw_1h = load_1h(symbol)
    data = {
        "1H": add_indicators(raw_1h).dropna(subset=["ema100", "atr"]).reset_index(drop=True),
        "4H": add_indicators(resample(raw_1h, symbol, "4H")).dropna(subset=["ema100", "atr"]).reset_index(drop=True),
        "1D": add_indicators(resample(raw_1h, symbol, "1D")).dropna(subset=["ema100", "atr"]).reset_index(drop=True),
        "1W": add_indicators(resample(raw_1h, symbol, "1W")).dropna(subset=["ema100", "atr"]).reset_index(drop=True),
    }
    base = data["1H"].sort_values("time").reset_index(drop=True)
    cols = ["time", "trend", "close", "ema100", "macd_hist", "adx", "volume_ratio", "atr"]
    for timeframe, prefix in [("4H", "fourh"), ("1D", "daily"), ("1W", "weekly")]:
        right = data[timeframe][cols].sort_values("time").reset_index(drop=True)
        right = right.rename(columns={col: f"{prefix}_{col}" for col in cols if col != "time"})
        base = pd.merge_asof(base, right, on="time", direction="backward")
    base["symbol"] = symbol
    return base


def build_signal(row: pd.Series) -> tuple[str, float]:
    required = ["weekly_trend", "daily_trend", "fourh_trend", "weekly_ema100", "daily_ema100", "fourh_ema100"]
    if any(pd.isna(row.get(col)) for col in required):
        return "WAIT", 0.0
    weekly_long = row["weekly_trend"] != "bear" and row["weekly_close"] >= row["weekly_ema100"]
    weekly_short = row["weekly_trend"] != "bull" and row["weekly_close"] <= row["weekly_ema100"]
    quality = row["adx"] >= ADX_THRESHOLD and row["volume_ratio"] >= VOLUME_MIN and row["atr"] > 0
    long_checks = [
        row["daily_trend"] == "bull",
        row["fourh_trend"] == "bull",
        row["trend"] == "bull",
        row["macd_hist"] > 0,
        row["adx"] >= ADX_THRESHOLD,
        row["volume_ratio"] >= VOLUME_MIN,
    ]
    short_checks = [
        row["daily_trend"] == "bear",
        row["fourh_trend"] == "bear",
        row["trend"] == "bear",
        row["macd_hist"] < 0,
        row["adx"] >= ADX_THRESHOLD,
        row["volume_ratio"] >= VOLUME_MIN,
    ]
    weights = [0.24, 0.24, 0.12, 0.12, 0.14, 0.14]
    long_conf = sum(weight for weight, ok in zip(weights, long_checks) if ok)
    short_conf = sum(weight for weight, ok in zip(weights, short_checks) if ok)
    if weekly_long and quality and all(long_checks) and long_conf >= MIN_CONFIDENCE:
        return "LONG", long_conf
    if weekly_short and quality and all(short_checks) and short_conf >= MIN_CONFIDENCE:
        return "SHORT", short_conf
    return "WAIT", max(long_conf, short_conf)


def main() -> None:
    rows = pd.concat([prepared_symbol(symbol) for symbol in ASSETS], ignore_index=True).sort_values(["time", "symbol"])
    balance = INITIAL
    positions: dict[str, dict] = {}
    latest_prices: dict[str, float] = {}
    daily_trades: dict[str, int] = {}
    last_trade_ts = 0
    trades: list[dict] = []
    equity: list[dict] = []

    for timestamp, group in rows.groupby("time", sort=True):
        dt = group.iloc[0]["datetime"]
        day = str(pd.to_datetime(dt).date())
        for _, row in group.iterrows():
            symbol = row["symbol"]
            latest_prices[symbol] = float(row["close"])
            if symbol not in positions:
                continue
            pos = positions[symbol]
            high = float(row["high"])
            low = float(row["low"])
            atr = float(row["atr"])
            exit_reason = None
            exit_price = 0.0
            if pos["side"] == "LONG":
                if low <= pos["stop"]:
                    exit_reason, exit_price = ("TRAILING_STOP" if pos["stop"] > pos["initial_stop"] else "STOP_LOSS"), pos["stop"]
                elif high >= pos["take"]:
                    exit_reason, exit_price = "TAKE_PROFIT", pos["take"]
            else:
                if high >= pos["stop"]:
                    exit_reason, exit_price = ("TRAILING_STOP" if pos["stop"] < pos["initial_stop"] else "STOP_LOSS"), pos["stop"]
                elif low <= pos["take"]:
                    exit_reason, exit_price = "TAKE_PROFIT", pos["take"]
            if exit_reason:
                gross = (exit_price - pos["entry"]) * pos["size"] if pos["side"] == "LONG" else (pos["entry"] - exit_price) * pos["size"]
                fee = (pos["entry"] * pos["size"] + exit_price * pos["size"]) * FEE_RATE
                net = gross - fee
                balance += net
                trades.append({**pos, "exit": exit_price, "exit_time": dt, "gross": gross, "fee": fee, "net": net, "reason": exit_reason})
                del positions[symbol]
            elif row["adx"] >= ADX_THRESHOLD and atr > 0:
                if pos["side"] == "LONG":
                    pos["highest"] = max(pos["highest"], high)
                    pos["stop"] = max(pos["stop"], pos["highest"] - atr * TRAIL_ATR)
                else:
                    pos["lowest"] = min(pos["lowest"], low)
                    pos["stop"] = min(pos["stop"], pos["lowest"] + atr * TRAIL_ATR)

        candidates = []
        if len(positions) < MAX_OPEN and daily_trades.get(day, 0) < MAX_TRADES_DAY:
            for _, row in group.iterrows():
                if row["symbol"] in positions:
                    continue
                side, confidence = build_signal(row)
                if side in {"LONG", "SHORT"}:
                    candidates.append((confidence, side, row))
        candidates.sort(key=lambda item: item[0], reverse=True)
        for confidence, side, row in candidates:
            if len(positions) >= MAX_OPEN or daily_trades.get(day, 0) >= MAX_TRADES_DAY:
                break
            if last_trade_ts and timestamp - last_trade_ts < COOLDOWN_MINUTES * 60 and not positions:
                continue
            price = float(row["close"])
            atr = float(row["atr"])
            risk_amount = balance * MAX_RISK
            size = min((risk_amount / (atr * SL_ATR)) * price, balance * MAX_POSITION_PCT * LEVERAGE) / price
            if side == "LONG":
                stop, take = price - atr * SL_ATR, price + atr * TP_ATR
            else:
                stop, take = price + atr * SL_ATR, price - atr * TP_ATR
            positions[row["symbol"]] = {
                "symbol": row["symbol"],
                "side": side,
                "entry_time": row["datetime"],
                "entry": price,
                "size": size,
                "stop": stop,
                "initial_stop": stop,
                "take": take,
                "highest": price,
                "lowest": price,
                "confidence": confidence,
            }
            daily_trades[day] = daily_trades.get(day, 0) + 1
            last_trade_ts = timestamp

        account_equity = balance
        for symbol, pos in positions.items():
            price = latest_prices.get(symbol, pos["entry"])
            account_equity += (price - pos["entry"]) * pos["size"] if pos["side"] == "LONG" else (pos["entry"] - price) * pos["size"]
        peak = max([item["equity"] for item in equity], default=INITIAL)
        peak = max(peak, account_equity)
        equity.append({"time": dt, "equity": account_equity, "drawdown": (account_equity - peak) / peak * 100})

    trades_frame = pd.DataFrame(trades)
    equity_frame = pd.DataFrame(equity)
    months = (pd.to_datetime(rows["datetime"].max()) - pd.to_datetime(rows["datetime"].min())).days / 30.4375
    print("PORTFOLIO BACKTEST BTC ETH SOL BCH LTC")
    print(f"capital_final={balance:.2f}")
    print(f"pnl_pct={(balance - INITIAL) / INITIAL * 100:.2f}")
    print(f"trades={len(trades_frame)}")
    print(f"trades_per_month={len(trades_frame) / months:.2f}")
    print(f"max_drawdown={equity_frame['drawdown'].min():.2f}")
    if not trades_frame.empty:
        print(f"win_rate={(trades_frame['net'] > 0).mean() * 100:.2f}")
        print(f"gross_pnl={trades_frame['gross'].sum():.2f}")
        print(f"fees={trades_frame['fee'].sum():.2f}")
        print(f"net_pnl={trades_frame['net'].sum():.2f}")
        print("\\nBY SYMBOL")
        print(trades_frame.groupby("symbol").agg(trades=("net", "count"), win_rate=("net", lambda s: (s > 0).mean() * 100), pnl=("net", "sum")).to_string())
        print("\\nBY SIDE")
        print(trades_frame.groupby("side").agg(trades=("net", "count"), win_rate=("net", lambda s: (s > 0).mean() * 100), pnl=("net", "sum")).to_string())
        print("\\nEXIT REASONS")
        print(trades_frame["reason"].value_counts().to_string())


if __name__ == "__main__":
    main()
