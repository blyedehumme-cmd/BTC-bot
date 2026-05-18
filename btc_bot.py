#!/usr/bin/env python3
"""
BTC Bot Seguro Avanzado - Arquitectura Profesional Multi-Timeframe + IA Asistida

Fase 1: Base LONG/SHORT, multi-timeframe, trailing stop, Telegram, gestión de riesgo.
"""

import os
import time
import math
import json
import tempfile
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List

from coinbase.rest import RESTClient
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# =========================
# CONFIGURACIÓN
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.getenv("CHAT_ID", "").strip()
CB_API_KEY = os.getenv("CB_API_KEY", "").strip()
CB_API_SECRET = os.getenv("CB_API_SECRET", "").strip().replace("\\n", "\n")
PRODUCT_ID = os.getenv("PRODUCT_ID", "BTC-USDC").strip()
DRY_RUN = os.getenv("DRY_RUN", "true").lower().strip() == "true"

MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "0.0125"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.03"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.70"))
MIN_MINUTES_BETWEEN_TRADES = int(os.getenv("MIN_MINUTES_BETWEEN_TRADES", "60"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
ANALYZE_EVERY_SECONDS = int(os.getenv("ANALYZE_EVERY_SECONDS", "300"))
MAX_POSITION_BALANCE_PCT = float(os.getenv("MAX_POSITION_BALANCE_PCT", "0.25"))
MIN_ORDER_USD = float(os.getenv("MIN_ORDER_USD", "10"))
DRY_RUN_BALANCE = float(os.getenv("DRY_RUN_BALANCE", "5000"))
USE_AI_ASSIST = os.getenv("USE_AI_ASSIST", "true").lower().strip() == "true"
STATE_FILE = os.getenv("STATE_FILE", "bot_state.json")

EMA_FAST = 21
EMA_MID = 50
EMA_SLOW = 100
MACD_FAST = 21
MACD_SLOW = 50
MACD_SIGNAL = 10
ADX_PERIOD = 14
ADX_THRESHOLD = 23.0
VOLUME_HEALTH_MIN = 0.75

TIMEFRAMES = {
    "1H": "ONE_HOUR",
    "4H": "FOUR_HOUR",
    "1D": "ONE_DAY",
    "1W": "ONE_WEEK",
}

CANDLE_LIMITS = {
    "1H": 160,
    "4H": 120,
    "1D": 140,
    "1W": 120,
}

# =========================
# LOGGING
# =========================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("btc-bot-advanced")

client: Optional[RESTClient] = None

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
    entry_price: float = 0.0
    position_size_btc: float = 0.0
    position_usd: float = 0.0
    stop_loss: float = 0.0
    initial_stop_loss: float = 0.0
    take_profit: float = 0.0
    highest_price: float = 0.0
    last_trade_ts: float = 0.0
    day: str = ""
    starting_day_balance: float = 0.0
    last_signal: str = "WAIT"
    last_confidence: float = 0.0
    last_reason: str = "Sin análisis todavía."
    stats: TradeStats = field(default_factory=TradeStats)
    trade_history: List[Dict[str, Any]] = field(default_factory=list)
    daily_trades: int = 0
    lowest_price: float = 0.0

state = BotState()


def save_state():
    directory = os.path.dirname(os.path.abspath(STATE_FILE)) or "."
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="bot_state_", suffix=".json", dir=directory)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(state.__dict__, file, default=lambda o: o.__dict__, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, STATE_FILE)
    except Exception as e:
        logger.error("Error guardando estado: %s", e)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def load_state():
    global state
    if not os.path.exists(STATE_FILE):
        logger.info("No existe archivo de estado.")
        return
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        stats_data = data.get("stats", {})
        state = BotState(
            active=bool(data.get("active", True)),
            position_open=bool(data.get("position_open", False)),
            side=data.get("side"),
            entry_price=float(data.get("entry_price", 0.0)),
            position_size_btc=float(data.get("position_size_btc", 0.0)),
            position_usd=float(data.get("position_usd", 0.0)),
            stop_loss=float(data.get("stop_loss", 0.0)),
            initial_stop_loss=float(data.get("initial_stop_loss", 0.0)),
            take_profit=float(data.get("take_profit", 0.0)),
            highest_price=float(data.get("highest_price", 0.0)),
            last_trade_ts=float(data.get("last_trade_ts", 0.0)),
            day=str(data.get("day", "")),
            starting_day_balance=float(data.get("starting_day_balance", 0.0)),
            last_signal=str(data.get("last_signal", "WAIT")),
            last_confidence=float(data.get("last_confidence", 0.0)),
            last_reason=str(data.get("last_reason", "")),
            stats=TradeStats(
                total_trades=int(stats_data.get("total_trades", 0)),
                wins=int(stats_data.get("wins", 0)),
                losses=int(stats_data.get("losses", 0)),
                simulated_pnl_usd=float(stats_data.get("simulated_pnl_usd", 0.0)),
                best_trade=float(stats_data.get("best_trade", 0.0)),
                worst_trade=float(stats_data.get("worst_trade", 0.0)),
            ),
            trade_history=data.get("trade_history", []),
            daily_trades=int(data.get("daily_trades", 0)),
            lowest_price=float(data.get("lowest_price", 0.0)),
        )
        logger.info("Estado cargado correctamente.")
    except Exception as e:
        logger.error("Error cargando estado: %s", e)


# =========================
# API CLIENT
# =========================

def get_client() -> RESTClient:
    global client
    if client is None:
        if not CB_API_KEY or not CB_API_SECRET:
            raise RuntimeError("Faltan CB_API_KEY o CB_API_SECRET en Render.")
        client = RESTClient(api_key=CB_API_KEY, api_secret=CB_API_SECRET)
    return client


def get_timeframe_candles(timeframe: str, limit: int) -> List[Dict[str, Any]]:
    granularity = TIMEFRAMES[timeframe]
    end_ts = int(time.time())
    start_ts = end_ts - (limit * {
        "1H": 3600,
        "4H": 14400,
        "1D": 86400,
        "1W": 604800,
    }[timeframe])
    cb = get_client()
    response = cb.get_candles(product_id=PRODUCT_ID, start=str(start_ts), end=str(end_ts), granularity=granularity)
    candles = getattr(response, "candles", None)
    if candles is None and isinstance(response, dict):
        candles = response.get("candles", [])
    result = []
    for c in candles:
        if isinstance(c, dict):
            result.append(c)
        else:
            result.append({
                "start": getattr(c, "start", 0),
                "low": getattr(c, "low", 0),
                "high": getattr(c, "high", 0),
                "open": getattr(c, "open", 0),
                "close": getattr(c, "close", 0),
                "volume": getattr(c, "volume", 0),
            })
    return sorted(result, key=lambda x: int(x.get("start", 0)))


def get_usdc_balance() -> float:
    if DRY_RUN:
        return DRY_RUN_BALANCE
    cb = get_client()
    response = cb.get_accounts()
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


def place_market_order(side: str, quote_size: Optional[float] = None, base_size: Optional[float] = None) -> Dict[str, Any]:
    if DRY_RUN:
        logger.info("[DRY_RUN] Orden simulada: %s quote=%s base=%s", side, quote_size, base_size)
        return {"dry_run": True, "side": side, "quote_size": quote_size, "base_size": base_size}
    cb = get_client()
    client_order_id = f"btc-bot-{int(time.time())}"
    if side.upper() == "BUY":
        return cb.market_order_buy(client_order_id=client_order_id, product_id=PRODUCT_ID, quote_size=str(round(float(quote_size), 2)))
    return cb.market_order_sell(client_order_id=client_order_id, product_id=PRODUCT_ID, base_size=str(round(float(base_size), 8)))


# =========================
# INDICADORES
# =========================

def ema(values: List[float], period: int) -> float:
    if not values or period <= 0:
        return 0.0
    k = 2 / (period + 1)
    e = values[0]
    for price in values[1:]:
        e = price * k + e * (1 - k)
    return e


def macd(values: List[float]) -> Dict[str, float]:
    if len(values) < MACD_SLOW + MACD_SIGNAL:
        return {"macd": 0.0, "signal": 0.0, "hist": 0.0}
    macd_line = ema(values, MACD_FAST) - ema(values, MACD_SLOW)
    macd_series = []
    for i in range(MACD_SLOW + MACD_SIGNAL, len(values) + 1):
        window = values[:i]
        macd_series.append(ema(window, MACD_FAST) - ema(window, MACD_SLOW))
    signal = ema(macd_series[-MACD_SIGNAL:], MACD_SIGNAL) if len(macd_series) >= MACD_SIGNAL else macd_line
    return {"macd": macd_line, "signal": signal, "hist": macd_line - signal}


def adx(candles: List[Dict[str, Any]], period: int = ADX_PERIOD) -> float:
    if len(candles) < period + 2:
        return 0.0
    tr = []
    plus_dm = []
    minus_dm = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_high = float(candles[i - 1]["high"])
        prev_low = float(candles[i - 1]["low"])
        tr.append(max(high - low, abs(high - float(candles[i - 1]["close"])), abs(low - float(candles[i - 1]["close"]))))
        up_move = high - prev_high
        down_move = prev_low - low
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0.0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0.0)
    atr_val = sum(tr[-period:]) / period
    plus_di = 100 * (sum(plus_dm[-period:]) / atr_val) if atr_val else 0.0
    minus_di = 100 * (sum(minus_dm[-period:]) / atr_val) if atr_val else 0.0
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if plus_di + minus_di else 0.0
    return dx


