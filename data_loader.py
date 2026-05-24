from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd
import requests


KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
COINBASE_CANDLES_URL = "https://api.exchange.coinbase.com/products/{product_id}/candles"
DATA_DIR = Path("data")
PAIR = "XBTUSD"
COINBASE_PRODUCT_ID = os.getenv("BACKTEST_COINBASE_PRODUCT_ID", "BTC-USD")
START_DATE = "2021-01-01"
DATA_SOURCE = os.getenv("BACKTEST_DATA_SOURCE", "coinbase").lower().strip()
KRAKEN_REQUEST_SLEEP = float(os.getenv("KRAKEN_REQUEST_SLEEP", "2.0"))
COINBASE_REQUEST_SLEEP = float(os.getenv("COINBASE_REQUEST_SLEEP", "0.35"))
INTERVALS: Dict[str, int] = {
    "15M": 15,
    "1H": 60,
    "4H": 240,
    "1D": 1440,
    "1W": 10080,
}
COINBASE_RESAMPLE_RULES = {
    "4H": "4h",
    "1D": "1D",
    "1W": "1W",
}


def start_timestamp() -> int:
    return int(datetime.fromisoformat(START_DATE).replace(tzinfo=timezone.utc).timestamp())


def csv_path(label: str) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
    if DATA_SOURCE == "coinbase":
        safe_product = COINBASE_PRODUCT_ID.replace("-", "")
        return DATA_DIR / f"coinbase_{safe_product}_{label}.csv"
    return DATA_DIR / f"kraken_{PAIR}_{label}.csv"


