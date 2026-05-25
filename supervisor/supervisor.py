from __future__ import annotations

from typing import Any

from .decision import SupervisorDecision
from .engines import ai_engine, hmm_engine, risk_engine, trader_engine


def evaluate_supervisor(
    analysis: dict[str, Any],
    *,
    min_confidence: float,
    use_ai_assist: bool,
    hmm_filter_enabled: bool,
    allowed_hmm_regimes: set[int] | None,
    active_positions: int,
    max_open_positions: int,
    daily_trades: int,
    max_trades_per_day: int,
    can_trade: bool,
    usd_size: float,
    min_order_usd: float,
    risk_amount: float,
    stop_distance: float,
    leverage: float,
) -> SupervisorDecision:
    agents = [
        trader_engine(analysis, min_confidence),
        risk_engine(
            analysis,
            active_positions=active_positions,
            max_open_positions=max_open_positions,
            daily_trades=daily_trades,
            max_trades_per_day=max_trades_per_day,
            can_trade=can_trade,
            usd_size=usd_size,
            min_order_usd=min_order_usd,
            risk_amount=risk_amount,
            stop_distance=stop_distance,
            leverage=leverage,
        ),
        hmm_engine(analysis, allowed_hmm_regimes, hmm_filter_enabled),
        ai_engine(analysis, use_ai_assist),
    ]

    blocking = [agent for agent in agents if agent.status == "blocked"]
    if blocking:
        return SupervisorDecision(
            approved=False,
            action="WAIT",
            reason=" | ".join(agent.reason for agent in blocking),
            agents=agents,
        )

    signal = str(analysis.get("signal", "WAIT"))
    if signal not in {"LONG", "SHORT"}:
        return SupervisorDecision(
            approved=False,
            action="WAIT",
            reason="No hay senal accionable.",
            agents=agents,
        )

    return SupervisorDecision(
        approved=True,
        action=signal,
        reason="Supervisor aprobo la operacion con controles Trader/Riesgo/HMM/IA.",
        agents=agents,
    )