def bollinger(values: List[float], period: int = 20, mult: float = 2.0) -> Dict[str, float]:
    if len(values) < 2:
        return {"upper": 0.0, "middle": 0.0, "lower": 0.0, "width_pct": 0.0}
    recent = values[-period:] if len(values) >= period else values
    mid = sum(recent) / len(recent)
    variance = sum((x - mid) ** 2 for x in recent) / len(recent)
    std = math.sqrt(variance)
    width_pct = ((2 * mult * std) / mid * 100) if mid else 0.0
    return {"upper": mid + mult * std, "middle": mid, "lower": mid - mult * std, "width_pct": width_pct}


def volume_ratio(candles: List[Dict[str, Any]], period: int = 20) -> float:
    volumes = [float(c.get("volume", 0)) for c in candles]
    if len(volumes) < period + 1:
        return 1.0
    avg = sum(volumes[-period - 1:-1]) / period
    return volumes[-1] / avg if avg else 1.0


# =========================
# ESTRATEGIA MULTI-TIMEFRAME
# =========================

def timeframe_analysis(candles: List[Dict[str, Any]], timeframe: str) -> Dict[str, Any]:
    closes = [float(c["close"]) for c in candles]
    if len(closes) < EMA_SLOW + 1:
        return {
            "trend": "neutral",
            "price": closes[-1] if closes else 0.0,
            "ema21": 0.0,
            "ema50": 0.0,
            "ema100": 0.0,
            "macd": {"macd": 0.0, "signal": 0.0, "hist": 0.0},
            "adx": 0.0,
            "volume_ratio": 1.0,
        }
    ema21_val = ema(closes[-80:], EMA_FAST)
    ema50_val = ema(closes[-120:], EMA_MID)
    ema100_val = ema(closes[-160:], EMA_SLOW)
    macd_val = macd(closes)
    adx_val = adx(candles[-(ADX_PERIOD + 1):])
    vol_ratio = volume_ratio(candles)
    price = closes[-1]
    trend = "bull" if ema21_val > ema50_val and price > ema100_val else "bear" if ema21_val < ema50_val and price < ema100_val else "neutral"
    return {
        "trend": trend,
        "price": price,
        "ema21": ema21_val,
        "ema50": ema50_val,
        "ema100": ema100_val,
        "macd": macd_val,
        "adx": adx_val,
        "volume_ratio": vol_ratio,
    }