def parse_kraken_rows(rows: list[list[object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["time", "open", "high", "low", "close", "vwap", "volume", "count"])
    if frame.empty:
        return frame
    numeric_cols = ["time", "open", "high", "low", "close", "vwap", "volume", "count"]
    for col in numeric_cols:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["time", "open", "high", "low", "close"]).drop_duplicates(subset=["time"])
    frame["time"] = frame["time"].astype(int)
    frame["datetime"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    return frame.sort_values("time").reset_index(drop=True)


def extract_rows(payload: dict) -> list[list[object]]:
    result = payload.get("result", {})
    pair_key = next((key for key in result.keys() if key != "last"), "")
    return result.get(pair_key, []) if pair_key else []


def fetch_ohlc_page(interval: int, since: int) -> tuple[list[list[object]], int]:
    response = requests.get(
        KRAKEN_OHLC_URL,
        params={"pair": PAIR, "interval": interval, "since": since},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    errors = payload.get("error") or []
    if errors:
        raise RuntimeError(f"Kraken OHLC error: {errors}")
    result = payload.get("result", {})
    rows = extract_rows(payload)
    last = int(result.get("last", since))
    return rows, last


def download_ohlc(label: str, interval: int) -> pd.DataFrame:
    if DATA_SOURCE == "coinbase":
        return download_coinbase_ohlc(label, interval)
    return download_kraken_ohlc(label, interval)


def download_kraken_ohlc(label: str, interval: int) -> pd.DataFrame:
    print(f"Descargando {label} desde Kraken...")
    since = start_timestamp()
    all_rows: list[list[object]] = []
    seen = set()
    empty_pages = 0

    while True:
        rows, last = fetch_ohlc_page(interval, since)
        new_rows = []
        for row in rows:
            if not row:
                continue
            candle_time = int(float(row[0]))
            if candle_time not in seen:
                seen.add(candle_time)
                new_rows.append(row)

        all_rows.extend(new_rows)
        if rows:
            since = int(float(rows[-1][0])) + interval * 60
        else:
            since = last

        if not new_rows:
            empty_pages += 1
        else:
            empty_pages = 0

        if not rows or empty_pages >= 2:
            break
        if rows and int(float(rows[-1][0])) >= int(time.time()) - interval * 60:
            break

        time.sleep(KRAKEN_REQUEST_SLEEP)

    frame = parse_kraken_rows(all_rows)
    path = csv_path(label)
    frame.to_csv(path, index=False)
    print(f"Guardado {path} con {len(frame)} velas.")
    return frame


def parse_coinbase_rows(rows: list[list[object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    if frame.empty:
        return frame
    for col in ["time", "low", "high", "open", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame = frame.dropna(subset=["time", "open", "high", "low", "close"]).drop_duplicates(subset=["time"])
    frame["time"] = frame["time"].astype(int)
    frame["vwap"] = 0.0
    frame["count"] = 0
    frame["datetime"] = pd.to_datetime(frame["time"], unit="s", utc=True)
    return frame[["time", "open", "high", "low", "close", "vwap", "volume", "count", "datetime"]].sort_values("time").reset_index(drop=True)


def fetch_coinbase_page(interval: int, start_ts: int, end_ts: int) -> list[list[object]]:
    url = COINBASE_CANDLES_URL.format(product_id=COINBASE_PRODUCT_ID)
    response = requests.get(
        url,
        params={
            "granularity": interval * 60,
            "start": datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat(),
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def download_coinbase_ohlc(label: str, interval: int) -> pd.DataFrame:
    print(f"Descargando {label} desde Coinbase para {COINBASE_PRODUCT_ID}...")
    step_seconds = interval * 60 * 300
    current_start = start_timestamp()
    now = int(time.time())
    all_rows: list[list[object]] = []
    seen = set()

    while current_start < now:
        current_end = min(current_start + step_seconds, now)
        rows = fetch_coinbase_page(interval, current_start, current_end)
        for row in rows:
            if not row:
                continue
            candle_time = int(float(row[0]))
            if candle_time not in seen:
                seen.add(candle_time)
                all_rows.append(row)
        current_start = current_end
        time.sleep(COINBASE_REQUEST_SLEEP)

    frame = parse_coinbase_rows(all_rows)
    path = csv_path(label)
    frame.to_csv(path, index=False)
    print(f"Guardado {path} con {len(frame)} velas.")
    return frame


def load_ohlc(label: str, interval: int, refresh: bool = False) -> pd.DataFrame:
    path = csv_path(label)
    if path.exists() and not refresh:
        frame = pd.read_csv(path)
        frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
        return frame.sort_values("time").reset_index(drop=True)
    return download_ohlc(label, interval)


def resample_from_1h(frame_1h: pd.DataFrame, label: str) -> pd.DataFrame:
    rule = COINBASE_RESAMPLE_RULES[label]
    source = frame_1h.copy()
    source["datetime"] = pd.to_datetime(source["datetime"], utc=True)
    source = source.set_index("datetime").sort_index()
    resampled = source.resample(rule).agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "count": "sum",
    }).dropna(subset=["open", "high", "low", "close"])
    resampled["time"] = [int(timestamp.timestamp()) for timestamp in resampled.index]
    resampled["vwap"] = 0.0
    resampled["datetime"] = resampled.index
    output = resampled[["time", "open", "high", "low", "close", "vwap", "volume", "count", "datetime"]].reset_index(drop=True)
    path = csv_path(label)
    output.to_csv(path, index=False)
    print(f"Generado {path} con {len(output)} velas desde 1H.")
    return output


def load_all_timeframes(refresh: bool = False) -> dict[str, pd.DataFrame]:
    if DATA_SOURCE == "coinbase":
        frame_1h = load_ohlc("1H", INTERVALS["1H"], refresh=refresh)
        data = {"1H": frame_1h}
        for label in ["4H", "1D", "1W"]:
            path = csv_path(label)
            if path.exists() and not refresh:
                frame = pd.read_csv(path)
                frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
                data[label] = frame.sort_values("time").reset_index(drop=True)
            else:
                data[label] = resample_from_1h(frame_1h, label)
            if data[label].empty:
                print(f"ADVERTENCIA: no hay datos para {label}. Se continuara con los datos disponibles.")
        return data

    data = {}
    for label, interval in INTERVALS.items():
        frame = load_ohlc(label, interval, refresh=refresh)
        if frame.empty:
            print(f"ADVERTENCIA: no hay datos para {label}. Se continuara con los datos disponibles.")
        data[label] = frame
    return data
