from __future__ import annotations

import numpy as np
import pandas as pd


def ema(values: pd.Series, period: int) -> pd.Series:
    """EMA estandar sobre la serie completa."""
    return values.astype(float).ewm(span=period, adjust=False).mean()


def macd(values: pd.Series, fast: int = 21, slow: int = 50, signal: int = 10) -> pd.DataFrame:
    """MACD estandar: EMA rapida - EMA lenta, con senal EMA sobre toda la linea MACD."""
    close = values.astype(float)
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "hist": macd_line - signal_line,
    })


def true_range(candles: pd.DataFrame) -> pd.Series:
    high = candles["high"].astype(float)
    low = candles["low"].astype(float)
    prev_close = candles["close"].astype(float).shift(1)
    ranges = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1)
    return ranges.max(axis=1)


def atr(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    """ATR real usando high/low/close y suavizado Wilder/RMA."""
    return true_range(candles).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def adx(candles: pd.DataFrame, period: int = 14) -> pd.Series:
    """ADX real con suavizado de Wilder para TR, +DM, -DM y DX."""
    high = candles["high"].astype(float)
    low = candles["low"].astype(float)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=candles.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=candles.index)

    tr_rma = true_range(candles).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    plus_rma = plus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    minus_rma = minus_dm.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    plus_di = 100 * plus_rma / tr_rma.replace(0, np.nan)
    minus_di = 100 * minus_rma / tr_rma.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False, min_periods=period).mean().fillna(0.0)


def bollinger(values: pd.Series, period: int = 20, mult: float = 2.0) -> pd.DataFrame:
    close = values.astype(float)
    middle = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    upper = middle + mult * std
    lower = middle - mult * std
    width_pct = ((upper - lower) / middle.replace(0, np.nan)) * 100
    return pd.DataFrame({
        "upper": upper,
        "middle": middle,
        "lower": lower,
        "width_pct": width_pct,
    })


def volume_ratio(candles: pd.DataFrame, period: int = 20) -> pd.Series:
    volume = candles["volume"].astype(float)
    avg = volume.shift(1).rolling(period).mean()
    return (volume / avg.replace(0, np.nan)).fillna(1.0)


def add_indicators(candles: pd.DataFrame) -> pd.DataFrame:
    output = candles.copy()
    close = output["close"].astype(float)
    output["ema21"] = ema(close, 21)
    output["ema50"] = ema(close, 50)
    output["ema100"] = ema(close, 100)
    macd_data = macd(close)
    output["macd"] = macd_data["macd"]
    output["macd_signal"] = macd_data["signal"]
    output["macd_hist"] = macd_data["hist"]
    output["atr"] = atr(output, 14)
    output["adx"] = adx(output, 14)
    output["volume_ratio"] = volume_ratio(output, 20)
    output["bollinger_width_pct"] = bollinger(close)["width_pct"]
    output["trend"] = np.select(
        [
            (output["ema21"] > output["ema50"]) & (close > output["ema100"]),
            (output["ema21"] < output["ema50"]) & (close < output["ema100"]),
        ],
        ["bull", "bear"],
        default="neutral",
    )
    return output
