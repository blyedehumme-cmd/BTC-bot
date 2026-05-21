from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


REPORT_PATH = Path("backtest_report.txt")


def money(value: float) -> str:
    return f"${value:,.2f}"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def calculate_summary(trades: pd.DataFrame, equity_curve: pd.DataFrame, initial_capital: float, final_capital: float) -> dict[str, Any]:
    if trades.empty:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "long_win_rate": 0.0,
            "short_win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "long_count": 0,
            "short_count": 0,
            "avg_duration": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
        }

    wins = trades[trades["pnl_net"] > 0]
    losses = trades[trades["pnl_net"] <= 0]
    gross_profit = wins["pnl_gross"].sum()
    gross_loss = abs(losses["pnl_gross"].sum())
    long_trades = trades[trades["side"] == "LONG"]
    short_trades = trades[trades["side"] == "SHORT"]
    drawdown = equity_curve["drawdown_pct"].min() if not equity_curve.empty else 0.0

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) * 100,
        "long_win_rate": (long_trades["pnl_net"] > 0).mean() * 100 if len(long_trades) else 0.0,
        "short_win_rate": (short_trades["pnl_net"] > 0).mean() * 100 if len(short_trades) else 0.0,
        "profit_factor": gross_profit / gross_loss if gross_loss else float("inf"),
        "max_drawdown": drawdown,
        "long_count": len(long_trades),
        "short_count": len(short_trades),
        "avg_duration": trades["duration_hours"].mean(),
        "best_trade": trades["pnl_net"].max(),
        "worst_trade": trades["pnl_net"].min(),
        "pnl_usd": final_capital - initial_capital,
        "pnl_pct": (final_capital - initial_capital) / initial_capital * 100,
    }


def write_report(
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    initial_capital: float,
    final_capital: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    summary = calculate_summary(trades, equity_curve, initial_capital, final_capital)
    lines = [
        "REPORTE BACKTEST BTC/USD",
        "=" * 72,
        f"Capital inicial: {money(initial_capital)}",
        f"Capital final: {money(final_capital)}",
        f"PnL total: {money(summary.get('pnl_usd', 0.0))} ({pct(summary.get('pnl_pct', 0.0))})",
        f"Win rate general: {pct(summary['win_rate'])}",
        f"Win rate LONG: {pct(summary['long_win_rate'])}",
        f"Win rate SHORT: {pct(summary['short_win_rate'])}",
        f"Profit factor: {summary['profit_factor']:.2f}" if summary["profit_factor"] != float("inf") else "Profit factor: inf",
        f"Max drawdown: {pct(summary['max_drawdown'])}",
        f"Total trades: {summary['total_trades']}",
        f"Ganados: {summary['wins']}",
        f"Perdidos: {summary['losses']}",
        f"Trades LONG: {summary['long_count']}",
        f"Trades SHORT: {summary['short_count']}",
        f"Duracion promedio: {summary['avg_duration']:.2f} horas",
        f"Mejor trade: {money(summary['best_trade'])}",
        f"Peor trade: {money(summary['worst_trade'])}",
    ]
    if metadata:
        lines.extend(["", "CONFIGURACION", "-" * 72])
        lines.extend(f"{key}: {value}" for key, value in metadata.items())
    lines.extend(["", "TRADES", "-" * 72])

    if trades.empty:
        lines.append("No se ejecutaron trades.")
    else:
        table = trades[[
            "entry_time",
            "side",
            "entry_price",
            "exit_price",
            "pnl_net",
            "fee_total",
            "exit_reason",
        ]].copy()
        lines.append(table.to_string(index=False))

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Reporte guardado en {REPORT_PATH}")


def plot_equity(equity_curve: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 6))
    plt.plot(equity_curve["time"], equity_curve["equity"], color="#00a3ff")
    plt.title("Evolucion del capital")
    plt.xlabel("Fecha")
    plt.ylabel("Capital USD")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig("equity_curve.png", dpi=150)
    plt.close()


def plot_price_trades(candles_1h: pd.DataFrame, trades: pd.DataFrame) -> None:
    plt.figure(figsize=(14, 7))
    plt.plot(candles_1h["datetime"], candles_1h["close"], color="#d1d5db", linewidth=1, label="BTC close")
    if not trades.empty:
        longs = trades[trades["side"] == "LONG"]
        shorts = trades[trades["side"] == "SHORT"]
        plt.scatter(longs["entry_time"], longs["entry_price"], marker="^", color="green", s=65, label="Entrada LONG")
        plt.scatter(shorts["entry_time"], shorts["entry_price"], marker="v", color="red", s=65, label="Entrada SHORT")
        plt.scatter(trades["exit_time"], trades["exit_price"], marker="x", color="white", s=65, label="Cierre")
    plt.title("Precio BTC con entradas y salidas")
    plt.xlabel("Fecha")
    plt.ylabel("Precio USD")
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig("price_trades.png", dpi=150)
    plt.close()


def plot_pnl_distribution(trades: pd.DataFrame) -> None:
    plt.figure(figsize=(10, 6))
    if not trades.empty:
        plt.hist(trades[trades["side"] == "LONG"]["pnl_net"], bins=30, alpha=0.65, label="LONG", color="tab:blue")
        plt.hist(trades[trades["side"] == "SHORT"]["pnl_net"], bins=30, alpha=0.65, label="SHORT", color="tab:orange")
        plt.legend()
    plt.title("Distribucion PnL por trade")
    plt.xlabel("PnL USD")
    plt.ylabel("Frecuencia")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig("pnl_distribution.png", dpi=150)
    plt.close()


def plot_drawdown(equity_curve: pd.DataFrame) -> None:
    plt.figure(figsize=(12, 6))
    plt.plot(equity_curve["time"], equity_curve["drawdown_pct"], color="tab:red")
    plt.title("Drawdown")
    plt.xlabel("Fecha")
    plt.ylabel("Drawdown %")
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    plt.savefig("drawdown.png", dpi=150)
    plt.close()


def generate_outputs(
    trades: pd.DataFrame,
    equity_curve: pd.DataFrame,
    candles_1h: pd.DataFrame,
    initial_capital: float,
    final_capital: float,
    metadata: dict[str, Any] | None = None,
) -> None:
    write_report(trades, equity_curve, initial_capital, final_capital, metadata=metadata)
    if not equity_curve.empty:
        plot_equity(equity_curve)
        plot_drawdown(equity_curve)
    plot_price_trades(candles_1h, trades)
    plot_pnl_distribution(trades)
    print("Graficas guardadas: equity_curve.png, price_trades.png, pnl_distribution.png, drawdown.png")
