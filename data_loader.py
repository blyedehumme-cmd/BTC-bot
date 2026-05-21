from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd
import requests


KRAKEN_OHLC_URL = "https://api.kraken.com/0/public/OHLC"
DATA_DIR = Path("data")
PAIR = "XBTUSD"
START_DATE = "2021-01-01"
INTERVALS: Dict[str, int] = {
    "1H": 60,
    "4H": 240,
    "1D": 1440,
    "1W": 10080,
}


def start_timestamp() -> int:
    return int(datetime.fromisoformat(START_DATE).replace(tzinfo=timezone.utc).timestamp())


def csv_path(label: str) -> Path:
    DATA_DIR.mkdir(exist_ok=True)
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

        time.sleep(1)

    frame = parse_kraken_rows(all_rows)
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


def load_all_timeframes(refresh: bool = False) -> dict[str, pd.DataFrame]:
    data = {}
    for label, interval in INTERVALS.items():
        frame = load_ohlc(label, interval, refresh=refresh)
        if frame.empty:
            print(f"ADVERTENCIA: no hay datos para {label}. Se continuara con los datos disponibles.")
        data[label] = frame
    return data
