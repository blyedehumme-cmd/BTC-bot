from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .regimes import regime_distribution, transition_matrix


WARNING = (
    "ADVERTENCIA: Los resultados del HMM son analisis historico/in-sample. "
    "No garantizan resultados futuros y no deben usarse solos para operar dinero real. "
    "El HMM debe ser filtro de contexto, no senal principal."
)


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        if value == float("inf"):
            return "inf"
        return f"{value:.2f}"
    return str(value)


def write_text_report(path: Path, results: dict[str, dict[str, Any]]) -> None:
    lines = ["LESLY HMM REGIME ANALYSIS", WARNING, ""]
    for name, result in results.items():
        lines.append(f"=== {name.upper()} ===")
        fit = result["fit"]
        lines.append(f"Estados elegidos: {fit.n_states}")
        lines.append(f"BIC: {fit.bic:.2f}")
        lines.append(f"Log likelihood: {fit.score:.2f}")
        lines.append("")
        lines.append("Distribucion de tiempo por regimen:")
        lines.append(result["distribution"].to_string(index=False))
        lines.append("")
        lines.append("Metricas por regimen:")
        metrics = result["metrics"]
        lines.append(metrics.to_string(index=False) if not metrics.empty else "Sin trades clasificados.")
        lines.append("")
        if not metrics.empty:
            best = metrics.sort_values("net_profit", ascending=False).head(1)
            worst = metrics.sort_values("net_profit", ascending=True).head(1)
            lines.append("Mejor regimen:")
            lines.append(best.to_string(index=False))
            lines.append("Peor regimen:")
            lines.append(worst.to_string(index=False))
        lines.append("")
        lines.append("Matriz de transicion:")
        lines.append(result["transition"].to_string())
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def plot_regime_timeline(regimes: pd.DataFrame, output: Path, title: str) -> None:
    plt.figure(figsize=(14, 5))
    plt.scatter(regimes["datetime"], regimes["close"], c=regimes["regime"], cmap="viridis", s=5)
    plt.title(title)
    plt.xlabel("Fecha")
    plt.ylabel("Precio")
    plt.colorbar(label="Regimen HMM")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def plot_regime_distribution(distribution: pd.DataFrame, output: Path, title: str) -> None:
    plt.figure(figsize=(8, 4))
    plt.bar(distribution["regime"].astype(str), distribution["time_pct"])
    plt.title(title)
    plt.xlabel("Regimen")
    plt.ylabel("% tiempo")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def plot_transition_matrix(matrix: pd.DataFrame, output: Path, title: str) -> None:
    plt.figure(figsize=(6, 5))
    plt.imshow(matrix.to_numpy(), cmap="Blues")
    plt.title(title)
    plt.xlabel("Regimen destino")
    plt.ylabel("Regimen origen")
    plt.xticks(range(len(matrix.columns)), matrix.columns)
    plt.yticks(range(len(matrix.index)), matrix.index)
    plt.colorbar(label="Probabilidad")
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def plot_equity_by_regime(trades: pd.DataFrame, output: Path, title: str, initial_capital: float) -> None:
    plt.figure(figsize=(12, 6))
    if trades.empty:
        plt.title(title)
        plt.savefig(output)
        plt.close()
        return
    ordered = trades.sort_values("exit_time").copy()
    ordered["global_equity"] = initial_capital + ordered["pnl_net"].cumsum()
    plt.plot(ordered["exit_time"], ordered["global_equity"], label="Global", linewidth=2)
    for regime, group in ordered.groupby("regime"):
        local = group.sort_values("exit_time").copy()
        local["equity"] = initial_capital + local["pnl_net"].cumsum()
        plt.plot(local["exit_time"], local["equity"], label=f"Regimen {regime}", alpha=0.75)
    plt.title(title)
    plt.xlabel("Fecha")
    plt.ylabel("Equity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(output)
    plt.close()


def plot_swing_vs_day(results: dict[str, dict[str, Any]], output: Path) -> None:
    labels = []
    profits = []
    win_rates = []
    for name, result in results.items():
        trades = result["classified_trades"]
        labels.append(name)
        if trades.empty:
            profits.append(0.0)
            win_rates.append(0.0)
        else:
            profits.append(float(trades["pnl_net"].sum()))
            win_rates.append(float((trades["pnl_net"] > 0).mean() * 100))
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.bar(labels, profits, color="#1f77b4", alpha=0.8)
    ax1.set_ylabel("Net Profit USD")
    ax2 = ax1.twinx()
    ax2.plot(labels, win_rates, color="#ff7f0e", marker="o")
    ax2.set_ylabel("Win Rate %")
    plt.title("Comparacion Swing vs Day Trading")
    fig.tight_layout()
    plt.savefig(output)
    plt.close()


def generate_hmm_outputs(output_dir: Path, results: dict[str, dict[str, Any]], initial_capital: float) -> None:
    output_dir.mkdir(exist_ok=True)
    for name, result in results.items():
        distribution = regime_distribution(result["regimes"])
        transition = transition_matrix(result["regimes"])
        result["distribution"] = distribution
        result["transition"] = transition
        plot_regime_timeline(result["regimes"], output_dir / f"hmm_{name}_timeline.png", f"{name} - Timeline de regimenes")
        plot_regime_distribution(distribution, output_dir / f"hmm_{name}_distribution.png", f"{name} - Distribucion por regimen")
        plot_transition_matrix(transition, output_dir / f"hmm_{name}_transition.png", f"{name} - Matriz de transicion")
        plot_equity_by_regime(
            result["classified_trades"],
            output_dir / f"hmm_{name}_equity_by_regime.png",
            f"{name} - Equity por regimen",
            initial_capital,
        )
    plot_swing_vs_day(results, output_dir / "hmm_swing_vs_day.png")
    write_text_report(output_dir / "hmm_regime_report.txt", results)
