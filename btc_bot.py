#!/usr/bin/env python3
"""
BTC Bot Seguro Avanzado - paper trading multi-timeframe.

Mantiene compatibilidad con diagnose.py y con el backend FastAPI existente:
- POST /api/signals/
- POST /api/market/snapshots/
- POST /api/ai/decisions/
- POST /api/trades/

Notas de seguridad:
- DRY_RUN=true por defecto.
- En Coinbase spot, SHORT real no abre una posicion corta; venderia BTC disponible.
  Por eso las senales SHORT reales se bloquean salvo ALLOW_REAL_SPOT_SHORT=true.
"""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import math
import os
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode

import requests
from coinbase.rest import RESTClient
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# =========================
# CONFIGURACION
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
TELEGRAM_POLLING_ENABLED = os.getenv("TELEGRAM_POLLING_ENABLED", "false").lower().strip() == "true"
CB_API_KEY = os.getenv("CB_API_KEY", "").strip()
CB_API_SECRET = os.getenv("CB_API_SECRET", "").strip().replace("\\n", "\n")
EXCHANGE = os.getenv("EXCHANGE", "kraken").strip().lower()
EXCHANGE_MODE = os.getenv("EXCHANGE_MODE", "futures").strip().lower()
PRODUCT_ID = os.getenv("PRODUCT_ID", "BTC-USDC").strip()
KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "").strip()
KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "").strip()
KRAKEN_PAIR = os.getenv("KRAKEN_PAIR", "XBTUSD").strip()
KRAKEN_FUTURES_SYMBOL = os.getenv("KRAKEN_FUTURES_SYMBOL", "PI_XBTUSD").strip()
KRAKEN_BASE_ASSET = os.getenv("KRAKEN_BASE_ASSET", "XXBT").strip()
KRAKEN_QUOTE_ASSET = os.getenv("KRAKEN_QUOTE_ASSET", "ZUSD").strip()
KRAKEN_API_URL = os.getenv("KRAKEN_API_URL", "https://api.kraken.com").strip().rstrip("/")
KRAKEN_FUTURES_API_URL = os.getenv("KRAKEN_FUTURES_API_URL", "https://futures.kraken.com").strip().rstrip("/")
WATCHLIST = [item.strip().upper() for item in os.getenv("WATCHLIST", "BTC").split(",") if item.strip()]
DRY_RUN = os.getenv("DRY_RUN", "true").lower().strip() == "true"
RUN_ONCE = os.getenv("RUN_ONCE", "false").lower().strip() == "true"
ALLOW_REAL_SPOT_SHORT = os.getenv("ALLOW_REAL_SPOT_SHORT", "false").lower().strip() == "true"
ALLOW_SHORT_SIGNALS = os.getenv("ALLOW_SHORT_SIGNALS", "true").lower().strip() == "true"
USE_CLOSED_CANDLES = os.getenv("USE_CLOSED_CANDLES", "true").lower().strip() == "true"
MAX_ALLOWED_LEVERAGE = 3.0
MAX_LEVERAGE = max(1.0, min(float(os.getenv("MAX_LEVERAGE", "3.0")), MAX_ALLOWED_LEVERAGE))
DYNAMIC_LEVERAGE_ENABLED = os.getenv("DYNAMIC_LEVERAGE_ENABLED", "true").lower().strip() == "true"
DYNAMIC_LEVERAGE_STRONG_ADX = float(os.getenv("DYNAMIC_LEVERAGE_STRONG_ADX", "30.0"))
DYNAMIC_LEVERAGE_MID = max(1.0, min(float(os.getenv("DYNAMIC_LEVERAGE_MID", "2.0")), MAX_ALLOWED_LEVERAGE))

MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "0.03"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.03"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.70"))
MIN_MINUTES_BETWEEN_TRADES = int(os.getenv("MIN_MINUTES_BETWEEN_TRADES", "240"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
ANALYZE_EVERY_SECONDS = int(os.getenv("ANALYZE_EVERY_SECONDS", "300"))
MAX_POSITION_BALANCE_PCT = float(os.getenv("MAX_POSITION_BALANCE_PCT", "1.0"))
MAX_OPEN_POSITIONS = 1
MIN_ORDER_USD = float(os.getenv("MIN_ORDER_USD", "10"))
DRY_RUN_BALANCE = float(os.getenv("DRY_RUN_BALANCE", "5000"))
ATR_STOP_MULTIPLIER = float(os.getenv("ATR_STOP_MULTIPLIER", "1.5"))
ATR_TAKE_PROFIT_MULTIPLIER = float(os.getenv("ATR_TAKE_PROFIT_MULTIPLIER", "3.0"))
ATR_TRAILING_MULTIPLIER = float(os.getenv("ATR_TRAILING_MULTIPLIER", "3.0"))

USE_AI_ASSIST = os.getenv("USE_AI_ASSIST", "false").lower().strip() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "").strip().rstrip("/")
STATE_FILE = os.getenv("STATE_FILE", "bot_state.json")

EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 100
MACD_FAST = 21
MACD_SLOW = 50
MACD_SIGNAL = 10
ADX_PERIOD = 14
ADX_THRESHOLD = float(os.getenv("ADX_THRESHOLD", "24.0"))
VOLUME_HEALTH_MIN = float(os.getenv("VOLUME_HEALTH_MIN", "0.60"))
REQUIRE_MTF_MACD_CONFIRM = os.getenv("REQUIRE_MTF_MACD_CONFIRM", "true").lower().strip() == "true"
AI_CONFIDENCE_BUFFER = float(os.getenv("AI_CONFIDENCE_BUFFER", "0.08"))
MAX_CANDLE_ATR_MULTIPLIER = float(os.getenv("MAX_CANDLE_ATR_MULTIPLIER", "2.5"))

API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
API_RETRY_BASE_DELAY = float(os.getenv("API_RETRY_BASE_DELAY", "1.0"))
API_RETRY_MAX_DELAY = float(os.getenv("API_RETRY_MAX_DELAY", "30.0"))

TIMEFRAMES = {
    "30M": "THIRTY_MINUTE",
    "1H": "ONE_HOUR",
    "4H": "FOUR_HOUR",
    "1D": "ONE_DAY",
    "1W": "ONE_WEEK",
}

KRAKEN_INTERVALS = {
    "30M": 30,
    "1H": 60,
    "4H": 240,
    "1D": 1440,
    "1W": 10080,
}

CANDLE_SECONDS = {
    "30M": 1800,
    "1H": 3600,
    "4H": 14400,
    "1D": 86400,
    "1W": 604800,
}

CANDLE_LIMITS = {
    "30M": 180,
    "1H": 160,
    "4H": 120,
    "1D": 140,
    "1W": 120,
}

MARKETS = {
    "BTC": {"name": "Bitcoin", "spot_pair": "XBTUSD", "futures_symbol": "PI_XBTUSD", "coinbase": "BTC-USD"},
    "ETH": {"name": "Ethereum", "spot_pair": "ETHUSD", "futures_symbol": "PI_ETHUSD", "coinbase": "ETH-USD"},
    "SOL": {"name": "Solana", "spot_pair": "SOLUSD", "futures_symbol": "PF_SOLUSD", "coinbase": "SOL-USD"},
    "BCH": {"name": "Bitcoin Cash", "spot_pair": "BCHUSD", "futures_symbol": "PF_BCHUSD", "coinbase": "BCH-USD"},
    "LTC": {"name": "Litecoin", "spot_pair": "LTCUSD", "futures_symbol": "PF_LTCUSD", "coinbase": "LTC-USD"},
}

WATCHLIST = [symbol for symbol in WATCHLIST if symbol in MARKETS] or ["BTC"]

# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | btc-bot | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("btc-bot")
client: Optional[RESTClient] = None
telegram_bot: Optional[Bot] = None


# =========================
# ESTADO
# =========================

@dataclass
class TradeStats:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    simulated_pnl_usd: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0


@dataclass
class BotState:
    active: bool = True
    position_open: bool = False
    side: Optional[str] = None
    position_symbol: str = "BTC"
    entry_timeframe: str = "1H"
    entry_price: float = 0.0
    position_size_btc: float = 0.0
    position_usd: float = 0.0
    stop_loss: float = 0.0
    initial_stop_loss: float = 0.0
    take_profit: float = 0.0
    highest_price: float = 0.0
    lowest_price: float = 0.0
    last_trade_ts: float = 0.0
    day: str = ""
    starting_day_balance: float = 0.0
    last_signal: str = "WAIT"
    last_confidence: float = 0.0
    last_reason: str = "Sin analisis todavia."
    stats: TradeStats = field(default_factory=TradeStats)
    trade_history: List[Dict[str, Any]] = field(default_factory=list)
    positions: List[Dict[str, Any]] = field(default_factory=list)
    daily_trades: int = 0


state = BotState()


def save_state() -> None:
    directory = os.path.dirname(os.path.abspath(STATE_FILE)) or "."
    os.makedirs(directory, exist_ok=True)
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="bot_state_", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(state, file, default=lambda obj: obj.__dict__, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, STATE_FILE)
    except Exception as exc:
        logger.error("state_save_failed error=%s", exc)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def load_state() -> None:
    global state
    if not os.path.exists(STATE_FILE):
        logger.info("state_load skipped reason=missing_file")
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        stats = data.get("stats", {})
        state = BotState(
            active=bool(data.get("active", True)),
            position_open=bool(data.get("position_open", False)),
            side=data.get("side"),
            position_symbol=str(data.get("position_symbol", "BTC")).upper(),
            entry_timeframe=str(data.get("entry_timeframe", "1H")).upper(),
            entry_price=float(data.get("entry_price", 0.0)),
            position_size_btc=float(data.get("position_size_btc", 0.0)),
            position_usd=float(data.get("position_usd", 0.0)),
            stop_loss=float(data.get("stop_loss", 0.0)),
            initial_stop_loss=float(data.get("initial_stop_loss", 0.0)),
            take_profit=float(data.get("take_profit", 0.0)),
            highest_price=float(data.get("highest_price", 0.0)),
            lowest_price=float(data.get("lowest_price", 0.0)),
            last_trade_ts=float(data.get("last_trade_ts", 0.0)),
            day=str(data.get("day", "")),
            starting_day_balance=float(data.get("starting_day_balance", 0.0)),
            last_signal=str(data.get("last_signal", "WAIT")),
            last_confidence=float(data.get("last_confidence", 0.0)),
            last_reason=str(data.get("last_reason", "")),
            stats=TradeStats(
                total_trades=int(stats.get("total_trades", 0)),
                wins=int(stats.get("wins", 0)),
                losses=int(stats.get("losses", 0)),
                simulated_pnl_usd=float(stats.get("simulated_pnl_usd", 0.0)),
                best_trade=float(stats.get("best_trade", 0.0)),
                worst_trade=float(stats.get("worst_trade", 0.0)),
            ),
            trade_history=list(data.get("trade_history", [])),
            positions=list(data.get("positions", [])),
            daily_trades=int(data.get("daily_trades", 0)),
        )
        if state.position_open and not state.positions:
            state.positions = [position_from_state()]
        sync_primary_position()
        logger.info("state_loaded file=%s position_open=%s", STATE_FILE, state.position_open)
    except Exception as exc:
        logger.error("state_load_failed error=%s", exc)


def position_from_state() -> Dict[str, Any]:
    return {
        "symbol": state.position_symbol,
        "entry_timeframe": state.entry_timeframe,
        "side": state.side,
        "entry_price": state.entry_price,
        "position_size_btc": state.position_size_btc,
        "position_usd": state.position_usd,
        "stop_loss": state.stop_loss,
        "initial_stop_loss": state.initial_stop_loss,
        "take_profit": state.take_profit,
        "highest_price": state.highest_price,
        "lowest_price": state.lowest_price,
        "last_trade_ts": state.last_trade_ts,
        "last_confidence": state.last_confidence,
        "last_reason": state.last_reason,
    }


def set_state_from_position(position: Dict[str, Any]) -> None:
    state.position_open = True
    state.position_symbol = str(position.get("symbol", WATCHLIST[0])).upper()
    state.entry_timeframe = str(position.get("entry_timeframe", "1H")).upper()
    state.side = position.get("side")
    state.entry_price = float(position.get("entry_price", 0.0))
    state.position_size_btc = float(position.get("position_size_btc", 0.0))
    state.position_usd = float(position.get("position_usd", 0.0))
    state.stop_loss = float(position.get("stop_loss", 0.0))
    state.initial_stop_loss = float(position.get("initial_stop_loss", 0.0))
    state.take_profit = float(position.get("take_profit", 0.0))
    state.highest_price = float(position.get("highest_price", 0.0))
    state.lowest_price = float(position.get("lowest_price", 0.0))
    state.last_trade_ts = float(position.get("last_trade_ts", 0.0))
    state.last_confidence = float(position.get("last_confidence", state.last_confidence))
    state.last_reason = str(position.get("last_reason", state.last_reason))


def sync_position_from_state(position: Dict[str, Any]) -> Dict[str, Any]:
    position.update(position_from_state())
    return position


def active_positions() -> List[Dict[str, Any]]:
    valid_positions = [
        pos
        for pos in state.positions
        if pos.get("side") in ["LONG", "SHORT"] and str(pos.get("symbol", "")).upper() in WATCHLIST
    ]
    state.positions = valid_positions[:MAX_OPEN_POSITIONS]
    return state.positions


def sync_primary_position() -> None:
    positions = active_positions()
    if positions:
        set_state_from_position(positions[0])
        state.position_open = True
        return
    state.position_open = False
    state.side = None
    state.position_symbol = WATCHLIST[0]
    state.entry_timeframe = "1H"
    state.entry_price = 0.0
    state.position_size_btc = 0.0
    state.position_usd = 0.0
    state.stop_loss = 0.0
    state.initial_stop_loss = 0.0
    state.take_profit = 0.0
    state.highest_price = 0.0
    state.lowest_price = 0.0


def open_position_symbols() -> set[str]:
    return {str(position.get("symbol", "")).upper() for position in active_positions()}


def analysis_key_for_timeframe(timeframe: str) -> str:
    return {
        "30M": "thirtym",
        "1H": "hourly",
        "4H": "fourh",
        "1D": "daily",
        "1W": "weekly",
    }.get(timeframe.upper(), "hourly")


# =========================
# API / EXCHANGE
# =========================

def retry_with_backoff(fn: Callable[[], Any]) -> Any:
    last_exc: Exception = RuntimeError("No se realizaron intentos")
    for attempt in range(API_MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt == API_MAX_RETRIES - 1:
                break
            delay = min(API_RETRY_BASE_DELAY * (2 ** attempt), API_RETRY_MAX_DELAY)
            logger.warning("retry attempt=%s/%s delay=%.1fs error=%s", attempt + 1, API_MAX_RETRIES, delay, exc)
            time.sleep(delay)
    raise last_exc


def get_client() -> RESTClient:
    global client
    if client is None:
        if not CB_API_KEY or not CB_API_SECRET:
            raise RuntimeError("Faltan CB_API_KEY o CB_API_SECRET.")
        client = RESTClient(api_key=CB_API_KEY, api_secret=CB_API_SECRET)
    return client


def market_config(symbol: Optional[str] = None) -> Dict[str, str]:
    selected = (symbol or state.position_symbol or WATCHLIST[0]).upper()
    return MARKETS.get(selected, MARKETS["BTC"])


def selected_symbol(symbol: Optional[str] = None) -> str:
    config = market_config(symbol)
    if EXCHANGE == "kraken" and EXCHANGE_MODE == "futures":
        return config["futures_symbol"]
    return config["spot_pair"] if EXCHANGE == "kraken" else config["coinbase"]


def exchange_credentials_available() -> bool:
    if EXCHANGE == "kraken":
        return bool(KRAKEN_API_KEY and KRAKEN_API_SECRET)
    return bool(CB_API_KEY and CB_API_SECRET)


def trading_venue_label() -> str:
    if EXCHANGE == "kraken":
        return f"kraken-{EXCHANGE_MODE}"
    return EXCHANGE


def kraken_private_request(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not KRAKEN_API_KEY or not KRAKEN_API_SECRET:
        raise RuntimeError("Faltan KRAKEN_API_KEY o KRAKEN_API_SECRET.")

    path = f"/0/private/{endpoint}"
    nonce = str(int(time.time() * 1000))
    data = {"nonce": nonce, **payload}
    post_data = urlencode(data)
    encoded = (nonce + post_data).encode("utf-8")
    message = path.encode("utf-8") + hashlib.sha256(encoded).digest()
    signature = hmac.new(base64.b64decode(KRAKEN_API_SECRET), message, hashlib.sha512)
    headers = {
        "API-Key": KRAKEN_API_KEY,
        "API-Sign": base64.b64encode(signature.digest()).decode("utf-8"),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    response = requests.post(f"{KRAKEN_API_URL}{path}", headers=headers, data=post_data, timeout=20)
    response.raise_for_status()
    body = response.json()
    errors = body.get("error") or []
    if errors:
        raise RuntimeError(f"Kraken API error: {errors}")
    return body.get("result", {})


def kraken_public_request(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.get(f"{KRAKEN_API_URL}/0/public/{endpoint}", params=params, timeout=20)
    response.raise_for_status()
    body = response.json()
    errors = body.get("error") or []
    if errors:
        raise RuntimeError(f"Kraken public API error: {errors}")
    return body.get("result", {})


def _backend_url(path: str) -> str:
    clean = path.strip("/")
    return f"{BACKEND_API_URL}/{clean}/"


def _post_json_to_backend(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if not BACKEND_API_URL:
        return {}
    try:
        response = requests.post(_backend_url(path), json=payload, timeout=10)
        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.RequestException as exc:
        logger.warning("backend_post_failed path=%s error=%s", path, exc)
    except Exception as exc:
        logger.warning("backend_post_unexpected path=%s error=%s", path, exc)
    return {}


def _get_json_from_backend(path: str) -> Dict[str, Any]:
    if not BACKEND_API_URL:
        return {}
    try:
        response = requests.get(_backend_url(path), timeout=10)
        response.raise_for_status()
        return response.json() if response.content else {}
    except requests.RequestException as exc:
        logger.warning("backend_get_failed path=%s error=%s", path, exc)
    except Exception as exc:
        logger.warning("backend_get_unexpected path=%s error=%s", path, exc)
    return {}


async def post_json_to_backend(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return await asyncio.to_thread(lambda: _post_json_to_backend(path, payload))


async def sync_bot_control_from_backend() -> None:
    if not BACKEND_API_URL:
        return
    payload = await asyncio.to_thread(lambda: _get_json_from_backend("bot/status"))
    active = payload.get("active") if isinstance(payload, dict) else None
    if isinstance(active, bool) and state.active != active:
        state.active = active
        save_state()
        logger.info("bot_control_synced active=%s source=backend mode=%s", active, payload.get("mode"))


def generate_mock_candles(timeframe: str, limit: int) -> List[Dict[str, Any]]:
    step = {"30M": 50.0, "1H": 80.0, "4H": 180.0, "1D": 320.0, "1W": 600.0}[timeframe]
    current_price = 30000.0
    now = int(time.time())
    result: List[Dict[str, Any]] = []
    for index in range(limit):
        drift = step * 0.04
        wave = math.sin(index / 6.0) * step * 0.35
        open_price = current_price
        close_price = max(1.0, current_price + drift + wave * 0.08)
        high_price = max(open_price, close_price) + step * 0.20
        low_price = min(open_price, close_price) - step * 0.20
        result.append({
            "start": now - (limit - index) * CANDLE_SECONDS[timeframe],
            "low": low_price,
            "high": high_price,
            "open": open_price,
            "close": close_price,
            "volume": max(1.0, DRY_RUN_BALANCE / 1000.0 + (index % 10) * 5.0),
        })
        current_price = close_price
    return result


def finalize_candles(candles: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    ordered = sorted(candles, key=lambda item: int(item.get("start", 0)))
    if USE_CLOSED_CANDLES and len(ordered) > 1:
        ordered = ordered[:-1]
    return ordered[-limit:]


def get_timeframe_candles(timeframe: str, limit: int, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    fetch_limit = limit + 1 if USE_CLOSED_CANDLES else limit
    if DRY_RUN and not exchange_credentials_available():
        logger.info("mock_candles symbol=%s timeframe=%s limit=%s", symbol or WATCHLIST[0], timeframe, limit)
        return finalize_candles(generate_mock_candles(timeframe, fetch_limit), limit)

    if EXCHANGE == "kraken":
        since = int(time.time()) - (fetch_limit * CANDLE_SECONDS[timeframe])
        pair = market_config(symbol)["spot_pair"]

        def fetch_kraken() -> Dict[str, Any]:
            return kraken_public_request("OHLC", {"pair": pair, "interval": KRAKEN_INTERVALS[timeframe], "since": since})

        data = retry_with_backoff(fetch_kraken)
        pair_key = next((key for key in data.keys() if key != "last"), "")
        rows = data.get(pair_key, []) if pair_key else []
        result = []
        for row in rows[-fetch_limit:]:
            if len(row) < 7:
                continue
            result.append({
                "start": int(float(row[0])),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[6]),
            })
        return finalize_candles(result, limit)

    end_ts = int(time.time())
    start_ts = end_ts - (fetch_limit * CANDLE_SECONDS[timeframe])

    def fetch() -> Any:
        cb = get_client()
        return cb.get_candles(
            product_id=selected_symbol(symbol),
            start=str(start_ts),
            end=str(end_ts),
            granularity=TIMEFRAMES[timeframe],
        )

    response = retry_with_backoff(fetch)
    candles = getattr(response, "candles", None)
    if candles is None and isinstance(response, dict):
        candles = response.get("candles", [])

    result = []
    for candle in candles:
        if isinstance(candle, dict):
            result.append(candle)
        else:
            result.append({
                "start": getattr(candle, "start", 0),
                "low": getattr(candle, "low", 0),
                "high": getattr(candle, "high", 0),
                "open": getattr(candle, "open", 0),
                "close": getattr(candle, "close", 0),
                "volume": getattr(candle, "volume", 0),
            })
    return finalize_candles(result, limit)


def get_usdc_balance() -> float:
    if DRY_RUN:
        return DRY_RUN_BALANCE + state.stats.simulated_pnl_usd

    if EXCHANGE == "kraken":
        def fetch_kraken_balance() -> Dict[str, Any]:
            return kraken_private_request("Balance", {})

        balances = retry_with_backoff(fetch_kraken_balance)
        return float(balances.get(KRAKEN_QUOTE_ASSET, 0.0))

    def fetch() -> Any:
        return get_client().get_accounts()

    response = retry_with_backoff(fetch)
    accounts = getattr(response, "accounts", None)
    if accounts is None and isinstance(response, dict):
        accounts = response.get("accounts", [])

    for account in accounts:
        if isinstance(account, dict):
            currency = account.get("currency")
            available = account.get("available_balance", {}).get("value", 0)
        else:
            currency = getattr(account, "currency", "")
            available_balance = getattr(account, "available_balance", None)
            available = getattr(available_balance, "value", 0) if available_balance else 0
        if currency == "USDC":
            return float(available)
    return 0.0


def effective_leverage(adx_value: float = 0.0) -> float:
    if EXCHANGE != "kraken" or EXCHANGE_MODE != "futures":
        return 1.0
    if not DYNAMIC_LEVERAGE_ENABLED:
        return MAX_LEVERAGE
    if adx_value >= DYNAMIC_LEVERAGE_STRONG_ADX:
        return MAX_LEVERAGE
    return min(DYNAMIC_LEVERAGE_MID, MAX_LEVERAGE)


def place_market_order(side: str, quote_size: Optional[float] = None, base_size: Optional[float] = None, leverage: Optional[float] = None) -> Dict[str, Any]:
    order_leverage = leverage if leverage is not None else effective_leverage()
    if DRY_RUN:
        logger.info(
            "paper_order venue=%s symbol=%s leverage=%.2fx side=%s quote_size=%s base_size=%s",
            trading_venue_label(),
            selected_symbol(state.position_symbol),
            order_leverage,
            side,
            quote_size,
            base_size,
        )
        return {
            "dry_run": True,
            "venue": trading_venue_label(),
            "symbol": selected_symbol(state.position_symbol),
            "leverage": order_leverage,
            "side": side,
            "quote_size": quote_size,
            "base_size": base_size,
        }

    if EXCHANGE == "kraken":
        if EXCHANGE_MODE == "futures":
            raise RuntimeError("Kraken Futures real aun no esta habilitado. Mantén DRY_RUN=true hasta implementar la API Futures.")

        def place_kraken() -> Dict[str, Any]:
            volume = base_size
            if volume is None and quote_size is not None:
                recent = get_timeframe_candles("1H", 2, state.position_symbol)
                last_price = float(recent[-1]["close"]) if recent else 0.0
                if last_price <= 0:
                    raise RuntimeError("No se pudo convertir quote_size a volumen base para Kraken.")
                volume = float(quote_size) / last_price
            if volume is None or float(volume) <= 0:
                raise RuntimeError("Kraken requiere base_size/volume positivo para orden market.")
            return kraken_private_request("AddOrder", {
                "pair": KRAKEN_PAIR,
                "type": side.lower(),
                "ordertype": "market",
                "volume": f"{float(volume):.8f}",
            })

        response = retry_with_backoff(place_kraken)
        logger.info("live_order_submitted exchange=kraken side=%s pair=%s", side, KRAKEN_PAIR)
        return {"exchange": "kraken", "raw_response": response}

    def place() -> Any:
        cb = get_client()
        client_order_id = f"btc-bot-{int(time.time())}"
        if side.upper() == "BUY":
            return cb.market_order_buy(
                client_order_id=client_order_id,
                product_id=PRODUCT_ID,
                quote_size=str(round(float(quote_size), 2)),
            )
        return cb.market_order_sell(
            client_order_id=client_order_id,
            product_id=PRODUCT_ID,
            base_size=str(round(float(base_size), 8)),
        )

    response = retry_with_backoff(place)
    logger.info("live_order_submitted side=%s product=%s", side, PRODUCT_ID)
    return {"raw_response": str(response)}


# =========================
# INDICADORES
# =========================

def ema_series(values: List[float], period: int) -> List[float]:
    if not values or period <= 0:
        return []
    k = 2.0 / (period + 1)
    output = [values[0]]
    for price in values[1:]:
        output.append(price * k + output[-1] * (1.0 - k))
    return output


def ema(values: List[float], period: int) -> float:
    series = ema_series(values, period)
    return series[-1] if series else 0.0


def macd(values: List[float]) -> Dict[str, float]:
    if len(values) < MACD_SLOW + MACD_SIGNAL:
        return {"macd": 0.0, "signal": 0.0, "hist": 0.0}
    fast_series = ema_series(values, MACD_FAST)
    slow_series = ema_series(values, MACD_SLOW)
    macd_line = [fast - slow for fast, slow in zip(fast_series, slow_series)]
    signal_series = ema_series(macd_line, MACD_SIGNAL)
    current_macd = macd_line[-1]
    current_signal = signal_series[-1] if signal_series else current_macd
    return {"macd": current_macd, "signal": current_signal, "hist": current_macd - current_signal}


def true_ranges(candles: List[Dict[str, Any]]) -> List[float]:
    ranges = []
    for index in range(1, len(candles)):
        high = float(candles[index]["high"])
        low = float(candles[index]["low"])
        prev_close = float(candles[index - 1]["close"])
        ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    return ranges


def atr_real(candles: List[Dict[str, Any]], period: int = 14) -> float:
    ranges = true_ranges(candles)
    if len(ranges) < period:
        return 0.0
    return sum(ranges[-period:]) / period


def wilder_smooth(values: List[float], period: int) -> List[float]:
    if len(values) < period:
        return []
    output = [sum(values[:period]) / period]
    for value in values[period:]:
        output.append(((output[-1] * (period - 1)) + value) / period)
    return output


def adx(candles: List[Dict[str, Any]], period: int = ADX_PERIOD) -> float:
    if len(candles) < period * 2 + 1:
        return 0.0

    tr_values: List[float] = []
    plus_dm: List[float] = []
    minus_dm: List[float] = []
    for index in range(1, len(candles)):
        high = float(candles[index]["high"])
        low = float(candles[index]["low"])
        prev_high = float(candles[index - 1]["high"])
        prev_low = float(candles[index - 1]["low"])
        prev_close = float(candles[index - 1]["close"])
        tr_values.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        up_move = high - prev_high
        down_move = prev_low - low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)

    smoothed_tr = wilder_smooth(tr_values, period)
    smoothed_plus = wilder_smooth(plus_dm, period)
    smoothed_minus = wilder_smooth(minus_dm, period)
    dx_values = []
    for tr_val, plus_val, minus_val in zip(smoothed_tr, smoothed_plus, smoothed_minus):
        if tr_val <= 0:
            dx_values.append(0.0)
            continue
        plus_di = 100.0 * plus_val / tr_val
        minus_di = 100.0 * minus_val / tr_val
        denominator = plus_di + minus_di
        dx_values.append(100.0 * abs(plus_di - minus_di) / denominator if denominator else 0.0)

    adx_values = wilder_smooth(dx_values, period)
    return adx_values[-1] if adx_values else 0.0


def bollinger(values: List[float], period: int = 20, mult: float = 2.0) -> Dict[str, float]:
    if len(values) < 2:
        return {"upper": 0.0, "middle": 0.0, "lower": 0.0, "width_pct": 0.0}
    recent = values[-period:] if len(values) >= period else values
    mid = sum(recent) / len(recent)
    variance = sum((value - mid) ** 2 for value in recent) / len(recent)
    std = math.sqrt(variance)
    width_pct = ((2 * mult * std) / mid * 100) if mid else 0.0
    return {"upper": mid + mult * std, "middle": mid, "lower": mid - mult * std, "width_pct": width_pct}


def volume_ratio(candles: List[Dict[str, Any]], period: int = 20) -> float:
    volumes = [float(candle.get("volume", 0.0)) for candle in candles]
    if len(volumes) < period + 1:
        return 1.0
    avg = sum(volumes[-period - 1:-1]) / period
    return volumes[-1] / avg if avg else 1.0


# =========================
# ESTRATEGIA
# =========================

def empty_timeframe(price: float = 0.0) -> Dict[str, Any]:
    return {
        "trend": "neutral",
        "price": price,
        "ema21": 0.0,
        "ema50": 0.0,
        "ema100": 0.0,
        "macd": {"macd": 0.0, "signal": 0.0, "hist": 0.0},
        "adx": 0.0,
        "volume_ratio": 1.0,
        "atr": 0.0,
        "volatility_ratio": 0.0,
    }


def empty_analysis(reason: str, price: float = 0.0) -> Dict[str, Any]:
    frame = empty_timeframe(price)
    return {
        "signal": "WAIT",
        "confidence": 0.0,
        "price": price,
        "atr": 0.0,
        "reason": reason,
        "weekly": dict(frame),
        "daily": dict(frame),
        "fourh": dict(frame),
        "hourly": frame,
    }


def timeframe_analysis(candles: List[Dict[str, Any]], timeframe: str = "") -> Dict[str, Any]:
    closes = [float(candle["close"]) for candle in candles]
    if len(closes) < EMA_SLOW + 1:
        return empty_timeframe(closes[-1] if closes else 0.0)

    ema21_val = ema(closes[-80:], EMA_FAST)
    ema50_val = ema(closes[-120:], EMA_MID)
    ema100_val = ema(closes[-160:], EMA_SLOW)
    price = closes[-1]
    trend = (
        "bull" if ema21_val > ema50_val and price > ema100_val
        else "bear" if ema21_val < ema50_val and price < ema100_val
        else "neutral"
    )
    atr_value = atr_real(candles, 14)
    latest_range = float(candles[-1]["high"]) - float(candles[-1]["low"])
    return {
        "trend": trend,
        "price": price,
        "ema21": ema21_val,
        "ema50": ema50_val,
        "ema100": ema100_val,
        "macd": macd(closes),
        "adx": adx(candles),
        "volume_ratio": volume_ratio(candles),
        "atr": atr_value,
        "volatility_ratio": latest_range / atr_value if atr_value > 0 else 0.0,
    }


def ai_quality_filter(analysis: Dict[str, Any]) -> bool:
    return analysis["adx"] >= ADX_THRESHOLD and analysis["volume_ratio"] >= VOLUME_HEALTH_MIN


def _clean_openai_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.replace("```json", "", 1).replace("```", "", 1).strip()
    return text


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = _clean_openai_text(text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def _ai_not_called(reason: str, score: float = 0.0) -> Dict[str, Any]:
    return {
        "allow": True,
        "score": score,
        "called_openai": False,
        "rate_limited": False,
        "reasons": [reason],
        "openai": {},
        "openai_explanation": reason,
    }


def _format_analysis_block(label: str, data: Dict[str, Any]) -> str:
    return (
        f"{label}: trend={data['trend']}, price={data['price']}, ema21={data['ema21']}, "
        f"ema50={data['ema50']}, ema100={data['ema100']}, macd_hist={data['macd']['hist']}, "
        f"adx={data['adx']}, volume_ratio={data['volume_ratio']}, atr={data.get('atr', 0.0)}"
    )


def _openai_assist(weekly: Dict[str, Any], daily: Dict[str, Any], fourh: Dict[str, Any], hourly: Dict[str, Any], direction: str = "") -> Dict[str, Any]:
    if not USE_AI_ASSIST or not OPENAI_API_KEY:
        return {}

    prompt = (
        "Eres un validador de paper trading BTC. No reemplazas la estrategia. "
        "Responde solo JSON con: allow, approved_direction, validation, signal_reason, "
        "risk_summary, market_summary, extra_reasons.\n"
        f"Direccion candidata: {direction or 'N/A'}\n"
        f"{_format_analysis_block('Weekly', weekly)}\n"
        f"{_format_analysis_block('Daily', daily)}\n"
        f"{_format_analysis_block('4H', fourh)}\n"
        f"{_format_analysis_block('1H', hourly)}"
    )

    def call() -> Dict[str, Any]:
        payload = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": "Valida senales de trading con JSON estricto."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 320,
        }
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=20)
        if response.status_code == 429:
            logger.warning("openai_rate_limited status=429 fallback=WAIT")
            return {
                "allow": False,
                "rate_limited": True,
                "validation": "OpenAI rate limit 429. Fallback seguro a WAIT para evitar sobreoperar.",
                "signal_reason": "No se aprueba entrada porque la validacion IA no estuvo disponible.",
                "risk_summary": "Riesgo operacional alto por rate limit.",
                "market_summary": "Analisis IA omitido por limite de tasa.",
                "extra_reasons": ["Reducir frecuencia de llamadas o subir limites antes de operar con IA."],
            }
        response.raise_for_status()
        text = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        return _extract_json_object(text)

    try:
        return retry_with_backoff(call)
    except Exception as exc:
        logger.warning("openai_assist_failed error=%s", exc)
        return {
            "allow": False,
            "openai_error": str(exc),
            "validation": "OpenAI no estuvo disponible. Fallback seguro a WAIT.",
            "signal_reason": "No se aprueba entrada porque fallo la validacion IA.",
            "risk_summary": "Riesgo operacional alto por error de IA.",
            "market_summary": "Analisis IA no disponible.",
            "extra_reasons": [],
        }


def ai_assist_analysis(weekly: Dict[str, Any], daily: Dict[str, Any], fourh: Dict[str, Any], hourly: Dict[str, Any], direction: str = "") -> Dict[str, Any]:
    score = 0.0
    reasons: List[str] = []
    checks = [
        (hourly["adx"] >= ADX_THRESHOLD, 0.25, "ADX fuerte en 1H", "ADX debil en 1H"),
        (hourly["volume_ratio"] >= VOLUME_HEALTH_MIN, 0.20, "Volumen saludable en 1H", "Volumen bajo en 1H"),
        (abs(hourly["macd"]["hist"]) >= 0.05, 0.15, "Momentum MACD significativo en 1H", "Momentum MACD debil en 1H"),
        (weekly["trend"] != "neutral", 0.15, f"Tendencia 1W {weekly['trend']}", "Tendencia 1W neutral"),
        (daily["trend"] != "neutral", 0.15, f"Tendencia 1D {daily['trend']}", "Tendencia 1D neutral"),
    ]
    for passed, weight, good_reason, bad_reason in checks:
        if passed:
            score += weight
            reasons.append(good_reason)
        else:
            reasons.append(bad_reason)

    allow = score >= 0.60
    openai_feedback = _openai_assist(weekly, daily, fourh, hourly, direction)
    called_openai = bool(USE_AI_ASSIST and OPENAI_API_KEY)
    openai_explanation_parts: List[str] = []
    if openai_feedback:
        openai_allow = openai_feedback.get("allow")
        if isinstance(openai_allow, bool):
            allow = allow and openai_allow
        for key, prefix in [
            ("validation", "IA validacion"),
            ("signal_reason", "IA senal"),
            ("risk_summary", "IA riesgo"),
            ("market_summary", "IA resumen"),
        ]:
            value = openai_feedback.get(key)
            if value:
                reasons.append(f"{prefix}: {value}")
                openai_explanation_parts.append(f"{prefix}: {value}")
        extra = openai_feedback.get("extra_reasons")
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, str) and item.strip():
                    reasons.append(f"IA extra: {item}")
                    openai_explanation_parts.append(f"IA extra: {item}")
    elif called_openai:
        allow = False
        reasons.append("IA no devolvio respuesta util. Fallback seguro a WAIT")
        openai_explanation_parts.append("IA no devolvio respuesta util. Fallback seguro a WAIT")

    openai_explanation = " | ".join(openai_explanation_parts) if openai_explanation_parts else "OpenAI no fue llamado."
    return {
        "allow": allow,
        "score": score,
        "reasons": reasons,
        "openai": openai_feedback,
        "called_openai": called_openai,
        "rate_limited": bool(openai_feedback.get("rate_limited")) if isinstance(openai_feedback, dict) else False,
        "openai_explanation": openai_explanation,
    }


def build_signal(weekly: Dict[str, Any], daily: Dict[str, Any], fourh: Dict[str, Any], hourly: Dict[str, Any]) -> Dict[str, Any]:
    atr_value = float(hourly.get("atr", 0.0))
    volatility_ratio = float(hourly.get("volatility_ratio", 0.0))
    volatility_ok = volatility_ratio <= MAX_CANDLE_ATR_MULTIPLIER if volatility_ratio > 0 else True
    candidate_checks = {
        "LONG": [
            (daily["trend"] == "bull", 0.24, "1D bullish", "1D no confirma LONG"),
            (fourh["trend"] == "bull", 0.24, "4H bullish", "4H no confirma LONG"),
            (hourly["trend"] == "bull", 0.12, "1H bullish", "1H no confirma LONG"),
            (hourly["macd"]["hist"] > 0, 0.12, "MACD 1H positivo", "MACD 1H no confirma LONG"),
            (
                not REQUIRE_MTF_MACD_CONFIRM or (daily["macd"]["hist"] > 0 and fourh["macd"]["hist"] > 0),
                0.00,
                "MACD 4H/1D confirma LONG",
                "MACD 4H/1D no confirma LONG",
            ),
            (hourly["adx"] >= ADX_THRESHOLD, 0.14, "ADX fuerte", "ADX insuficiente"),
            (hourly["volume_ratio"] >= VOLUME_HEALTH_MIN, 0.14, "Volumen saludable", "Volumen insuficiente"),
            (volatility_ok, 0.00, "Volatilidad 1H aceptable", "Volatilidad extrema: vela 1H demasiado grande contra ATR"),
        ],
        "SHORT": [
            (ALLOW_SHORT_SIGNALS, 0.00, "SHORT habilitado", "Senales SHORT deshabilitadas por configuracion"),
            (daily["trend"] == "bear", 0.24, "1D bearish", "1D no confirma SHORT"),
            (fourh["trend"] == "bear", 0.24, "4H bearish", "4H no confirma SHORT"),
            (hourly["trend"] == "bear", 0.12, "1H bearish", "1H no confirma SHORT"),
            (hourly["macd"]["hist"] < 0, 0.12, "MACD 1H negativo", "MACD 1H no confirma SHORT"),
            (
                not REQUIRE_MTF_MACD_CONFIRM or (daily["macd"]["hist"] < 0 and fourh["macd"]["hist"] < 0),
                0.00,
                "MACD 4H/1D confirma SHORT",
                "MACD 4H/1D no confirma SHORT",
            ),
            (hourly["adx"] >= ADX_THRESHOLD, 0.14, "ADX fuerte", "ADX insuficiente"),
            (hourly["volume_ratio"] >= VOLUME_HEALTH_MIN, 0.14, "Volumen saludable", "Volumen insuficiente"),
            (volatility_ok, 0.00, "Volatilidad 1H aceptable", "Volatilidad extrema: vela 1H demasiado grande contra ATR"),
        ],
    }
    weekly_context = {
        "LONG": (
            weekly["trend"] != "bear" and weekly["price"] >= weekly["ema100"],
            "1W permite LONG como contexto",
            "Filtro 1W bloquea LONG: tendencia semanal bajista o precio bajo EMA100",
        ),
        "SHORT": (
            weekly["trend"] != "bull" and weekly["price"] <= weekly["ema100"],
            "1W permite SHORT como contexto",
            "Filtro 1W bloquea SHORT: tendencia semanal alcista o precio sobre EMA100",
        ),
    }

    candidates: List[Dict[str, Any]] = []
    for direction, checks in candidate_checks.items():
        confidence = 0.0
        reasons: List[str] = []
        failures: List[str] = []
        check_rows: List[Dict[str, Any]] = []
        context_ok, context_reason, context_failure = weekly_context[direction]
        if context_ok:
            reasons.append(context_reason)
        else:
            failures.append(context_failure)
        check_rows.append({
            "label": "1W contexto",
            "status": "ok" if context_ok else "block",
            "value": weekly["trend"],
            "detail": context_reason if context_ok else context_failure,
        })
        for passed, weight, reason, failure in checks:
            if passed:
                confidence += weight
                reasons.append(reason)
            else:
                failures.append(failure)
            check_rows.append({
                "label": reason.split(" ")[0] if reason.startswith(("1D", "4H", "1H")) else reason,
                "status": "ok" if passed else "block",
                "value": reason if passed else failure,
                "detail": reason if passed else failure,
            })
        check_rows.append({
            "label": "ATR real",
            "status": "ok" if atr_value > 0 else "block",
            "value": round(atr_value, 4),
            "detail": "ATR disponible para SL/TP/trailing" if atr_value > 0 else "ATR real no disponible",
        })
        candidates.append({
            "direction": direction,
            "confidence": confidence,
            "reasons": reasons,
            "failures": failures,
            "checks": check_rows,
            "strict_ok": context_ok and not failures and atr_value > 0,
        })

    best_candidate = max(candidates, key=lambda item: float(item["confidence"]))
    best_direction = str(best_candidate["direction"])
    best_confidence = float(best_candidate["confidence"])
    strict_ok = bool(best_candidate["strict_ok"])
    near_confidence = strict_ok and best_confidence >= max(0.0, MIN_CONFIDENCE - AI_CONFIDENCE_BUFFER)

    if not USE_AI_ASSIST:
        ai_evaluation = _ai_not_called("IA desactivada.", best_confidence)
        ai_reason = "IA desactivada"
    elif not strict_ok:
        failure_text = ", ".join(best_candidate["failures"]) if best_candidate["failures"] else "ATR real no disponible"
        ai_evaluation = _ai_not_called(
            f"OpenAI no llamado: swing estricto no confirmado para {best_direction} ({failure_text}).",
            best_confidence,
        )
        ai_reason = f"IA omitida: {'|'.join(ai_evaluation['reasons'])}"
    elif not near_confidence:
        ai_evaluation = _ai_not_called(
            f"OpenAI no llamado: confianza {best_confidence:.2f} debajo de zona cercana a MIN_CONFIDENCE {MIN_CONFIDENCE:.2f}.",
            best_confidence,
        )
        ai_reason = f"IA omitida: {'|'.join(ai_evaluation['reasons'])}"
    else:
        ai_evaluation = ai_assist_analysis(weekly, daily, fourh, hourly, best_direction)
        ai_reason = f"IA: {'|'.join(ai_evaluation['reasons'])}"

    base = {
        "price": hourly["price"],
        "atr": atr_value,
        "ai_called": ai_evaluation.get("called_openai", False),
        "ai_rate_limited": ai_evaluation.get("rate_limited", False),
        "ai_explanation": ai_evaluation.get("openai_explanation", ""),
        "ai_feedback": ai_evaluation.get("openai", {}),
        "strategy_checks": best_candidate.get("checks", []),
        "blocked_reasons": best_candidate.get("failures", []),
        "volatility_ratio": volatility_ratio,
    }

    if atr_value <= 0:
        return {
            **base,
            "signal": "WAIT",
            "confidence": best_confidence,
            "reason": f"ATR real no disponible para SL/TP en {best_direction}. {ai_reason}",
        }

    if not strict_ok:
        return {
            **base,
            "signal": "WAIT",
            "confidence": best_confidence,
            "reason": f"No se cumplen condiciones swing estrictas para {best_direction}: {', '.join(best_candidate['failures'])}. {ai_reason}",
        }

    if best_confidence < MIN_CONFIDENCE:
        return {
            **base,
            "signal": "WAIT",
            "confidence": best_confidence,
            "reason": f"Confianza insuficiente para {best_direction}. {ai_reason}",
        }

    if USE_AI_ASSIST and ai_evaluation.get("called_openai") and not ai_evaluation["allow"]:
        return {
            **base,
            "signal": "WAIT",
            "confidence": best_confidence,
            "reason": f"Falto confirmacion IA para {best_direction}: {', '.join(ai_evaluation['reasons'])}",
        }

    feedback = ai_evaluation.get("openai") or {}
    approved_direction = str(feedback.get("approved_direction", "")).upper()
    if feedback and approved_direction not in ["", best_direction]:
        return {
            **base,
            "signal": "WAIT",
            "confidence": best_confidence,
            "reason": f"OpenAI rechazo {best_direction}: {ai_evaluation.get('openai_explanation', feedback)}",
        }

    return {
        **base,
        "signal": best_direction,
        "confidence": best_confidence,
        "reason": ", ".join(best_candidate["reasons"]) + ". " + ai_reason,
    }


ENTRY_TIMEFRAME_PRIORITY = {
    "30M": 0.00,
    "1H": 0.01,
    "4H": 0.02,
    "1D": 0.03,
}


def _direction_matches(direction: str, analysis: Dict[str, Any]) -> bool:
    if direction == "LONG":
        return analysis.get("trend") == "bull" and analysis.get("macd", {}).get("hist", 0.0) > 0
    if direction == "SHORT":
        return analysis.get("trend") == "bear" and analysis.get("macd", {}).get("hist", 0.0) < 0
    return False


def build_entry_timeframe_signal(
    entry_timeframe: str,
    weekly: Dict[str, Any],
    daily: Dict[str, Any],
    fourh: Dict[str, Any],
    hourly: Dict[str, Any],
    thirtym: Dict[str, Any],
) -> Dict[str, Any]:
    entry_map = {
        "30M": thirtym,
        "1H": hourly,
        "4H": fourh,
        "1D": daily,
    }
    entry = entry_map[entry_timeframe]
    if entry_timeframe == "30M":
        signal = build_signal(weekly, daily, fourh, thirtym)
        direction = str(signal.get("signal", "WAIT"))
        if direction in ["LONG", "SHORT"] and not _direction_matches(direction, hourly):
            signal = {
                **signal,
                "signal": "WAIT",
                "reason": f"30M dio {direction}, pero 1H no confirma la misma direccion.",
            }
    elif entry_timeframe == "1H":
        signal = build_signal(weekly, daily, fourh, hourly)
    elif entry_timeframe == "4H":
        signal = build_signal(weekly, daily, daily, fourh)
    else:
        signal = build_signal(weekly, daily, daily, daily)

    adx_component = min(float(entry.get("adx", 0.0)) / 100.0, 0.10)
    volume_component = min(float(entry.get("volume_ratio", 0.0)) / 100.0, 0.03)
    opportunity_score = float(signal.get("confidence", 0.0)) + adx_component + volume_component + ENTRY_TIMEFRAME_PRIORITY[entry_timeframe]
    signal.update({
        "entry_timeframe": entry_timeframe,
        "entry_analysis": entry,
        "price": entry.get("price", signal.get("price", 0.0)),
        "atr": entry.get("atr", signal.get("atr", 0.0)),
        "opportunity_score": opportunity_score,
    })
    if signal.get("signal") in ["LONG", "SHORT"]:
        signal["reason"] = f"Entrada {entry_timeframe}: {signal.get('reason', '')}"
    return signal


def analyze_market(symbol: Optional[str] = None) -> Dict[str, Any]:
    selected = (symbol or WATCHLIST[0]).upper()
    candles = {
        "1W": get_timeframe_candles("1W", CANDLE_LIMITS["1W"], selected),
        "1D": get_timeframe_candles("1D", CANDLE_LIMITS["1D"], selected),
        "4H": get_timeframe_candles("4H", CANDLE_LIMITS["4H"], selected),
        "1H": get_timeframe_candles("1H", CANDLE_LIMITS["1H"], selected),
        "30M": get_timeframe_candles("30M", CANDLE_LIMITS["30M"], selected),
    }
    last_price = float(candles["1H"][-1]["close"]) if candles["1H"] else 0.0
    min_required_candles = EMA_SLOW + MACD_SIGNAL
    if any(len(items) < min_required_candles for items in candles.values()):
        return empty_analysis(
            f"No hay suficientes velas para EMA100/MACD. Minimo requerido: {min_required_candles}.",
            last_price,
        )

    weekly = timeframe_analysis(candles["1W"], "1W")
    daily = timeframe_analysis(candles["1D"], "1D")
    fourh = timeframe_analysis(candles["4H"], "4H")
    hourly = timeframe_analysis(candles["1H"], "1H")
    thirtym = timeframe_analysis(candles["30M"], "30M")
    entry_signals = [
        build_entry_timeframe_signal(entry_timeframe, weekly, daily, fourh, hourly, thirtym)
        for entry_timeframe in ["30M", "1H", "4H", "1D"]
    ]
    actionable = [item for item in entry_signals if item.get("signal") in ["LONG", "SHORT"]]
    signal = max(
        actionable if actionable else entry_signals,
        key=lambda item: float(item.get("opportunity_score", item.get("confidence", 0.0))),
    )
    signal.update({
        "symbol": selected,
        "trade_symbol": selected_symbol(selected),
        "asset_name": market_config(selected)["name"],
        "weekly": weekly,
        "daily": daily,
        "fourh": fourh,
        "hourly": hourly,
        "thirtym": thirtym,
        "entry_signals": entry_signals,
    })
    return signal


def analyze_watchlist() -> List[Dict[str, Any]]:
    analyses: List[Dict[str, Any]] = []
    for symbol in WATCHLIST:
        try:
            analyses.append(analyze_market(symbol))
        except Exception as exc:
            logger.warning("market_analysis_failed symbol=%s error=%s", symbol, exc)
            failed = empty_analysis(f"Error analizando {symbol}: {exc}", 0.0)
            failed.update({"symbol": symbol, "trade_symbol": selected_symbol(symbol), "asset_name": market_config(symbol)["name"]})
            analyses.append(failed)
    return analyses


def choose_trade_analysis(analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    actionable = [item for item in analyses if item.get("signal") in ["LONG", "SHORT"]]
    candidates = actionable if actionable else analyses
    return max(candidates, key=lambda item: float(item.get("opportunity_score", item.get("confidence", 0.0)))) if candidates else empty_analysis("Watchlist vacio.", 0.0)


# =========================
# BACKEND PAYLOADS
# =========================

def build_market_snapshot_payload(analysis: Dict[str, Any]) -> Dict[str, Any]:
    display_analysis = analysis.get("entry_analysis") or analysis.get("hourly", {})
    price = float(display_analysis.get("price", analysis.get("price", 0.0)))
    atr_value = float(analysis.get("atr", 0.0))
    support = max(0.0, price - atr_value * ATR_STOP_MULTIPLIER) if atr_value > 0 else price * 0.995
    resistance = price + atr_value * ATR_STOP_MULTIPLIER if atr_value > 0 else price * 1.005
    return {
        "symbol": analysis.get("trade_symbol", selected_symbol(str(analysis.get("symbol", WATCHLIST[0])))),
        "timeframe": analysis.get("entry_timeframe", "1H"),
        "price": price,
        "trend": display_analysis.get("trend", "neutral"),
        "support": support,
        "resistance": resistance,
        "volume": float(display_analysis.get("volume_ratio", 0.0)),
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


def build_signal_payload(analysis: Dict[str, Any]) -> Dict[str, Any]:
    confidence = int(round(float(analysis.get("confidence", 0.0)) * 100))
    direction = analysis.get("signal", "WAIT")
    return {
        "symbol": analysis.get("trade_symbol", selected_symbol(str(analysis.get("symbol", WATCHLIST[0])))),
        "timeframe": analysis.get("entry_timeframe", "1H"),
        "direction": direction,
        "confidence_score": max(0, min(confidence, 100)),
        "risk_level": "low" if confidence >= 80 else "medium" if confidence >= 50 else "high",
        "market_condition": (analysis.get("entry_analysis") or analysis.get("hourly", {})).get("trend", "neutral"),
        "approved": direction in ["LONG", "SHORT"],
        "explanation": analysis.get("reason", "No reason provided."),
        "created_at": datetime.utcnow().isoformat() + "Z",
    }


def build_ai_decision_payload(analysis: Dict[str, Any], signal_id: int = 0) -> Dict[str, Any]:
    direction = analysis.get("signal", "WAIT")
    reason = analysis.get("reason", "No reason provided.")
    hourly = analysis.get("hourly", {})
    ai_called = bool(analysis.get("ai_called", False))
    ai_rate_limited = bool(analysis.get("ai_rate_limited", False))
    ai_explanation = str(analysis.get("ai_explanation") or "").strip()
    snapshot = {
        "symbol": analysis.get("symbol"),
        "trade_symbol": analysis.get("trade_symbol"),
        "asset_name": analysis.get("asset_name"),
        "signal": direction,
        "entry_timeframe": analysis.get("entry_timeframe", "1H"),
        "opportunity_score": analysis.get("opportunity_score"),
        "confidence": analysis.get("confidence", 0.0),
        "trend_30m": analysis.get("thirtym", {}).get("trend"),
        "trend_1h": hourly.get("trend"),
        "trend_4h": analysis.get("fourh", {}).get("trend"),
        "trend_1d": analysis.get("daily", {}).get("trend"),
        "entry_adx": (analysis.get("entry_analysis") or {}).get("adx"),
        "adx": hourly.get("adx"),
        "volume_ratio": hourly.get("volume_ratio"),
        "atr": hourly.get("atr"),
        "volatility_ratio": analysis.get("volatility_ratio"),
        "strategy_checks": analysis.get("strategy_checks", []),
        "blocked_reasons": analysis.get("blocked_reasons", []),
        "ai_called": ai_called,
        "ai_rate_limited": ai_rate_limited,
        "ai_feedback": analysis.get("ai_feedback", {}),
    }
    if ai_rate_limited:
        decision_type = "ai_rate_limited"
    elif direction in ["LONG", "SHORT"]:
        decision_type = "signal_approved"
    elif ai_called and "confirmacion IA" in reason:
        decision_type = "ai_rejected"
    else:
        decision_type = "analysis_wait"

    backend_explanation = reason
    if ai_called and ai_explanation:
        backend_explanation = f"{reason}\n\nExplicacion IA real: {ai_explanation}"

    return {
        "signal_id": signal_id,
        "decision_type": decision_type,
        "reason": f"{direction}: {reason[:200]}",
        "condition_snapshot": json.dumps(snapshot),
        "explanation": backend_explanation,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def build_trade_payload(price: float, pnl: float) -> Dict[str, Any]:
    return {
        "signal_id": 0,
        "entry_price": state.entry_price,
        "stop_loss": state.stop_loss,
        "take_profit": state.take_profit,
        "target_price": state.take_profit,
        "closed_price": price,
        "result_pct": (pnl / state.position_usd * 100) if state.position_usd else 0.0,
        "status": "CLOSED",
        "opened_at": datetime.utcfromtimestamp(state.last_trade_ts).isoformat() + "Z" if state.last_trade_ts else datetime.utcnow().isoformat() + "Z",
        "closed_at": datetime.utcnow().isoformat() + "Z",
        "drawdown_pct": 0.0,
        "notes": state.last_reason,
    }


async def send_signal_to_backend(analysis: Dict[str, Any]) -> None:
    if not BACKEND_API_URL:
        return
    result = await post_json_to_backend("signals", build_signal_payload(analysis))
    signal_id = int(result.get("id", 0)) if isinstance(result, dict) else 0
    await post_json_to_backend("ai/decisions", build_ai_decision_payload(analysis, signal_id))


async def send_snapshot_to_backend(analysis: Dict[str, Any]) -> None:
    if not BACKEND_API_URL:
        return
    await post_json_to_backend("market/snapshots", build_market_snapshot_payload(analysis))


async def send_trade_to_backend(price: float, pnl: float) -> None:
    if not BACKEND_API_URL:
        return
    await post_json_to_backend("trades", build_trade_payload(price, pnl))


async def publish_analyses_to_backend(analyses: List[Dict[str, Any]]) -> None:
    if not BACKEND_API_URL:
        return
    for analysis in analyses:
        await send_snapshot_to_backend(analysis)
        await send_signal_to_backend(analysis)


# =========================
# RIESGO
# =========================

def unrealized_pnl(price: float) -> float:
    if not state.position_open or price <= 0:
        return 0.0
    if state.side == "LONG":
        return (price - state.entry_price) * state.position_size_btc
    return (state.entry_price - price) * state.position_size_btc


def simulated_equity(price: float) -> float:
    return DRY_RUN_BALANCE + state.stats.simulated_pnl_usd + unrealized_pnl(price)


def can_trade_now(ignore_interval: bool = False) -> bool:
    if not state.active or len(active_positions()) >= MAX_OPEN_POSITIONS:
        return False
    if ignore_interval:
        return True
    if state.last_trade_ts == 0:
        return True
    return (time.time() - state.last_trade_ts) >= MIN_MINUTES_BETWEEN_TRADES * 60


def reset_daily_balance_if_needed(balance: float) -> None:
    today = date.today().isoformat()
    if state.day != today:
        state.day = today
        state.starting_day_balance = balance
        state.daily_trades = 0
        logger.info("new_trading_day balance=%.2f", balance)


def daily_loss_limit_reached(balance: float) -> bool:
    if state.starting_day_balance <= 0:
        return False
    drawdown = (state.starting_day_balance - balance) / state.starting_day_balance
    return drawdown >= MAX_DAILY_LOSS


def calculate_position_size(balance: float, price: float, atr_val: float, adx_value: float = 0.0) -> float:
    if atr_val <= 0 or price <= 0 or balance <= 0:
        return 0.0
    risk_amount = balance * MAX_RISK_PER_TRADE
    stop_distance = atr_val * ATR_STOP_MULTIPLIER
    btc_size = risk_amount / stop_distance
    max_notional = balance * MAX_POSITION_BALANCE_PCT
    max_notional *= effective_leverage(adx_value)
    usd_size = min(btc_size * price, max_notional)
    if usd_size < MIN_ORDER_USD:
        return 0.0
    return usd_size / price


def record_trade_pnl(exit_price: float) -> float:
    pnl = unrealized_pnl(exit_price)
    state.stats.total_trades += 1
    if pnl >= 0:
        state.stats.wins += 1
    else:
        state.stats.losses += 1
    state.stats.simulated_pnl_usd += pnl
    state.stats.best_trade = max(state.stats.best_trade, pnl)
    state.stats.worst_trade = min(state.stats.worst_trade, pnl)
    state.trade_history.append({
        "timestamp": int(time.time()),
        "symbol": state.position_symbol,
        "side": state.side,
        "entry": state.entry_price,
        "exit": exit_price,
        "pnl": pnl,
        "position_size_btc": state.position_size_btc,
        "confidence": state.last_confidence,
        "reason": state.last_reason,
    })
    return pnl


def manage_open_position(price: float, hourly: Dict[str, Any]) -> Optional[str]:
    if price <= 0:
        return None
    atr_value = float(hourly.get("atr", 0.0))
    if state.side == "LONG":
        state.highest_price = max(state.highest_price, price)
        if price <= state.stop_loss:
            return "STOP_LOSS"
        if price >= state.take_profit:
            return "TAKE_PROFIT"
        if hourly.get("adx", 0.0) >= ADX_THRESHOLD and atr_value > 0:
            state.stop_loss = max(state.stop_loss, state.highest_price - (atr_value * ATR_TRAILING_MULTIPLIER))
    elif state.side == "SHORT":
        state.lowest_price = min(state.lowest_price if state.lowest_price > 0 else price, price)
        if price >= state.stop_loss:
            return "STOP_LOSS"
        if price <= state.take_profit:
            return "TAKE_PROFIT"
        if hourly.get("adx", 0.0) >= ADX_THRESHOLD and atr_value > 0:
            state.stop_loss = min(state.stop_loss, state.lowest_price + (atr_value * ATR_TRAILING_MULTIPLIER))
    return None


def close_position_state() -> None:
    state.positions = [pos for pos in state.positions if str(pos.get("symbol", "")).upper() != state.position_symbol]
    sync_primary_position()
    if state.position_open:
        return
    state.side = None
    state.position_symbol = WATCHLIST[0]
    state.entry_timeframe = "1H"
    state.entry_price = 0.0
    state.position_size_btc = 0.0
    state.position_usd = 0.0
    state.stop_loss = 0.0
    state.initial_stop_loss = 0.0
    state.take_profit = 0.0
    state.highest_price = 0.0
    state.lowest_price = 0.0
    state.last_trade_ts = time.time()


# =========================
# TELEGRAM
# =========================

async def send_telegram(app: Optional[Application], message: str) -> None:
    global telegram_bot
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.info("telegram_disabled message=%s", message)
        return
    try:
        if app is not None:
            await app.bot.send_message(chat_id=CHAT_ID, text=message)
            return
        if telegram_bot is None:
            telegram_bot = Bot(token=TELEGRAM_TOKEN)
        await telegram_bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as exc:
        logger.error("telegram_send_failed error=%s", exc)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state.active = True
    save_state()
    await update.message.reply_text("BTC Bot Seguro activo.")


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state.active = False
    save_state()
    await update.message.reply_text("Bot pausado. No abrira nuevas operaciones.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    win_rate = (state.stats.wins / state.stats.total_trades * 100) if state.stats.total_trades else 0
    await update.message.reply_text(
        "Estado del bot\n"
        f"Activo: {state.active}\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"Exchange: {EXCHANGE}\n"
        f"Watchlist: {', '.join(WATCHLIST)}\n"
        f"Producto: {selected_symbol(state.position_symbol)}\n"
        f"Posiciones abiertas: {len(active_positions())}/{MAX_OPEN_POSITIONS}\n"
        f"Simbolo posicion: {state.position_symbol}\n"
        f"Temporalidad entrada: {state.entry_timeframe}\n"
        f"Side: {state.side}\n"
        f"Entrada: {state.entry_price:.2f}\n"
        f"BTC: {state.position_size_btc:.8f}\n"
        f"Stop Loss: {state.stop_loss:.2f}\n"
        f"Take Profit: {state.take_profit:.2f}\n"
        f"Trades dia: {state.daily_trades}\n"
        f"PnL simulado: ${state.stats.simulated_pnl_usd:.2f}\n"
        f"Win rate: {win_rate:.2f}%"
    )


async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Configuracion\n"
        f"Exchange: {EXCHANGE}\n"
        f"Modo exchange: {EXCHANGE_MODE}\n"
        f"Watchlist: {', '.join(WATCHLIST)}\n"
        f"Temporalidades entrada: 30M, 1H, 4H, 1D\n"
        f"Producto: {selected_symbol(state.position_symbol)}\n"
        f"Apalancamiento max: {MAX_LEVERAGE:.2f}x\n"
        f"Apalancamiento dinamico: {DYNAMIC_LEVERAGE_ENABLED}\n"
        f"ADX 3x: >= {DYNAMIC_LEVERAGE_STRONG_ADX:.2f}\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"ALLOW_REAL_SPOT_SHORT: {ALLOW_REAL_SPOT_SHORT}\n"
        f"ALLOW_SHORT_SIGNALS: {ALLOW_SHORT_SIGNALS}\n"
        f"USE_CLOSED_CANDLES: {USE_CLOSED_CANDLES}\n"
        f"IA asistida: {USE_AI_ASSIST}\n"
        f"ADX threshold: {ADX_THRESHOLD:.2f}\n"
        f"Volumen minimo: {VOLUME_HEALTH_MIN:.2f}x\n"
        f"MACD MTF obligatorio: {REQUIRE_MTF_MACD_CONFIRM}\n"
        f"Riesgo por trade: {MAX_RISK_PER_TRADE * 100:.2f}%\n"
        f"Limite perdida diaria: {MAX_DAILY_LOSS * 100:.2f}%\n"
        f"Confianza minima: {MIN_CONFIDENCE:.2f}\n"
        f"Max trades por dia: {MAX_TRADES_PER_DAY}\n"
        f"Max posiciones abiertas: {MAX_OPEN_POSITIONS}\n"
        f"SL ATR: {ATR_STOP_MULTIPLIER:.2f}x\n"
        f"TP ATR: {ATR_TAKE_PROFIT_MULTIPLIER:.2f}x\n"
        f"Trailing ATR: {ATR_TRAILING_MULTIPLIER:.2f}x"
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    win_rate = (state.stats.wins / state.stats.total_trades * 100) if state.stats.total_trades else 0
    await update.message.reply_text(
        "Estadisticas\n"
        f"Trades: {state.stats.total_trades}\n"
        f"Ganados: {state.stats.wins}\n"
        f"Perdidos: {state.stats.losses}\n"
        f"Win rate: {win_rate:.2f}%\n"
        f"PnL simulado: ${state.stats.simulated_pnl_usd:.2f}\n"
        f"Mejor trade: ${state.stats.best_trade:.2f}\n"
        f"Peor trade: ${state.stats.worst_trade:.2f}"
    )


async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Ultima senal\n"
        f"Senal: {state.last_signal}\n"
        f"Confianza: {state.last_confidence:.2f}\n"
        f"Razon: {state.last_reason}"
    )


async def manage_existing_positions(app: Optional[Application]) -> List[Dict[str, Any]]:
    analyses: List[Dict[str, Any]] = []
    kept_positions: List[Dict[str, Any]] = []
    for position in list(active_positions()):
        set_state_from_position(position)
        analysis = analyze_market(state.position_symbol)
        analyses.append(analysis)
        entry_timeframe = str(position.get("entry_timeframe", "1H")).upper()
        timeframe_analysis_data = analysis.get(analysis_key_for_timeframe(entry_timeframe)) or analysis.get("entry_analysis") or analysis.get("hourly", {})
        price = float(timeframe_analysis_data.get("price", analysis.get("price", 0.0)))
        exit_reason = manage_open_position(price, timeframe_analysis_data)
        if exit_reason:
            order_side = "SELL" if state.side == "LONG" else "BUY"
            place_market_order(
                order_side,
                base_size=state.position_size_btc if state.side == "LONG" else None,
                quote_size=None if state.side == "LONG" else state.position_usd,
                leverage=float(position.get("leverage", effective_leverage(timeframe_analysis_data.get("adx", 0.0)))),
            )
            pnl = record_trade_pnl(price)
            await send_trade_to_backend(price, pnl)
            win_rate = (state.stats.wins / state.stats.total_trades * 100) if state.stats.total_trades else 0
            await send_telegram(
                app,
                f"{state.position_symbol} trade {'ganado' if pnl >= 0 else 'perdido'}\n"
                f"Resultado: ${pnl:.2f}\n"
                f"PnL acumulado: ${state.stats.simulated_pnl_usd:.2f}\n"
                f"Win Rate: {win_rate:.2f}%\n"
                f"Salida: {exit_reason}\n"
                f"Precio salida: {price:.2f}\n"
                f"Entrada: {state.entry_price:.2f}\n"
                f"Size: {state.position_size_btc:.8f}",
            )
        else:
            kept_positions.append(sync_position_from_state(position))
    state.positions = kept_positions
    sync_primary_position()
    save_state()
    return analyses


async def open_position_from_analysis(analysis: Dict[str, Any], balance: float, app: Optional[Application]) -> bool:
    if analysis.get("signal") not in ["LONG", "SHORT"]:
        return False
    symbol = str(analysis.get("symbol", WATCHLIST[0])).upper()
    if symbol in open_position_symbols():
        return False
    if len(active_positions()) >= MAX_OPEN_POSITIONS:
        return False
    if not can_trade_now(ignore_interval=len(active_positions()) > 0):
        return False
    if not DRY_RUN and analysis.get("signal") == "SHORT" and not ALLOW_REAL_SPOT_SHORT:
        logger.warning("blocked_real_short exchange=%s symbol=%s", EXCHANGE, selected_symbol(symbol))
        await send_telegram(app, "Senal SHORT bloqueada: spot no abre short real sin margin/futures.")
        return False
    if state.daily_trades >= MAX_TRADES_PER_DAY:
        logger.info("daily_trade_limit_reached count=%s", state.daily_trades)
        return False

    price = float(analysis.get("price", 0.0))
    entry_timeframe = str(analysis.get("entry_timeframe", "1H")).upper()
    entry_analysis = analysis.get("entry_analysis") or analysis.get("hourly", {})
    atr_used = float(analysis.get("atr", 0.0)) or float(entry_analysis.get("atr", 0.0))
    adx_used = float(entry_analysis.get("adx", 0.0))
    leverage_used = effective_leverage(adx_used)
    size = calculate_position_size(balance, price, atr_used, adx_used)
    usd_size = size * price
    if usd_size < MIN_ORDER_USD:
        logger.info("position_size_below_min symbol=%s usd_size=%.2f min=%.2f", symbol, usd_size, MIN_ORDER_USD)
        return False

    side = str(analysis["signal"])
    if side == "LONG":
        stop = price - atr_used * ATR_STOP_MULTIPLIER
        take = price + atr_used * ATR_TAKE_PROFIT_MULTIPLIER
        order_side = "BUY"
    else:
        stop = price + atr_used * ATR_STOP_MULTIPLIER
        take = price - atr_used * ATR_TAKE_PROFIT_MULTIPLIER
        order_side = "SELL"

    state.position_symbol = symbol
    place_market_order(order_side, quote_size=usd_size if order_side == "BUY" else None, base_size=size, leverage=leverage_used)
    opened_at = time.time()
    position = {
        "symbol": symbol,
        "entry_timeframe": entry_timeframe,
        "side": side,
        "entry_price": price,
        "position_size_btc": size,
        "position_usd": usd_size,
        "stop_loss": stop,
        "initial_stop_loss": stop,
        "take_profit": take,
        "leverage": leverage_used,
        "highest_price": price,
        "lowest_price": price,
        "last_trade_ts": opened_at,
        "last_confidence": float(analysis.get("confidence", 0.0)),
        "last_reason": str(analysis.get("reason", "")),
    }
    state.positions.append(position)
    state.daily_trades += 1
    state.last_trade_ts = opened_at
    set_state_from_position(position)
    save_state()
    logger.info(
        "position_opened symbol=%s timeframe=%s side=%s price=%.2f usd=%.2f size=%.8f leverage=%.2fx adx=%.2f stop=%.2f take=%.2f open_positions=%s",
        symbol,
        entry_timeframe,
        side,
        price,
        usd_size,
        size,
        leverage_used,
        adx_used,
        stop,
        take,
        len(active_positions()),
    )
    await send_telegram(
        app,
        f"{symbol} {'Compra' if side == 'LONG' else 'Venta'} {'simulada' if DRY_RUN else 'real'}\n"
        f"Temporalidad: {entry_timeframe}\n"
        f"Precio: {price:.2f}\nUSD: {usd_size:.2f}\nSize: {size:.8f}\n"
        f"Apalancamiento: {leverage_used:.2f}x\nADX {entry_timeframe}: {adx_used:.2f}\n"
        f"Stop: {stop:.2f}\nTake Profit: {take:.2f}\nATR usado: {atr_used:.2f}\n"
        f"Confianza: {float(analysis.get('confidence', 0.0)):.2f}\nRazon: {analysis.get('reason', '')}",
    )
    return True


# =========================
# LOOP PRINCIPAL
# =========================

async def trading_loop(app: Optional[Application]) -> None:
    await send_telegram(app, f"BTC Bot Seguro iniciado. DRY_RUN={DRY_RUN} Exchange={EXCHANGE} Producto={selected_symbol()}")
    while True:
        try:
            managed_analyses = await manage_existing_positions(app)
            open_symbols = open_position_symbols()
            scan_symbols = [symbol for symbol in WATCHLIST if symbol not in open_symbols]
            scan_analyses = [analyze_market(symbol) for symbol in scan_symbols] if len(open_symbols) < MAX_OPEN_POSITIONS else []
            analyses = managed_analyses + scan_analyses
            analysis = choose_trade_analysis(analyses)
            price = float(analysis.get("price", 0.0))
            balance = DRY_RUN_BALANCE + state.stats.simulated_pnl_usd if DRY_RUN else get_usdc_balance()
            reset_daily_balance_if_needed(balance)
            await sync_bot_control_from_backend()

            state.last_signal = analysis.get("signal", "WAIT")
            state.last_confidence = float(analysis.get("confidence", 0.0))
            state.last_reason = analysis.get("reason", "")

            if daily_loss_limit_reached(balance):
                state.active = False
                save_state()
                await send_telegram(app, "Bot pausado: limite de perdida diaria alcanzado.")
                await asyncio.sleep(ANALYZE_EVERY_SECONDS)
                continue

            logger.info(
                "cycle symbol=%s price=%.2f signal=%s confidence=%.2f equity=%.2f position_open=%s",
                analysis.get("symbol", state.position_symbol),
                price,
                state.last_signal,
                state.last_confidence,
                balance,
                len(active_positions()) > 0,
            )
            logger.info("cycle_reason %s", state.last_reason)
            ordered_analyses = [item for item in analyses if item is not analysis] + [analysis]
            await publish_analyses_to_backend(ordered_analyses)

            actionable = sorted(
                [item for item in scan_analyses if item.get("signal") in ["LONG", "SHORT"]],
                key=lambda item: float(item.get("confidence", 0.0)),
                reverse=True,
            )
            for candidate in actionable:
                if len(active_positions()) >= MAX_OPEN_POSITIONS:
                    break
                if state.daily_trades >= MAX_TRADES_PER_DAY:
                    logger.info("daily_trade_limit_reached count=%s", state.daily_trades)
                    break
                await open_position_from_analysis(candidate, balance, app)
        except Exception as exc:
            logger.exception("trading_loop_error error=%s", exc)
            await send_telegram(app, f"Error en bot:\n{str(exc)[:900]}")

        if RUN_ONCE:
            logger.info("run_once complete=true")
            break
        await asyncio.sleep(ANALYZE_EVERY_SECONDS)


async def post_init(app: Application) -> None:
    asyncio.create_task(trading_loop(app))


def validate_config() -> None:
    if EXCHANGE not in ["coinbase", "kraken"]:
        raise RuntimeError("EXCHANGE debe ser coinbase o kraken.")
    if EXCHANGE_MODE not in ["spot", "futures"]:
        raise RuntimeError("EXCHANGE_MODE debe ser spot o futures.")
    if EXCHANGE != "kraken" and EXCHANGE_MODE == "futures":
        raise RuntimeError("El modo futures solo esta permitido con EXCHANGE=kraken.")
    if MAX_LEVERAGE > MAX_ALLOWED_LEVERAGE:
        raise RuntimeError(f"MAX_LEVERAGE no puede superar {MAX_ALLOWED_LEVERAGE:.0f}x.")
    if MAX_OPEN_POSITIONS < 1:
        raise RuntimeError("MAX_OPEN_POSITIONS debe ser al menos 1.")
    if not DRY_RUN and EXCHANGE == "kraken" and EXCHANGE_MODE == "futures":
        raise RuntimeError("Kraken Futures real aun no esta habilitado. Mantén DRY_RUN=true.")
    if not DRY_RUN and not exchange_credentials_available():
        raise RuntimeError(f"Faltan credenciales para EXCHANGE={EXCHANGE}.")
    if DRY_RUN and not exchange_credentials_available():
        logger.warning("dry_run_mock_market enabled=true exchange=%s reason=missing_exchange_credentials", EXCHANGE)
    if not DRY_RUN and ALLOW_REAL_SPOT_SHORT:
        logger.warning("allow_real_spot_short enabled=true")
    if TELEGRAM_TOKEN and not CHAT_ID:
        logger.warning("CHAT_ID no configurado; Telegram deshabilitado.")
    if CHAT_ID and not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN no configurado; Telegram deshabilitado.")
    if TELEGRAM_TOKEN and CHAT_ID and not TELEGRAM_POLLING_ENABLED:
        logger.info("telegram_polling disabled=true notifications_enabled=true")
    if not BACKEND_API_URL:
        logger.info("backend_client disabled=true")


def main() -> None:
    validate_config()
    load_state()
    if not DRY_RUN and EXCHANGE == "coinbase":
        get_client()

    use_telegram = bool(TELEGRAM_TOKEN and CHAT_ID and TELEGRAM_POLLING_ENABLED)
    app: Optional[Application] = None
    if use_telegram:
        app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("pause", pause_cmd))
        app.add_handler(CommandHandler("status", status_cmd))
        app.add_handler(CommandHandler("config", config_cmd))
        app.add_handler(CommandHandler("stats", stats_cmd))
        app.add_handler(CommandHandler("signal", signal_cmd))

    logger.info(
        "startup dry_run=%s telegram_polling=%s venue=%s symbol=%s max_leverage=%.2fx max_open_positions=%s",
        DRY_RUN,
        use_telegram,
        trading_venue_label(),
        selected_symbol(),
        MAX_LEVERAGE if EXCHANGE == "kraken" and EXCHANGE_MODE == "futures" else 1.0,
        MAX_OPEN_POSITIONS,
    )
    if use_telegram:
        app.run_polling(drop_pending_updates=True)
    else:
        asyncio.run(trading_loop(None))


if __name__ == "__main__":
    main()