def ai_quality_filter(analysis: Dict[str, Any]) -> bool:
    if analysis["adx"] < ADX_THRESHOLD:
        return False
    if analysis["volume_ratio"] < VOLUME_HEALTH_MIN:
        return False
    return True


def ai_assist_analysis(weekly: Dict[str, Any], daily: Dict[str, Any], fourh: Dict[str, Any], hourly: Dict[str, Any]) -> Dict[str, Any]:
    score = 0.0
    reasons: List[str] = []

    if hourly["adx"] >= ADX_THRESHOLD:
        score += 0.25
        reasons.append("ADX fuerte en 1H")
    else:
        reasons.append("ADX débil en 1H")

    if hourly["volume_ratio"] >= VOLUME_HEALTH_MIN:
        score += 0.20
        reasons.append("Volumen saludable en 1H")
    else:
        reasons.append("Volumen bajo en 1H")

    macd_hist = hourly["macd"]["hist"]
    if abs(macd_hist) >= 0.05:
        score += 0.15
        reasons.append("Momentum MACD significativo en 1H")
    else:
        reasons.append("Momentum MACD débil en 1H")

    if weekly["trend"] != "neutral":
        score += 0.15
        reasons.append(f"Tendencia 1W {weekly['trend']}")
    else:
        reasons.append("Tendencia 1W neutral")

    if daily["trend"] != "neutral":
        score += 0.15
        reasons.append(f"Tendencia 1D {daily['trend']}")
    else:
        reasons.append("Tendencia 1D neutral")

    allow = score >= 0.60
    return {"allow": allow, "score": score, "reasons": reasons}


