#!/usr/bin/env python3
"""
BTC Trading Bot — Coinbase + Telegram
Token: 7879789602:AAFK172eeD0QmshegCq49Jgrr6mmy_1ZfTE
Chat ID: 1528945134
"""

import hmac, hashlib, time, json, asyncio, logging
from datetime import datetime
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ═══════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════
TELEGRAM_TOKEN  = "7879789602:AAFK172eeD0QmshegCq49Jgrr6mmy_1ZfTE"
CHAT_ID         = "1528945134"
CB_API_KEY      = "organizations/b9bdbe0e-53e7-48e0-920e-3c921d7721bb/apiKeys/e9d7f71c-42f0-4244-9e9e-6b391b361918"
CB_API_SECRET   = "TU_API_SECRET_AQUI"   # ← pega aquí tu clave secreta de Coinbase
MAX_RISK        = 0.10   # 10 % máximo por operación
MIN_CONFIDENCE  = 0.70   # 70 % mínimo para entrar
INTERVAL_MIN    = 5      # analizar cada 5 minutos
PRODUCT         = "BTC-USDC"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════
#  ESTADO GLOBAL
# ═══════════════════════════════════════════
bot_running   = False
position      = None   # {"side","entry","sl","tp","size","risk"}
trades        = []
bot_app       = None

