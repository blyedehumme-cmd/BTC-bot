#!/usr/bin/env python3
"""
BTC Trading Bot Seguro - Coinbase Advanced Trade + Telegram

IMPORTANTE:
- Este bot inicia en DRY_RUN=True por seguridad. No compra ni vende real hasta que lo cambies.
- Usa variables de entorno en Render. NO pongas tus keys dentro del código.
- Trading siempre tiene riesgo. Prueba primero con poco dinero.
"""

import os
import time
import hmac
import json
import math
import base64
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, List

import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes


# =========================
# CONFIGURACIÓN SEGURA
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

CB_API_KEY = os.getenv("CB_API_KEY", "")
CB_API_SECRET = os.getenv("CB_API_SECRET", "")

PRODUCT_ID = os.getenv("PRODUCT_ID", "BTC-USDC")

# Seguridad: por defecto NO opera real
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# Riesgo recomendado para automático: 1% a 2%
MAX_RISK_PER_TRADE = float(os.getenv("MAX_RISK_PER_TRADE", "0.01"))

# No perder más de 3% del balance en un día
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.03"))

# Evita sobre-operar
MIN_MINUTES_BETWEEN_TRADES = int(os.getenv("MIN_MINUTES_BETWEEN_TRADES", "60"))

# Señal mínima para entrar
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.72"))

# Intervalo de análisis
ANALYZE_EVERY_SECONDS = int(os.getenv("ANALYZE_EVERY_SECONDS", "300"))

# Stop y take profit
STOP_LOSS_ATR_MULTIPLIER = float(os.getenv("STOP_LOSS_ATR_MULTIPLIER", "1.8"))
TAKE_PROFIT_ATR_MULTIPLIER = float(os.getenv("TAKE_PROFIT_ATR_MULTIPLIER", "2.8"))

# Límite mínimo de orden
MIN_ORDER_USD = float(os.getenv("MIN_ORDER_USD", "10"))

COINBASE_API_URL = "https://api.coinbase.com"


# =========================
# LOGGING
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("btc-bot-seguro")


# =========================
# ESTADO DEL BOT
# =========================

@dataclass
class BotState:
    active: bool = True
    position_open: bool = False
    entry_price: float = 0.0
    position_size_btc: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    last_trade_ts: float = 0.0
    day: str = ""
    starting_day_balance: float = 0.0
    realized_pnl_today: float = 0.0


state = BotState()


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
    await update.message.reply_text(
        "✅ BTC Bot Seguro activo.\n\n"
        "Comandos:\n"
        "/status - Ver estado\n"
        "/pause - Pausar bot\n"
        "/resume - Activar bot\n"
        "/dryrun - Ver si opera real o simulación"
    )


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        f"📊 Estado del bot\n"
        f"Activo: {state.active}\n"
        f"DRY_RUN: {DRY_RUN}\n"
        f"Producto: {PRODUCT_ID}\n"
        f"Posición abierta: {state.position_open}\n"
        f"Entrada: {state.entry_price}\n"
        f"BTC: {state.position_size_btc}\n"
        f"Stop Loss: {state.stop_loss}\n"
        f"Take Profit: {state.take_profit}\n"
        f"Riesgo por trade: {MAX_RISK_PER_TRADE*100:.2f}%\n"
        f"Límite pérdida diaria: {MAX_DAILY_LOSS*100:.2f}%"
    )
    await update.message.reply_text(msg)


async def pause_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.active = False
    await update.message.reply_text("⏸ Bot pausado. No abrirá nuevas operaciones.")


async def resume_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state.active = True
    await update.message.reply_text("▶️ Bot activado.")


async def dryrun_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if DRY_RUN:
        await update.message.reply_text("🧪 DRY_RUN está activado. El bot NO compra ni vende real.")
    else:
        await update.message.reply_text("⚠️ DRY_RUN está apagado. El bot puede operar REAL.")


# =========================
# COINBASE ADVANCED TRADE
# =========================