def build_signal(weekly: Dict[str, Any], daily: Dict[str, Any], fourh: Dict[str, Any], hourly: Dict[str, Any]) -> Dict[str, Any]:
    good_weekly_long = weekly["trend"] in ["bull", "neutral"] and weekly["price"] >= weekly["ema100"]
    good_daily_long = daily["trend"] == "bull"
    good_4h_long = fourh["trend"] == "bull"
    good_hour_long = hourly["trend"] == "bull" and hourly["macd"]["hist"] > 0

    good_weekly_short = weekly["trend"] in ["bear", "neutral"] and weekly["price"] <= weekly["ema100"]
    good_daily_short = daily["trend"] == "bear"
    good_4h_short = fourh["trend"] == "bear"
    good_hour_short = hourly["trend"] == "bear" and hourly["macd"]["hist"] < 0

    long_confidence = 0.0
    short_confidence = 0.0
    long_reasons: List[str] = []
    short_reasons: List[str] = []

    if good_weekly_long:
        long_confidence += 0.18
        long_reasons.append("1W bullish/neutral")
    if good_daily_long:
        long_confidence += 0.20
        long_reasons.append("1D bullish")
    if good_4h_long:
        long_confidence += 0.20
        long_reasons.append("4H bullish")
    if good_hour_long:
        long_confidence += 0.18
        long_reasons.append("1H confirmación bullish")
    if hourly["adx"] >= ADX_THRESHOLD:
        long_confidence += 0.12
        long_reasons.append("ADX fuerte")
    if hourly["volume_ratio"] >= VOLUME_HEALTH_MIN:
        long_confidence += 0.12
        long_reasons.append("Volumen saludable")

    if good_weekly_short:
        short_confidence += 0.18
        short_reasons.append("1W bearish/neutral")
    if good_daily_short:
        short_confidence += 0.20
        short_reasons.append("1D bearish")
    if good_4h_short:
        short_confidence += 0.20
        short_reasons.append("4H bearish")
    if good_hour_short:
        short_confidence += 0.18
        short_reasons.append("1H confirmación bearish")
    if hourly["adx"] >= ADX_THRESHOLD:
        short_confidence += 0.12
        short_reasons.append("ADX fuerte")
    if hourly["volume_ratio"] >= VOLUME_HEALTH_MIN:
        short_confidence += 0.12
        short_reasons.append("Volumen saludable")

    atr_value = abs(hourly["price"] - hourly["ema21"])
    if atr_value <= 0:
        atr_value = abs(hourly["price"] - hourly["ema50"])

    ai_evaluation = ai_assist_analysis(weekly, daily, fourh, hourly)
    if USE_AI_ASSIST:
        ai_reason = f"IA: {'|'.join(ai_evaluation['reasons'])}"
    else:
        ai_reason = "IA desactivada"

    if long_confidence >= MIN_CONFIDENCE and ai_quality_filter(hourly):
        if USE_AI_ASSIST and not ai_evaluation["allow"]:
            return {
                "signal": "WAIT",
                "confidence": long_confidence,
                "reason": f"Faltó confirmación IA: {', '.join(ai_evaluation['reasons'])}",
                "price": hourly["price"],
                "atr": atr_value,
            }
        return {
            "signal": "LONG",
            "confidence": long_confidence,
            "reason": ", ".join(long_reasons) + ". " + ai_reason,
            "price": hourly["price"],
            "atr": atr_value,
        }
    if short_confidence >= MIN_CONFIDENCE and ai_quality_filter(hourly):
        if USE_AI_ASSIST and not ai_evaluation["allow"]:
            return {
                "signal": "WAIT",
                "confidence": short_confidence,
                "reason": f"Faltó confirmación IA: {', '.join(ai_evaluation['reasons'])}",
                "price": hourly["price"],
                "atr": atr_value,
            }
        return {
            "signal": "SHORT",
            "confidence": short_confidence,
            "reason": ", ".join(short_reasons) + ". " + ai_reason,
            "price": hourly["price"],
            "atr": atr_value,
        }

    return {"signal": "WAIT", "confidence": 0.0, "reason": f"No se cumplen condiciones multi-timeframe. {ai_reason}", "price": hourly["price"], "atr": 0.0}


