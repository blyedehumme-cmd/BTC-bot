#!/usr/bin/env python3
"""
BTC Bot Seguro Avanzado - Coinbase Advanced Trade + Telegram

Versión con cliente oficial RESTClient de Coinbase.

Variables necesarias en Render:
TELEGRAM_TOKEN
CHAT_ID
CB_API_KEY
CB_API_SECRET
DRY_RUN=true

Recomendado:
PYTHON_VERSION=3.11.9
"""

import os
import time
import math
import json
import tempfile
import logging
import asyncio
from dataclasses import dataclass, field
from datetime import date
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

# Riesgo solicitado: 1.5 %
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "0.015"))

MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.03"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.76"))
MIN_MINUTES_BETWEEN_TRADES = int(os.getenv("MIN_MINUTES_BETWEEN_TRADES", "60"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "3"))
ANALYZE_EVERY_SECONDS = int(os.getenv("ANALYZE_EVERY_SECONDS", "300"))

STOP_LOSS_ATR_MULTIPLIER = float(os.getenv("STOP_LOSS_ATR_MULTIPLIER", "1.8"))
TAKE_PROFIT_ATR_MULTIPLIER = float(os.getenv("TAKE_PROFIT_ATR_MULTIPLIER", "3.0"))
TRAILING_STOP_ATR_MULTIPLIER = float(os.getenv("TRAILING_STOP_ATR_MULTIPLIER", "1.4"))
BREAK_EVEN_TRIGGER_R = float(os.getenv("BREAK_EVEN_TRIGGER_R", "1.0"))

MAX_POSITION_BALANCE_PCT = float(os.getenv("MAX_POSITION_BALANCE_PCT", "0.25"))
MIN_ORDER_USD = float(os.getenv("MIN_ORDER_USD", "10"))
DRY_RUN_BALANCE = float(os.getenv("DRY_RUN_BALANCE", "500"))
STATE_FILE = os.getenv("STATE_FILE", "bot_state.json")

# =========================
# LOGGING
# =========================

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("btc-bot-restclient")


# =========================
# COINBASE CLIENT
# =========================

client: Optional[RESTClient] = None


def get_client() -> RESTClient:
    global client
    if client is None:
        if not CB_API_KEY or not CB_API_SECRET:
            raise RuntimeError("Faltan CB_API_KEY o CB_API_SECRET en Render.")
        client = RESTClient(api_key=CB_API_KEY, api_secret=CB_API_SECRET)
    return client


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