def _coinbase_headers(method: str, path: str, body: str = "") -> Dict[str, str]:
    """
    Firma básica para Coinbase Advanced Trade.
    Si tu API key nueva requiere formato JWT, revisa el tipo de key creada en Coinbase.
    """
    timestamp = str(int(time.time()))
    message = timestamp + method.upper() + path + body

    try:
        secret = base64.b64decode(CB_API_SECRET)
    except Exception:
        secret = CB_API_SECRET.encode()

    signature = hmac.new(secret, message.encode(), hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode()

    return {
        "CB-ACCESS-KEY": CB_API_KEY,
        "CB-ACCESS-SIGN": signature_b64,
        "CB-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json",
    }


def coinbase_request(method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    body = json.dumps(payload) if payload else ""
    headers = _coinbase_headers(method, path, body)
    url = COINBASE_API_URL + path

    response = requests.request(method, url, headers=headers, data=body, timeout=20)

    if response.status_code >= 400:
        raise RuntimeError(f"Coinbase error {response.status_code}: {response.text}")

    return response.json()


def get_candles(granularity: str = "FIVE_MINUTE", limit: int = 120) -> List[Dict[str, Any]]:
    path = f"/api/v3/brokerage/products/{PRODUCT_ID}/candles?granularity={granularity}&limit={limit}"
    data = coinbase_request("GET", path)
    candles = data.get("candles", [])
    return list(reversed(candles))


def get_price() -> float:
    path = f"/api/v3/brokerage/products/{PRODUCT_ID}"
    data = coinbase_request("GET", path)
    return float(data["price"])


def get_usdc_balance() -> float:
    path = "/api/v3/brokerage/accounts"
    data = coinbase_request("GET", path)

    for account in data.get("accounts", []):
        currency = account.get("currency")
        if currency == "USDC":
            return float(account.get("available_balance", {}).get("value", 0))

    return 0.0


def place_market_order(side: str, quote_size: Optional[float] = None, base_size: Optional[float] = None):
    client_order_id = f"btc-bot-{int(time.time())}"

    if side.upper() == "BUY":
        order_config = {
            "market_market_ioc": {
                "quote_size": str(round(quote_size, 2))
            }
        }
    else:
        order_config = {
            "market_market_ioc": {
                "base_size": str(round(base_size, 8))
            }
        }

    payload = {
        "client_order_id": client_order_id,
        "product_id": PRODUCT_ID,
        "side": side.upper(),
        "order_configuration": order_config
    }

    if DRY_RUN:
        logger.info("[DRY_RUN] Orden simulada: %s", payload)
        return {"dry_run": True, "payload": payload}

    return coinbase_request("POST", "/api/v3/brokerage/orders", payload)


# =========================
# INDICADORES
# =========================

def sma(values: List[float], period: int) -> float:
    if len(values) < period:
        return sum(values) / len(values)
    return sum(values[-period:]) / period


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

    gains = []
    losses = []

    for i in range(-period, 0):
        change = values[i] - values[i - 1]
        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def macd(values: List[float]) -> Dict[str, float]:
    ema12 = ema(values, 12)
    ema26 = ema(values, 26)
    macd_line = ema12 - ema26

    macd_values = []
    for i in range(35, len(values) + 1):
        sub = values[:i]
        macd_values.append(ema(sub, 12) - ema(sub, 26))

    signal = ema(macd_values[-9:], 9) if len(macd_values) >= 9 else macd_line
    return {"macd": macd_line, "signal": signal, "hist": macd_line - signal}


def bollinger(values: List[float], period: int = 20, mult: float = 2.0) -> Dict[str, float]:
    recent = values[-period:]
    mid = sum(recent) / len(recent)
    variance = sum((x - mid) ** 2 for x in recent) / len(recent)
    std = math.sqrt(variance)
    return {"upper": mid + mult * std, "middle": mid, "lower": mid - mult * std}


def atr(candles: List[Dict[str, Any]], period: int = 14) -> float:
    if len(candles) < period + 1:
        return 0.0

    trs = []
    for i in range(1, len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        prev_close = float(candles[i - 1]["close"])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    return sum(trs[-period:]) / period


# =========================
# ESTRATEGIA
# =========================

def analyze_market(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    closes = [float(c["close"]) for c in candles]
    price = closes[-1]

    rsi_val = rsi(closes)
    macd_val = macd(closes)
    bb = bollinger(closes)
    atr_val = atr(candles)

    ema50 = ema(closes[-80:], 50)
    ema200 = ema(closes, 200) if len(closes) >= 200 else sma(closes, min(len(closes), 100))

    bullish_trend = price > ema50 and ema50 >= ema200
    not_overbought = rsi_val < 68
    recovering = rsi_val > 42
    macd_positive = macd_val["macd"] > macd_val["signal"]
    price_not_too_high = price < bb["upper"]

    score = 0
    reasons = []

    if bullish_trend:
        score += 0.30
        reasons.append("tendencia alcista")
    if recovering:
        score += 0.18
        reasons.append("RSI saludable")
    if not_overbought:
        score += 0.15
        reasons.append("no está sobrecomprado")
    if macd_positive:
        score += 0.22
        reasons.append("MACD positivo")
    if price_not_too_high:
        score += 0.15
        reasons.append("precio no está extremo")

    signal = "BUY" if score >= MIN_CONFIDENCE else "WAIT"

    return {
        "signal": signal,
        "confidence": score,
        "price": price,
        "rsi": rsi_val,
        "macd": macd_val,
        "bollinger": bb,
        "atr": atr_val,
        "ema50": ema50,
        "ema200": ema200,
        "reasons": reasons,
    }


def can_trade_now() -> bool:
    if not state.active:
        return False

    if state.position_open:
        return False

    elapsed = time.time() - state.last_trade_ts
    return elapsed >= MIN_MINUTES_BETWEEN_TRADES * 60


def reset_daily_balance_if_needed(balance: float):
    today = date.today().isoformat()

    if state.day != today:
        state.day = today
        state.starting_day_balance = balance
        state.realized_pnl_today = 0.0
        logger.info("Nuevo día. Balance inicial: %.2f", balance)


def daily_loss_limit_reached(balance: float) -> bool:
    if state.starting_day_balance <= 0:
        return False

    drawdown = (state.starting_day_balance - balance) / state.starting_day_balance
    return drawdown >= MAX_DAILY_LOSS


def calculate_position_size(balance: float, price: float, atr_val: float) -> float:
    if atr_val <= 0:
        return 0.0

    risk_amount = balance * MAX_RISK_PER_TRADE
    stop_distance = atr_val * STOP_LOSS_ATR_MULTIPLIER

    btc_size = risk_amount / stop_distance
    usd_size = btc_size * price

    # Nunca usar más de 25% del balance en una sola compra
    max_usd_position = balance * 0.25
    usd_size = min(usd_size, max_usd_position)

    if usd_size < MIN_ORDER_USD:
        return 0.0

    return usd_size / price


async def trading_loop(app: Application):
    await send_telegram(app, f"🚀 BTC Bot Seguro iniciado.\nDRY_RUN: {DRY_RUN}\nProducto: {PRODUCT_ID}")

    while True:
        try:
            candles = get_candles(limit=120)
            analysis = analyze_market(candles)
            price = analysis["price"]
            balance = get_usdc_balance() if not DRY_RUN else 500.0

            reset_daily_balance_if_needed(balance)

            if daily_loss_limit_reached(balance):
                state.active = False
                await send_telegram(app, "🛑 Bot pausado: límite de pérdida diaria alcanzado.")
                await asyncio_sleep(ANALYZE_EVERY_SECONDS)
                continue

            logger.info(
                "Precio %.2f | Señal %s | Confianza %.2f | RSI %.2f",
                price,
                analysis["signal"],
                analysis["confidence"],
                analysis["rsi"],
            )

            # Manejo de posición abierta
            if state.position_open:
                if price <= state.stop_loss:
                    await send_telegram(app, f"🛑 Stop Loss ejecutado/simulado en {price:.2f}")
                    place_market_order("SELL", base_size=state.position_size_btc)
                    state.position_open = False
                    state.last_trade_ts = time.time()

                elif price >= state.take_profit:
                    await send_telegram(app, f"✅ Take Profit ejecutado/simulado en {price:.2f}")
                    place_market_order("SELL", base_size=state.position_size_btc)
                    state.position_open = False
                    state.last_trade_ts = time.time()

            # Nueva entrada
            elif can_trade_now() and analysis["signal"] == "BUY":
                btc_size = calculate_position_size(balance, price, analysis["atr"])
                usd_size = btc_size * price

                if usd_size >= MIN_ORDER_USD:
                    state.entry_price = price
                    state.position_size_btc = btc_size
                    state.stop_loss = price - (analysis["atr"] * STOP_LOSS_ATR_MULTIPLIER)
                    state.take_profit = price + (analysis["atr"] * TAKE_PROFIT_ATR_MULTIPLIER)
                    state.position_open = True
                    state.last_trade_ts = time.time()

                    place_market_order("BUY", quote_size=usd_size)

                    await send_telegram(
                        app,
                        f"🟢 Compra {'simulada' if DRY_RUN else 'real'}\n"
                        f"Precio: {price:.2f}\n"
                        f"USD: {usd_size:.2f}\n"
                        f"BTC: {btc_size:.8f}\n"
                        f"Stop: {state.stop_loss:.2f}\n"
                        f"Take Profit: {state.take_profit:.2f}\n"
                        f"Confianza: {analysis['confidence']:.2f}\n"
                        f"Razones: {', '.join(analysis['reasons'])}"
                    )

        except Exception as e:
            logger.exception("Error en loop principal")
            await send_telegram(app, f"⚠️ Error en bot:\n{str(e)[:900]}")

        await asyncio_sleep(ANALYZE_EVERY_SECONDS)


async def asyncio_sleep(seconds: int):
    import asyncio
    await asyncio.sleep(seconds)


async def post_init(app: Application):
    import asyncio
    asyncio.create_task(trading_loop(app))


def validate_config():
    if not TELEGRAM_TOKEN:
        logger.warning("TELEGRAM_TOKEN no configurado.")
    if not CHAT_ID:
        logger.warning("CHAT_ID no configurado.")
    if not DRY_RUN and (not CB_API_KEY or not CB_API_SECRET):
        raise RuntimeError("Para operar real necesitas CB_API_KEY y CB_API_SECRET en Render.")


def main():
    validate_config()

    if not TELEGRAM_TOKEN:
        logger.warning("Sin Telegram token. El bot correrá sin comandos de Telegram.")
        # Loop sin Telegram no implementado para mantenerlo simple.
        # Configura TELEGRAM_TOKEN y CHAT_ID en Render.
        return

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("pause", pause_cmd))
    app.add_handler(CommandHandler("resume", resume_cmd))
    app.add_handler(CommandHandler("dryrun", dryrun_cmd))

    logger.info("Iniciando Telegram polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