def analyze_market() -> Dict[str, Any]:
    candles_1w = get_timeframe_candles("1W", CANDLE_LIMITS["1W"])
    candles_1d = get_timeframe_candles("1D", CANDLE_LIMITS["1D"])
    candles_4h = get_timeframe_candles("4H", CANDLE_LIMITS["4H"])
    candles_1h = get_timeframe_candles("1H", CANDLE_LIMITS["1H"])

    if any(len(c) < 60 for c in [candles_1w, candles_1d, candles_4h, candles_1h]):
        return {"signal": "WAIT", "confidence": 0.0, "price": 0.0, "atr": 0.0, "reason": "No hay suficientes velas en todas las temporalidades."}

    weekly = timeframe_analysis(candles_1w, "1W")
    daily = timeframe_analysis(candles_1d, "1D")
    fourh = timeframe_analysis(candles_4h, "4H")
    hourly = timeframe_analysis(candles_1h, "1H")

    signal = build_signal(weekly, daily, fourh, hourly)
    signal.update({"weekly": weekly, "daily": daily, "fourh": fourh, "hourly": hourly})
    return signal


# =========================
# GESTIÓN DEL RIESGO
# =========================

def can_trade_now() -> bool:
    if not state.active or state.position_open:
        return False
    if state.last_trade_ts == 0:
        return True
    return (time.time() - state.last_trade_ts) >= MIN_MINUTES_BETWEEN_TRADES * 60