state = BotState()
def save_state():
    """
    Guarda el estado actual del bot en un archivo JSON.
    """

    directory = os.path.dirname(os.path.abspath(STATE_FILE)) or "."
    temp_path = None

    try:
        fd, temp_path = tempfile.mkstemp(
            prefix="bot_state_",
            suffix=".json",
            dir=directory
        )

        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "active": state.active,
                    "position_open": state.position_open,
                    "entry_price": state.entry_price,
                    "position_size_btc": state.position_size_btc,
                    "position_usd": state.position_usd,
                    "stop_loss": state.stop_loss,
                    "initial_stop_loss": state.initial_stop_loss,
                    "take_profit": state.take_profit,
                    "highest_price": state.highest_price,
                    "last_trade_ts": state.last_trade_ts,
                    "day": state.day,
                    "starting_day_balance": state.starting_day_balance,
                    "last_signal": state.last_signal,
                    "last_confidence": state.last_confidence,
                    "last_reason": state.last_reason,
                    "stats": {
                        "total_trades": state.stats.total_trades,
                        "wins": state.stats.wins,
                        "losses": state.stats.losses,
                        "simulated_pnl_usd": state.stats.simulated_pnl_usd,
                        "best_trade": state.stats.best_trade,
                        "worst_trade": state.stats.worst_trade,
                    },
                },
                file,
                indent=2
            )

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
    """
    Carga el estado guardado del bot.
    """

    global state

    if not os.path.exists(STATE_FILE):
        logger.info("No existe archivo de estado.")
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        stats_data = data.get("stats", {})

        state.active = bool(data.get("active", True))
        state.position_open = bool(data.get("position_open", False))
        state.entry_price = float(data.get("entry_price", 0.0))
        state.position_size_btc = float(data.get("position_size_btc", 0.0))
        state.position_usd = float(data.get("position_usd", 0.0))
        state.stop_loss = float(data.get("stop_loss", 0.0))
        state.initial_stop_loss = float(data.get("initial_stop_loss", 0.0))
        state.take_profit = float(data.get("take_profit", 0.0))
        state.highest_price = float(data.get("highest_price", 0.0))
        state.last_trade_ts = float(data.get("last_trade_ts", 0.0))
        state.day = str(data.get("day", ""))
        state.starting_day_balance = float(data.get("starting_day_balance", 0.0))
        state.last_signal = str(data.get("last_signal", "WAIT"))
        state.last_confidence = float(data.get("last_confidence", 0.0))
        state.last_reason = str(data.get("last_reason", ""))

        state.stats.total_trades = int(stats_data.get("total_trades", 0))
        state.stats.wins = int(stats_data.get("wins", 0))
        state.stats.losses = int(stats_data.get("losses", 0))
        state.stats.simulated_pnl_usd = float(stats_data.get("simulated_pnl_usd", 0.0))
        state.stats.best_trade = float(stats_data.get("best_trade", 0.0))
        state.stats.worst_trade = float(stats_data.get("worst_trade", 0.0))

        logger.info("Estado cargado correctamente.")

    except Exception as e:
        logger.error("Error cargando estado: %s", e)

# =========================
# TELEGRAM
# =========================

async def send_telegram(app: Optional[Application], message: str):
    if not TELEGRAM_TOKEN or not CHAT_ID: 
        logger.info("Telegram no configurado: %s", message)
        return
    try:
        if app:
            await app.bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        logger.error("Error enviando Telegram: %s", e)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.active = True
    save_state()
    
    await update.message.reply_text(
        "✅ BTC Bot Seguro activo.\n\n"
        "Comandos:\n"
        "/status - Ver estado\n"
        "/pause - Pausar bot\n"
        "/start - Activar bot\n"
        "/dryrun - Ver si opera real o simulación\n"
        "/stats - Ver estadísticas\n"
        "/signal - Ver última señal\n"
        "/config - Ver configuración"
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Estado del bot\n"
        f"Activo: {state.active}\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"Producto: {PRODUCT_ID}\n"
        f"Posición abierta: {state.position_open}\n"
        f"Entrada: {state.entry_price:.2f}\n"
        f"BTC: {state.position_size_btc:.8f}\n"
        f"Stop Loss: {state.stop_loss:.2f}\n"
        f"Take Profit: {state.take_profit:.2f}\n"
        f"Riesgo por trade: {MAX_RISK_PER_TRADE*100:.2f}%\n"
        f"Límite pérdida diaria: {MAX_DAILY_LOSS*100:.2f}%"
    )


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.active = False
    save_state()
    
    await update.message.reply_text("⏸ Bot pausado. No abrirá nuevas operaciones.")


async def dryrun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if DRY_RUN:
        await update.message.reply_text("🧪 DRY_RUN=True. El bot está en simulación y NO opera dinero real.")
    else:
        await update.message.reply_text("⚠️ DRY_RUN=False. El bot puede operar con dinero REAL.")


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


async def config_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Configuración\n"
        f"Producto: {PRODUCT_ID}\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"Riesgo por trade: {MAX_RISK_PER_TRADE*100:.2f}%\n"
        f"Límite pérdida diaria: {MAX_DAILY_LOSS*100:.2f}%\n"
        f"Confianza mínima: {MIN_CONFIDENCE:.2f}\n"
        f"Tiempo mínimo entre trades: {MIN_MINUTES_BETWEEN_TRADES} minutos\n"
        f"Stop ATR: {STOP_LOSS_ATR_MULTIPLIER}\n"
        f"Take Profit ATR: {TAKE_PROFIT_ATR_MULTIPLIER}\n"
        f"Trailing Stop ATR: {TRAILING_STOP_ATR_MULTIPLIER}"
    )