# ═══════════════════════════════════════════
#  COINBASE API
# ═══════════════════════════════════════════
def cb_sign(method, path, body=""):
    ts  = str(int(time.time()))
    msg = ts + method.upper() + path + body
    sig = hmac.new(CB_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return {"CB-ACCESS-KEY": CB_API_KEY, "CB-ACCESS-SIGN": sig,
            "CB-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}

def cb_get(path):
    r = requests.get(f"https://api.coinbase.com{path}", headers=cb_sign("GET", path), timeout=10)
    r.raise_for_status()
    return r.json()

def cb_post(path, body):
    b = json.dumps(body)
    r = requests.post(f"https://api.coinbase.com{path}", headers=cb_sign("POST", path, b), data=b, timeout=10)
    r.raise_for_status()
    return r.json()

def get_account():
    d = cb_get("/api/v3/brokerage/accounts")
    accs = d.get("accounts", [])
    usd = next((a for a in accs if a["currency"] in ("USDC","USD")), None)
    btc = next((a for a in accs if a["currency"] == "BTC"), None)
    return {
        "usd": float(usd["available_balance"]["value"]) if usd else 0,
        "btc": float(btc["available_balance"]["value"]) if btc else 0,
    }

def get_candles(tf):
    gran = {"1H":3600,"4H":14400,"1D":86400}[tf]
    lim  = {"1H":120, "4H":90,   "1D":60}[tf]
    end  = int(time.time())
    start= end - gran * lim
    path = f"/api/v3/brokerage/products/{PRODUCT}/candles?start={start}&end={end}&granularity_second={gran}&limit={lim}"
    d = cb_get(path)
    candles = d.get("candles", [])
    return sorted([
        {"t":int(c["start"]),"o":float(c["open"]),"h":float(c["high"]),
         "l":float(c["low"]), "c":float(c["close"]),"v":float(c["volume"])}
        for c in candles
    ], key=lambda x: x["t"])

def place_order(side, size):
    body = {
        "client_order_id": f"bot_{int(time.time()*1000)}",
        "product_id": PRODUCT,
        "side": side,
        "order_configuration": {
            "market_market_ioc": (
                {"quote_size": f"{size:.2f}"} if side == "BUY"
                else {"base_size": f"{size:.8f}"}
            )
        }
    }
    return cb_post("/api/v3/brokerage/orders", body)

# ═══════════════════════════════════════════
#  INDICADORES TÉCNICOS
# ═══════════════════════════════════════════
def ema(prices, n):
    k = 2/(n+1)
    e = sum(prices[:n])/n
    result = [e]
    for p in prices[n:]:
        e = p*k + e*(1-k)
        result.append(e)
    return result

def rsi(prices, n=14):
    ch = [prices[i]-prices[i-1] for i in range(1,len(prices))]
    ag = sum(c for c in ch[:n] if c>0)/n
    al = sum(-c for c in ch[:n] if c<0)/n
    result = [100-100/(1+ag/(al or 1e-10))]
    for c in ch[n:]:
        ag = (ag*(n-1)+max(c,0))/n
        al = (al*(n-1)+max(-c,0))/n
        result.append(100-100/(1+ag/(al or 1e-10)))
    return result

def macd_hist(prices):
    e12 = ema(prices,12); e26 = ema(prices,26)
    off = len(e12)-len(e26)
    ml  = [e12[i+off]-e26[i] for i in range(len(e26))]
    sig = ema(ml,9)
    return [ml[i+(len(ml)-len(sig))]-sig[i] for i in range(len(sig))]

def bollinger(prices, n=20):
    result = []
    for i in range(n-1, len(prices)):
        sl   = prices[i-n+1:i+1]
        mean = sum(sl)/n
        std  = (sum((x-mean)**2 for x in sl)/n)**0.5
        result.append({"u":mean+2*std,"m":mean,"l":mean-2*std})
    return result

def atr(candles, n=14):
    trs = [max(c["h"]-c["l"], abs(c["h"]-candles[i]["c"]), abs(c["l"]-candles[i]["c"]))
           for i,c in enumerate(candles[1:], 0)]
    a = sum(trs[:n])/n
    result = [a]
    for t in trs[n:]:
        a = (a*(n-1)+t)/n
        result.append(a)
    return result

def analyze(candles):
    if len(candles) < 55:
        return {"signal":"WAIT","conf":0,"reasons":[]}
    cl  = [c["c"] for c in candles]
    e9  = ema(cl,9);  e21 = ema(cl,21);  e50 = ema(cl,50)
    rs  = rsi(cl)
    mh  = macd_hist(cl)
    bb  = bollinger(cl)
    at  = atr(candles)
    lc=cl[-1]; le9=e9[-1]; le21=e21[-1]; le50=e50[-1]
    lr=rs[-1]; lm=mh[-1]; pm=mh[-2]
    lb=bb[-1]; la=at[-1]

    bull=0; bear=0; reasons=[]

    if le9>le21>le50:   bull+=2; reasons.append("✅ EMA alcista 9>21>50")
    elif le9<le21<le50: bear+=2; reasons.append("🔴 EMA bajista 9<21<50")

    if 50<lr<70:   bull+=1.5; reasons.append(f"✅ RSI {lr:.1f} alcista")
    elif 30<lr<50: bear+=1.5; reasons.append(f"🔴 RSI {lr:.1f} bajista")
    elif lr>=70:   bear+=1;   reasons.append(f"⚠️ RSI sobrecomprado {lr:.1f}")
    elif lr<=30:   bull+=1;   reasons.append(f"⚠️ RSI sobrevendido {lr:.1f}")

    if lm>0 and pm<0:   bull+=2; reasons.append("✅ MACD cruce alcista")
    elif lm<0 and pm>0: bear+=2; reasons.append("🔴 MACD cruce bajista")
    elif lm>0: bull+=0.5
    else:      bear+=0.5

    if lb["l"]<lc<lb["m"]:   bear+=1;   reasons.append("🔴 Precio bajo media BB")
    elif lb["m"]<lc<lb["u"]: bull+=1;   reasons.append("✅ Precio sobre media BB")
    if lc<=lb["l"]:           bull+=1.5; reasons.append("✅ Rebote banda inferior")
    if lc>=lb["u"]:           bear+=1.5; reasons.append("🔴 Rechazo banda superior")

    mom = lc/cl[-6]-1
    if mom>0.01:   bull+=1; reasons.append(f"✅ Momentum +{mom*100:.2f}%")
    elif mom<-0.01:bear+=1; reasons.append(f"🔴 Momentum {mom*100:.2f}%")

    tot  = bull+bear
    bc   = bull/tot if tot else 0
    sc   = bear/tot if tot else 0
    signal="WAIT"; conf=0
    if bc>=MIN_CONFIDENCE:   signal="BUY";  conf=min(bc*100,99)
    elif sc>=MIN_CONFIDENCE: signal="SELL"; conf=min(sc*100,99)
    else: conf=max(bc,sc)*100

    return {"signal":signal,"conf":conf,"reasons":reasons,
            "price":lc,"rsi":lr,"macd":lm,"atr":la,
            "sl": lc-la*1.5 if signal=="BUY" else lc+la*1.5,
            "tp": lc+la*2.5 if signal=="BUY" else lc-la*2.5}

def pos_size(balance, price, sl):
    risk = balance * MAX_RISK
    rpu  = abs(price - sl)
    if not rpu: return 0
    return min(risk/rpu, balance*0.5/price)

# ═══════════════════════════════════════════
#  TELEGRAM HELPERS
# ═══════════════════════════════════════════
async def tg_send(text):
    if bot_app:
        await bot_app.bot.send_message(chat_id=CHAT_ID, text=text, parse_mode="HTML")

# ═══════════════════════════════════════════
#  CICLO PRINCIPAL DEL BOT
# ═══════════════════════════════════════════
async def bot_cycle():
    global position, trades
    log.info("🔄 Analizando BTC...")

    try:
        acc = get_account()
    except Exception as e:
        await tg_send(f"⚠️ Error cuenta: {e}")
        return

    sigs = {}
    for tf in ["1H","4H","1D"]:
        try:
            c = get_candles(tf)
            sigs[tf] = analyze(c)
        except Exception as e:
            log.warning(f"Error candles {tf}: {e}")

    buy_v  = sum(1 for s in sigs.values() if s["signal"]=="BUY")
    sell_v = sum(1 for s in sigs.values() if s["signal"]=="SELL")
    avg_c  = sum(s["conf"] for s in sigs.values())/len(sigs) if sigs else 0
    consensus = "BUY" if buy_v>=2 else "SELL" if sell_v>=2 else "WAIT"

    log.info(f"Consenso: {consensus} | Confianza: {avg_c:.1f}%")

    ps = sigs.get("1H")
    if not ps: return

    # ── SALIDA ──────────────────────────────
    if position:
        price = ps["price"]
        pnl = ((price-position["entry"])/position["entry"]
               if position["side"]=="BUY"
               else (position["entry"]-price)/position["entry"])
        exit_now = (
            (position["side"]=="BUY"  and (price>=position["tp"] or price<=position["sl"])) or
            (position["side"]=="SELL" and (price<=position["tp"] or price>=position["sl"])) or
            (consensus=="SELL" and position["side"]=="BUY") or
            (consensus=="BUY"  and position["side"]=="SELL")
        )
        if exit_now:
            try:
                if position["side"]=="BUY" and acc["btc"]>0.0001:
                    place_order("SELL", acc["btc"])
                pnl_pct = pnl*100
                result  = "WIN ✅" if pnl>=0 else "LOSS ❌"
                trades.append({"side":position["side"],"pnl":pnl_pct,"win":pnl>=0,
                                "time":datetime.now().strftime("%H:%M %d/%m")})
                wins = sum(1 for t in trades if t["win"])
                wr   = wins/len(trades)*100
                msg = (f"{'✅ WIN' if pnl>=0 else '❌ LOSS'} — Posición cerrada\n\n"
                       f"📊 Par: BTC/USDC\n"
                       f"📍 Entrada: ${position['entry']:,.0f}\n"
                       f"📍 Salida: ${price:,.0f}\n"
                       f"💰 P&L: {'+' if pnl>=0 else ''}{pnl_pct:.2f}%\n"
                       f"📈 Efectividad: {wr:.1f}% ({len(trades)} trades)\n\n"
                       f"💵 Balance USDC: ${acc['usd']:.2f}")
                await tg_send(msg)
                position = None
            except Exception as e:
                await tg_send(f"❌ Error cerrando posición: {e}")
        else:
            pnl_now = pnl*100
            log.info(f"Posición {position['side']} activa | Entrada ${position['entry']:.0f} | P&L: {pnl_now:+.2f}%")
        return

    # ── ENTRADA ─────────────────────────────
    if consensus != "WAIT" and avg_c >= MIN_CONFIDENCE*100:
        price = ps["price"]
        sl    = ps["sl"]
        tp    = ps["tp"]
        sz    = pos_size(acc["usd"], price, sl)
        usd_amt = sz * price

        if usd_amt < 1:
            log.info("Balance insuficiente")
            return

        try:
            if consensus == "BUY":
                place_order("BUY", min(usd_amt, acc["usd"]*0.95))

            risk_pct = abs(price-sl)/price*100
            position = {"side":consensus,"entry":price,"sl":sl,"tp":tp,
                        "size":sz,"risk":risk_pct}

            reasons_txt = "\n".join(ps["reasons"][:4])
            msg = (f"🚀 ENTRADA {consensus} — BTC/USDC\n\n"
                   f"💵 Precio: ${price:,.0f}\n"
                   f"🛑 Stop Loss: ${sl:,.0f}\n"
                   f"🎯 Take Profit: ${tp:,.0f}\n"
                   f"⚠️ Riesgo: {risk_pct:.2f}%\n"
                   f"📊 Confianza: {avg_c:.1f}%\n\n"
                   f"📋 Señales:\n{reasons_txt}\n\n"
                   f"Envía /estado para ver tu posición")
            await tg_send(msg)
            log.info(f"ENTRADA {consensus} ${price:.0f}")
        except Exception as e:
            await tg_send(f"❌ Error abriendo posición: {e}")
    else:
        log.info(f"Sin señal válida. Consenso:{consensus} Conf:{avg_c:.1f}%")

# ═══════════════════════════════════════════
#  COMANDOS TELEGRAM
# ═══════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "₿ <b>BTC Trading Bot</b>\n\n"
        "Comandos disponibles:\n"
        "▶️ /iniciar — Activar el bot\n"
        "⏹ /parar — Detener el bot\n"
        "📊 /estado — Ver estado actual\n"
        "📈 /trades — Historial de operaciones\n"
        "💰 /balance — Ver balance\n"
        "ℹ️ /ayuda — Ver comandos",
        parse_mode="HTML"
    )

async def cmd_iniciar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_running
    if bot_running:
        await update.message.reply_text("⚠️ El bot ya está activo.")
        return
    bot_running = True
    await update.message.reply_text(
        "✅ <b>Bot iniciado</b>\n\n"
        "🤖 Analizando BTC cada 5 minutos\n"
        "📊 Temporalidades: 1H · 4H · 1D\n"
        "⚠️ Riesgo máximo: 10%\n"
        "🎯 Efectividad mínima: 70%\n\n"
        "Envía /parar cuando quieras detenerlo.",
        parse_mode="HTML"
    )
    asyncio.create_task(run_loop(ctx))

async def cmd_parar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global bot_running
    bot_running = False
    await update.message.reply_text(
        "⛔ <b>Bot detenido</b>\n\n"
        "El bot dejará de analizar.\n"
        "Tu posición actual (si hay) <b>NO se cierra automáticamente</b>.\n"
        "Envía /estado para verificar.",
        parse_mode="HTML"
    )

async def cmd_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    estado = "🟢 ACTIVO" if bot_running else "🔴 DETENIDO"
    try:
        acc = get_account()
        bal = f"${acc['usd']:.2f} USDC | {acc['btc']:.6f} BTC"
    except:
        bal = "Error obteniendo balance"

    if position:
        try:
            c = get_candles("1H")
            cur = c[-1]["c"] if c else position["entry"]
        except:
            cur = position["entry"]
        pnl = ((cur-position["entry"])/position["entry"]
               if position["side"]=="BUY"
               else (position["entry"]-cur)/position["entry"])*100
        pos_txt = (f"\n\n📍 <b>Posición activa: {position['side']}</b>\n"
                   f"Entrada: ${position['entry']:,.0f}\n"
                   f"Actual:  ${cur:,.0f}\n"
                   f"Stop Loss: ${position['sl']:,.0f}\n"
                   f"Take Profit: ${position['tp']:,.0f}\n"
                   f"P&L actual: {'+' if pnl>=0 else ''}{pnl:.2f}%")
    else:
        pos_txt = "\n\n💤 Sin posición abierta"

    wins = sum(1 for t in trades if t["win"])
    wr   = (wins/len(trades)*100) if trades else 0
    await update.message.reply_text(
        f"📊 <b>Estado del Bot</b>\n\n"
        f"Estado: {estado}\n"
        f"💰 Balance: {bal}\n"
        f"📈 Efectividad: {wr:.1f}% ({len(trades)} trades)"
        f"{pos_txt}",
        parse_mode="HTML"
    )

async def cmd_trades(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not trades:
        await update.message.reply_text("Sin trades aún.")
        return
    wins  = sum(1 for t in trades if t["win"])
    total_pnl = sum(t["pnl"] for t in trades)
    lines = [f"{'✅' if t['win'] else '❌'} {t['side']} {t['pnl']:+.2f}% — {t['time']}"
             for t in trades[-10:]]
    await update.message.reply_text(
        f"📈 <b>Últimos trades</b>\n\n"
        + "\n".join(lines) +
        f"\n\n✅ Wins: {wins} | ❌ Losses: {len(trades)-wins}\n"
        f"📊 P&L total: {total_pnl:+.2f}%\n"
        f"🎯 Efectividad: {wins/len(trades)*100:.1f}%",
        parse_mode="HTML"
    )

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        acc = get_account()
        await update.message.reply_text(
            f"💰 <b>Balance</b>\n\n"
            f"USDC: ${acc['usd']:.2f}\n"
            f"BTC:  {acc['btc']:.8f}",
            parse_mode="HTML"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ <b>Comandos</b>\n\n"
        "/iniciar — Activar bot\n"
        "/parar — Detener bot\n"
        "/estado — Estado + posición\n"
        "/trades — Historial operaciones\n"
        "/balance — Ver balance Coinbase\n\n"
        "⚙️ <b>Configuración actual</b>\n"
        f"Par: BTC/USDC\n"
        f"Riesgo máx: {MAX_RISK*100:.0f}%\n"
        f"Confianza mínima: {MIN_CONFIDENCE*100:.0f}%\n"
        f"Intervalo: cada {INTERVAL_MIN} min\n"
        f"Temporalidades: 1H · 4H · 1D",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════
#  LOOP AUTOMÁTICO
# ═══════════════════════════════════════════
async def run_loop(ctx):
    global bot_running
    while bot_running:
        try:
            await bot_cycle()
        except Exception as e:
            log.error(f"Error en ciclo: {e}")
            await tg_send(f"⚠️ Error en ciclo: {e}")
        await asyncio.sleep(INTERVAL_MIN * 60)

# ═══════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════
def main():
    global bot_app
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_app = app
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("iniciar", cmd_iniciar))
    app.add_handler(CommandHandler("parar",   cmd_parar))
    app.add_handler(CommandHandler("estado",  cmd_estado))
    app.add_handler(CommandHandler("trades",  cmd_trades))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("ayuda",   cmd_ayuda))
    log.info("🤖 Bot iniciado — esperando comandos en Telegram...")
    app.run_polling()

if __name__ == "__main__":
    main()