def reset_daily_balance_if_needed(balance: float):
    today = date.today().isoformat()
    if state.day != today:
        state.day = today
        state.starting_day_balance = balance
        state.daily_trades = 0
        logger.info("Nuevo día. Balance inicial: %.2f", balance)


def daily_loss_limit_reached(balance: float) -> bool:
    if state.starting_day_balance <= 0:
        return False
    drawdown = (state.starting_day_balance - balance) / state.starting_day_balance
    return drawdown >= MAX_DAILY_LOSS


def calculate_position_size(balance: float, price: float, atr_val: float) -> float:
    if atr_val <= 0 or price <= 0:
        return 0.0
    risk_amount = balance * MAX_RISK_PER_TRADE
    stop_distance = atr_val * 1.5
    if stop_distance <= 0:
        return 0.0
    btc_size = risk_amount / stop_distance
    usd_size = btc_size * price
    usd_size = min(usd_size, balance * MAX_POSITION_BALANCE_PCT)
    if usd_size < MIN_ORDER_USD:
        return 0.0
    return usd_size / price


def record_trade_pnl(exit_price: float):
    pnl = (exit_price - state.entry_price) * state.position_size_btc if state.side == "LONG" else (state.entry_price - exit_price) * state.position_size_btc
    s = state.stats
    s.total_trades += 1
    state.daily_trades += 1
    if pnl >= 0:
        s.wins += 1
    else:
        s.losses += 1
    s.simulated_pnl_usd += pnl
    s.best_trade = max(s.best_trade, pnl)
    s.worst_trade = min(s.worst_trade, pnl)
    state.trade_history.append({
        "timestamp": int(time.time()),
        "side": state.side,
        "entry": state.entry_price,
        "exit": exit_price,
        "pnl": pnl,
        "position_size_btc": state.position_size_btc,
        "confidence": state.last_confidence,
        "reason": state.last_reason,
    })


def manage_open_position(price: float, hourly: Dict[str, Any]) -> Optional[str]:
    if state.side == "LONG":
        state.highest_price = max(state.highest_price, price)
        if price <= state.stop_loss:
            return "STOP_LOSS"
        if price >= state.take_profit:
            return "TAKE_PROFIT"
        if hourly["adx"] >= ADX_THRESHOLD:
            trailing_stop = state.highest_price - (hourly["price"] * 0.01)
            state.stop_loss = max(state.stop_loss, trailing_stop)
    elif state.side == "SHORT":
        state.lowest_price = min(state.lowest_price if state.lowest_price > 0 else price, price)
        if price >= state.stop_loss:
            return "STOP_LOSS"
        if price <= state.take_profit:
            return "TAKE_PROFIT"
        if hourly["adx"] >= ADX_THRESHOLD:
            trailing_stop = state.lowest_price + (hourly["price"] * 0.01)
            state.stop_loss = min(state.stop_loss, trailing_stop)
    return None


# =========================
# TELEGRAM
# =========================

async def send_telegram(app: Optional[Application], message: str):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        logger.info("Telegram no configurado: %s", message)
        return
    if app is None:
        logger.info("Telegram no inicializado: %s", message)
        return
    try:
        await app.bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        logger.error("Error enviando Telegram: %s", e)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.active = True
    save_state()
    await update.message.reply_text("✅ BTC Bot Seguro activo.")


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.active = False
    save_state()
    await update.message.reply_text("⏸ Bot pausado. No abrirá nuevas operaciones.")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.stats
    win_rate = (s.wins / s.total_trades * 100) if s.total_trades else 0
    await update.message.reply_text(
        "📊 Estado del bot\n"
        f"Activo: {state.active}\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"Producto: {PRODUCT_ID}\n"
        f"Posición abierta: {state.position_open}\n"
        f"Side: {state.side}\n"
        f"Entrada: {state.entry_price:.2f}\n"
        f"BTC: {state.position_size_btc:.8f}\n"
        f"Stop Loss: {state.stop_loss:.2f}\n"
        f"Take Profit: {state.take_profit:.2f}\n"
        f"Trades día: {state.daily_trades}\n"
        f"Win rate: {win_rate:.2f}%"
    )