# =========================
# COINBASE FUNCTIONS
# =========================

def get_candles(granularity: str = "FIVE_MINUTE", limit: int = 180) -> List[Dict[str, Any]]:
    end = int(time.time())
    start = end - (limit * 300)

    cb = get_client()
    response = cb.get_candles(
        product_id=PRODUCT_ID,
        start=str(start),
        end=str(end),
        granularity=granularity
    )

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


def place_market_order(side: str, quote_size: Optional[float] = None, base_size: Optional[float] = None):
    if DRY_RUN:
        logger.info("[DRY_RUN] Orden simulada: side=%s quote=%s base=%s", side, quote_size, base_size)
        return {"dry_run": True}

    cb = get_client()
    client_order_id = f"btc-bot-{int(time.time())}"

    if side.upper() == "BUY":
        return cb.market_order_buy(
            client_order_id=client_order_id,
            product_id=PRODUCT_ID,
            quote_size=str(round(float(quote_size), 2))
        )

    return cb.market_order_sell(
        client_order_id=client_order_id,
        product_id=PRODUCT_ID,
        base_size=str(round(float(base_size), 8))
    )


# =========================
# INDICADORES
# =========================

def ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    k = 2 / (period + 1)
    e = values[0]
    for price in values[1:]:
        e = price * k + e * (1 - k)
    return e


def rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0

    gains, losses = [], []
    for i in range(-period, 0):
        change = values[i] - values[i - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values: List[float]) -> Dict[str, float]:
    macd_line = ema(values, 12) - ema(values, 26)
    macd_series = []

    for i in range(35, len(values) + 1):
        sub = values[:i]
        macd_series.append(ema(sub, 12) - ema(sub, 26))

    signal = ema(macd_series[-9:], 9) if len(macd_series) >= 9 else macd_line
    return {"macd": macd_line, "signal": signal, "hist": macd_line - signal}


def bollinger(values: List[float], period: int = 20, mult: float = 2.0) -> Dict[str, float]:
    recent = values[-period:] if len(values) >= period else values
    mid = sum(recent) / len(recent)
    variance = sum((x - mid) ** 2 for x in recent) / len(recent)
    std = math.sqrt(variance)
    width_pct = ((2 * mult * std) / mid * 100) if mid else 0
    return {"upper": mid + mult * std, "middle": mid, "lower": mid - mult * std, "width_pct": width_pct}


def atr(candles: List[Dict[str, Any]], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0

    trs = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i - 1]["close"])
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))

    return sum(trs[-period:]) / period


def volume_ratio(candles: List[Dict[str, Any]], period: int = 20) -> float:
    volumes = [float(c.get("volume", 0)) for c in candles]
    if len(volumes) < period + 1:
        return 1.0
    avg = sum(volumes[-period-1:-1]) / period
    return volumes[-1] / avg if avg else 1.0


# =========================
# ESTRATEGIA
# =========================

