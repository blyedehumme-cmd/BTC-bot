#!/usr/bin/env python3
"""
Genera contexto HMM para el bot en paper trading.

El archivo de salida puede ser leído por btc_bot.py usando HMM_REGIME_CONTEXT_FILE.
El HMM no genera entradas; solo clasifica el régimen estadístico actual.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from data_loader import load_ohlc
from hmm.model import HMMUnavailableError
from hmm.regimes import train_and_assign_regimes
from indicators import add_indicators


OUTPUT_FILE = Path(os.getenv("HMM_CONTEXT_OUTPUT", "hmm_context.json"))
SYMBOL = os.getenv("HMM_CONTEXT_SYMBOL", "BTC").strip().upper()
PRIMARY_TIMEFRAME = os.getenv("HMM_CONTEXT_PRIMARY_TIMEFRAME", "4H").strip().upper()
CONTEXT_TIMEFRAME = os.getenv("HMM_CONTEXT_HIGHER_TIMEFRAME", "1D").strip().upper()
MIN_STATES = int(os.getenv("HMM_MIN_STATES", "2"))
MAX_STATES = int(os.getenv("HMM_MAX_STATES", "5"))
INTERVAL_BY_TIMEFRAME = {
    "15M": 15,
    "1H": 60,
    "4H": 240,
    "1D": 1440,
    "1W": 10080,
}


def load_prepared(timeframe: str):
    frame = load_ohlc(timeframe, INTERVAL_BY_TIMEFRAME[timeframe], refresh=False)
    if frame.empty:
        raise RuntimeError(f"No hay datos para {timeframe}.")
    return add_indicators(frame).dropna(subset=["ema100", "atr"]).reset_index(drop=True)


def main() -> None:
    try:
        primary = load_prepared(PRIMARY_TIMEFRAME)
        context = load_prepared(CONTEXT_TIMEFRAME)
        regimes, fit = train_and_assign_regimes(
            primary,
            context=context,
            context_prefix=CONTEXT_TIMEFRAME.lower(),
            min_states=MIN_STATES,
            max_states=MAX_STATES,
        )
        latest = regimes.iloc[-1]
        payload = {
            SYMBOL: {
                "regime": int(latest["regime"]),
                "label": str(latest["regime_label"]),
                "source": "hmm_live_context",
                "primary_timeframe": PRIMARY_TIMEFRAME,
                "context_timeframe": CONTEXT_TIMEFRAME,
                "states": int(fit.n_states),
                "bic": float(fit.bic),
                "as_of": str(latest["datetime"]),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "warning": (
                    "HMM es contexto historico/in-sample. No es una senal principal "
                    "y no garantiza resultados futuros."
                ),
            }
        }
        OUTPUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"HMM context escrito en {OUTPUT_FILE}: {payload[SYMBOL]}")
    except HMMUnavailableError as exc:
        raise SystemExit(f"HMM no disponible: {exc}") from exc


if __name__ == "__main__":
    main()