async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Configuración\n"
        f"Producto: {PRODUCT_ID}\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"IA asistida: {USE_AI_ASSIST}\n"
        f"Riesgo por trade: {MAX_RISK_PER_TRADE*100:.2f}%\n"
        f"Límite pérdida diaria: {MAX_DAILY_LOSS*100:.2f}%\n"
        f"Confianza mínima: {MIN_CONFIDENCE:.2f}\n"
        f"Min min entre trades: {MIN_MINUTES_BETWEEN_TRADES}\n"
        f"Max trades por día: {MAX_TRADES_PER_DAY}\n"
        f"ADX threshold: {ADX_THRESHOLD}\n"
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = state.stats
    win_rate = (s.wins / s.total_trades * 100) if s.total_trades else 0
    await update.message.reply_text(
        "📈 Estadísticas\n"
        f"Trades: {s.total_trades}\n"
        f"Ganados: {s.wins}\n"
        f"Perdidos: {s.losses}\n"
        f"Win rate: {win_rate:.2f}%\n"
        f"PnL simulado: ${s.simulated_pnl_usd:.2f}\n"
        f"Mejor trade: ${s.best_trade:.2f}\n"
        f"Peor trade: ${s.worst_trade:.2f}"
    )


async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 Última señal\n"
        f"Señal: {state.last_signal}\n"
        f"Confianza: {state.last_confidence:.2f}\n"
        f"Razón: {state.last_reason}"
    )


# =========================
# BUCLE PRINCIPAL
# =========================