def analyze_market(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    if len(candles) < 60:
        return {"signal": "WAIT", "confidence": 0.0, "price": 0.0, "atr": 0.0, "reason": "No hay suficientes velas."}

    closes = [float(c["close"]) for c in candles]
    price = closes[-1]

    rsi_val = rsi(closes)
    macd_val = macd(closes)
    bb = bollinger(closes)
    atr_val = atr(candles)
    vol_ratio = volume_ratio(candles)

    ema21 = ema(closes[-60:], 21)
    ema50 = ema(closes[-100:], 50)
    ema100 = ema(closes[-160:], 100)

    checks = [
        (price > ema21 > ema50, 0.24, "EMA21 > EMA50 y precio encima"),
        (price > ema100, 0.18, "precio encima de EMA100"),
        (macd_val["macd"] > macd_val["signal"] and macd_val["hist"] > 0, 0.20, "MACD positivo"),
        (45 <= rsi_val <= 66, 0.16, "RSI saludable"),
        (price < bb["upper"], 0.10, "precio no está extremo"),
        (bb["width_pct"] >= 0.45, 0.07, "mercado no está tan lateral"),
        (vol_ratio >= 0.75, 0.05, "volumen aceptable"),
    ]

    score = 0.0
    reasons = []
    for ok, points, reason in checks:
        if ok:
            score += points
            reasons.append(reason)

    signal = "BUY" if score >= MIN_CONFIDENCE else "WAIT"

    return {
        "signal": signal,
        "confidence": score,
        "price": price,
        "rsi": rsi_val,
        "macd": macd_val,
        "bollinger": bb,
        "atr": atr_val,
        "ema21": ema21,
        "ema50": ema50,
        "ema100": ema100,
        "volume_ratio": vol_ratio,
        "reason": ", ".join(reasons) if reasons else "Sin confirmaciones suficientes.",
    }


def can_trade_now() -> bool:
    if not state.active or state.position_open:
        return False
    return (time.time() - state.last_trade_ts) >= MIN_MINUTES_BETWEEN_TRADES * 60


def reset_daily_balance_if_needed(balance: float):
    today = date.today().isoformat()
    if state.day != today:
        state.day = today
        state.starting_day_balance = balance
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
    stop_distance = atr_val * STOP_LOSS_ATR_MULTIPLIER

    btc_size = risk_amount / stop_distance
    usd_size = btc_size * price
    usd_size = min(usd_size, balance * MAX_POSITION_BALANCE_PCT)

    if usd_size < MIN_ORDER_USD:
        return 0.0

    return usd_size / price


def record_trade_pnl(exit_price: float):
    pnl = (exit_price - state.entry_price) * state.position_size_btc
    s = state.stats
    s.total_trades += 1
    if pnl >= 0:
        s.wins += 1
    else:
        s.losses += 1
    s.simulated_pnl_usd += pnl
    s.best_trade = max(s.best_trade, pnl)
    s.worst_trade = min(s.worst_trade, pnl)


def manage_open_position(price: float, atr_val: float) -> Optional[str]:
    state.highest_price = max(state.highest_price, price)

    initial_risk = state.entry_price - state.initial_stop_loss
    if initial_risk > 0 and price >= state.entry_price + (initial_risk * BREAK_EVEN_TRIGGER_R):
        state.stop_loss = max(state.stop_loss, state.entry_price)

    if atr_val > 0:
        trailing_stop = state.highest_price - (atr_val * TRAILING_STOP_ATR_MULTIPLIER)
        state.stop_loss = max(state.stop_loss, trailing_stop)

    if price <= state.stop_loss:
        return "STOP_LOSS"

    if price >= state.take_profit:
        return "TAKE_PROFIT"

    return None


async def trading_loop(app: Application):
    await send_telegram(
        app,
        f"🚀 BTC Bot Seguro Avanzado iniciado.\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"Producto: {PRODUCT_ID}\n"
        f"Riesgo: {MAX_RISK_PER_TRADE*100:.2f}%"
    )

    while True:
        try:
            candles = get_candles(limit=180)
            analysis = analyze_market(candles)

            price = analysis.get("price", 0.0)
            balance = get_usdc_balance()

            reset_daily_balance_if_needed(balance)

            state.last_signal = analysis["signal"]
            state.last_confidence = analysis["confidence"]
            state.last_reason = analysis.get("reason", "")

            if daily_loss_limit_reached(balance):
                state.active = False
                save_state()
                await send_telegram(app, "🛑 Bot pausado: límite de pérdida diaria alcanzado.")
                await asyncio.sleep(ANALYZE_EVERY_SECONDS)
                continue

            logger.info("Precio %.2f | Señal %s | Confianza %.2f | %s", price, analysis["signal"], analysis["confidence"], state.last_reason)

            if state.position_open:
                exit_reason = manage_open_position(price, analysis.get("atr", 0.0))

                if exit_reason:
                    place_market_order("SELL", base_size=state.position_size_btc)
                    record_trade_pnl(price)
                    
                    pnl = (price - state.entry_price) * state.position_size_btc

                    win_rate = (
                        (state.stats.wins / state.stats.total_trades) * 100
                        if state.stats.total_trades > 0 else 0
                    )

                    await send_telegram(
                        app,
                        f"{'🟢' if pnl >= 0 else '🔴'} Trade {'ganado' if pnl >= 0 else 'perdido'}\n"
                        f"Resultado: ${pnl:.2f}\n"
                        f"PnL acumulado: ${state.stats.simulated_pnl_usd:.2f}\n"
                        f"Win Rate: {win_rate:.2f}%\n"
                        f"Salida: {exit_reason}\n"
                        f"Precio salida: {price:.2f}\n"
                        f"Entrada: {state.entry_price:.2f}\n"
                        f"BTC: {state.position_size_btc:.8f}"
                    )

                    state.position_open = False
                    state.entry_price = 0.0
                    state.position_size_btc = 0.0
                    state.position_usd = 0.0
                    state.stop_loss = 0.0
                    state.initial_stop_loss = 0.0
                    state.take_profit = 0.0
                    state.highest_price = 0.0
                    state.last_trade_ts = time.time()
                    save_state()
                    
            elif can_trade_now() and analysis["signal"] == "BUY":
                btc_size = calculate_position_size(balance, price, analysis["atr"])
                usd_size = btc_size * price

                if usd_size >= MIN_ORDER_USD:
                    stop = price - (analysis["atr"] * STOP_LOSS_ATR_MULTIPLIER)
                    take = price + (analysis["atr"] * TAKE_PROFIT_ATR_MULTIPLIER)

                    place_market_order("BUY", quote_size=usd_size)

                    state.position_open = True
                    state.entry_price = price
                    state.position_size_btc = btc_size
                    state.position_usd = usd_size
                    state.stop_loss = stop
                    state.initial_stop_loss = stop
                    state.take_profit = take
                    state.highest_price = price
                    state.last_trade_ts = time.time()
                    save_state()
                    
                    await send_telegram(
                        app,
                        f"🟢 Compra {'simulada' if DRY_RUN else 'real'}\n"
                        f"Precio: {price:.2f}\n"
                        f"USD: {usd_size:.2f}\n"
                        f"BTC: {btc_size:.8f}\n"
                        f"Stop: {stop:.2f}\n"
                        f"Take Profit: {take:.2f}\n"
                        f"Confianza: {analysis['confidence']:.2f}\n"
                        f"Razón: {analysis['reason']}"
                    )

        except Exception as e:
            logger.exception("Error en loop principal")
            await send_telegram(app, f"⚠️ Error en bot:\n{str(e)[:900]}")

        await asyncio.sleep(ANALYZE_EVERY_SECONDS)


async def post_init(app: Application):
    asyncio.create_task(trading_loop(app))


def validate_config():
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Falta TELEGRAM_TOKEN.")
    if not CHAT_ID:
        raise RuntimeError("Falta CHAT_ID.")
    if not CB_API_KEY:
        raise RuntimeError("Falta CB_API_KEY.")
    if not CB_API_SECRET:
        raise RuntimeError("Falta CB_API_SECRET.")


def main():
    validate_config()
    load_state()
    get_client()

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("pause", pause_cmd))
    app.add_handler(CommandHandler("dryrun", dryrun_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("signal", signal_cmd))
    app.add_handler(CommandHandler("config", config_cmd))
    app.add_handler(CommandHandler("resume", start_cmd))

    logger.info("Iniciando BTC Bot Seguro Avanzado con RESTClient...")
    app.run_polling()


if __name__ == "__main__":
    main()