async def trading_loop(app: Application):
    await send_telegram(app, f"🚀 BTC Bot Seguro Avanzado iniciado. DRY_RUN: {DRY_RUN} Producto: {PRODUCT_ID}")
    while True:
        try:
            analysis = analyze_market()
            price = analysis.get("price", 0.0)
            balance = get_usdc_balance()
            reset_daily_balance_if_needed(balance)
            state.last_signal = analysis["signal"]
            state.last_confidence = analysis["confidence"]
            state.last_reason = analysis["reason"]
            if daily_loss_limit_reached(balance):
                state.active = False
                save_state()
                await send_telegram(app, "🛑 Bot pausado: límite de pérdida diaria alcanzado.")
                await asyncio.sleep(ANALYZE_EVERY_SECONDS)
                continue
            logger.info("Precio %.2f | Señal %s | Confianza %.2f | %s", price, analysis["signal"], analysis["confidence"], state.last_reason)
            if state.position_open:
                exit_reason = manage_open_position(price, analysis["hourly"])
                if exit_reason:
                    place_market_order("SELL" if state.side == "LONG" else "BUY", base_size=state.position_size_btc if state.side == "LONG" else None, quote_size=None if state.side == "LONG" else state.position_usd)
                    record_trade_pnl(price)
                    pnl = (price - state.entry_price) * state.position_size_btc if state.side == "LONG" else (state.entry_price - price) * state.position_size_btc
                    win_rate = (state.stats.wins / state.stats.total_trades * 100) if state.stats.total_trades else 0
                    await send_telegram(app, f"{('🟢' if pnl >= 0 else '🔴')} Trade {('ganado' if pnl >= 0 else 'perdido')}\nResultado: ${pnl:.2f}\nPnL acumulado: ${state.stats.simulated_pnl_usd:.2f}\nWin Rate: {win_rate:.2f}%\nSalida: {exit_reason}\nPrecio salida: {price:.2f}\nEntrada: {state.entry_price:.2f}\nBTC: {state.position_size_btc:.8f}")
                    state.position_open = False
                    state.side = None
                    state.entry_price = 0.0
                    state.position_size_btc = 0.0
                    state.position_usd = 0.0
                    state.stop_loss = 0.0
                    state.initial_stop_loss = 0.0
                    state.take_profit = 0.0
                    state.highest_price = 0.0
                    state.last_trade_ts = time.time()
                    save_state()
            elif can_trade_now() and analysis["signal"] in ["LONG", "SHORT"]:
                if state.daily_trades >= MAX_TRADES_PER_DAY:
                    logger.info("Máximo trades por día alcanzado: %s", state.daily_trades)
                else:
                    atr_estimate = abs(analysis["hourly"]["price"] - analysis["hourly"]["ema21"])
                    btc_size = calculate_position_size(balance, price, atr_estimate)
                    usd_size = btc_size * price
                    if usd_size >= MIN_ORDER_USD:
                        if analysis["signal"] == "LONG":
                            stop = price - atr_estimate * 1.5
                            take = price + atr_estimate * 3.0
                        else:
                            stop = price + atr_estimate * 1.5
                            take = price - atr_estimate * 3.0
                        place_market_order("BUY" if analysis["signal"] == "LONG" else "SELL", quote_size=usd_size if analysis["signal"] == "LONG" else None, base_size=None if analysis["signal"] == "LONG" else btc_size)
                        state.position_open = True
                        state.side = analysis["signal"]
                        state.entry_price = price
                        state.position_size_btc = btc_size
                        state.position_usd = usd_size
                        state.stop_loss = stop
                        state.initial_stop_loss = stop
                        state.take_profit = take
                        state.highest_price = price
                        state.lowest_price = price
                        state.last_trade_ts = time.time()
                        save_state()
                        await send_telegram(app, f"🟢 {'Compra' if analysis['signal'] == 'LONG' else 'Venta'} {'simulada' if DRY_RUN else 'real'}\nPrecio: {price:.2f}\nUSD: {usd_size:.2f}\nBTC: {btc_size:.8f}\nStop: {stop:.2f}\nTake Profit: {take:.2f}\nConfianza: {analysis['confidence']:.2f}\nRazón: {analysis['reason']}")
        except Exception as e:
            logger.exception("Error en loop principal")
            await send_telegram(app, f"⚠️ Error en bot:\n{str(e)[:900]}")
        await asyncio.sleep(ANALYZE_EVERY_SECONDS)


async def post_init(app: Application):
    asyncio.create_task(trading_loop(app))


def validate_config():
    if not DRY_RUN and (not CB_API_KEY or not CB_API_SECRET):
        raise RuntimeError("Faltan CB_API_KEY o CB_API_SECRET.")
    if DRY_RUN and (not CB_API_KEY or not CB_API_SECRET):
        logger.warning("DRY_RUN activo y faltan credenciales de Coinbase; no se ejecutarán órdenes reales.")
    if TELEGRAM_TOKEN and not CHAT_ID:
        logger.warning("CHAT_ID no configurado; Telegram deshabilitado.")
    if CHAT_ID and not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN no configurado; Telegram deshabilitado.")


def main():
    validate_config()
    load_state()

    if not DRY_RUN:
        get_client()

    use_telegram = bool(TELEGRAM_TOKEN and CHAT_ID)
    app: Optional[Application] = None
    if use_telegram:
        app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.add_handler(CommandHandler("start", start_cmd))
        app.add_handler(CommandHandler("pause", pause_cmd))
        app.add_handler(CommandHandler("status", status_cmd))
        app.add_handler(CommandHandler("config", config_cmd))
        app.add_handler(CommandHandler("stats", stats_cmd))
        app.add_handler(CommandHandler("signal", signal_cmd))

    logger.info("Iniciando BTC Bot Seguro Avanzado... DRY_RUN=%s Telegram=%s", DRY_RUN, "habilitado" if use_telegram else "deshabilitado")

    if use_telegram:
        app.run_polling()
    else:
        asyncio.run(trading_loop(None))


if __name__ == "__main__":
    main()
