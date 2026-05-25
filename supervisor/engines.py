from __future__ import annotations

from typing import Any

from .decision import AgentDecision


def trader_engine(analysis: dict[str, Any], min_confidence: float) -> AgentDecision:
    signal = str(analysis.get("signal", "WAIT"))
    confidence = float(analysis.get("confidence", 0.0))
    if signal not in {"LONG", "SHORT"}:
        return AgentDecision(
            "trader",
            "wait",
            f"Trader sin setup accionable: {signal}.",
            {"signal": signal, "confidence": confidence},
        )
    if confidence < min_confidence:
        return AgentDecision(
            "trader",
            "blocked",
            f"Confianza {confidence:.2f} menor al minimo {min_confidence:.2f}.",
            {"signal": signal, "confidence": confidence},
        )
    return AgentDecision(
        "trader",
        "approved",
        f"Setup tecnico {signal} con confianza {confidence:.2f}.",
        {
            "signal": signal,
            "confidence": confidence,
            "entry_timeframe": analysis.get("entry_timeframe", "1H"),
            "opportunity_score": analysis.get("opportunity_score"),
        },
    )


def risk_engine(
    analysis: dict[str, Any],
    *,
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
) -> AgentDecision:
    if active_positions >= max_open_positions:
        return AgentDecision("risk", "blocked", "Maximo de posiciones abiertas alcanzado.", {"active_positions": active_positions})
    if daily_trades >= max_trades_per_day:
        return AgentDecision("risk", "blocked", "Limite diario de trades alcanzado.", {"daily_trades": daily_trades})
    if not can_trade:
        return AgentDecision("risk", "blocked", "Cooldown o estado del bot no permite operar.", {})
    if usd_size < min_order_usd:
        return AgentDecision(
            "risk",
            "blocked",
            f"Tamano de orden {usd_size:.2f} menor al minimo {min_order_usd:.2f}.",
            {"usd_size": usd_size},
        )
    if stop_distance <= 0:
        return AgentDecision("risk", "blocked", "Distancia de stop invalida.", {"stop_distance": stop_distance})
    return AgentDecision(
        "risk",
        "approved",
        f"Riesgo aprobado: ${risk_amount:.2f}, notional ${usd_size:.2f}, leverage {leverage:.2f}x.",
        {
            "risk_amount": risk_amount,
            "notional_usd": usd_size,
            "stop_distance": stop_distance,
            "leverage": leverage,
            "symbol": analysis.get("symbol"),
        },
    )


def hmm_engine(analysis: dict[str, Any], allowed_regimes: set[int] | None, enabled: bool) -> AgentDecision:
    regime = analysis.get("hmm_regime")
    label = analysis.get("hmm_regime_label")
    if not enabled:
        return AgentDecision("hmm", "context", "HMM disponible como contexto; filtro automatico desactivado.", {"regime": regime, "label": label})
    if regime is None:
        return AgentDecision("hmm", "blocked", "Filtro HMM activo pero no hay regimen calculado.", {})
    regime_int = int(regime)
    if allowed_regimes is not None and regime_int not in allowed_regimes:
        return AgentDecision("hmm", "blocked", f"Regimen HMM {regime_int} no permitido para operar.", {"regime": regime_int, "label": label})
    return AgentDecision("hmm", "approved", f"Regimen HMM {regime_int} permitido.", {"regime": regime_int, "label": label})


def ai_engine(analysis: dict[str, Any], use_ai_assist: bool) -> AgentDecision:
    if not use_ai_assist:
        return AgentDecision("ai", "context", "IA asistida desactivada.", {})
    if analysis.get("ai_rate_limited"):
        return AgentDecision("ai", "blocked", "OpenAI rate limited; fallback seguro.", {"ai_rate_limited": True})
    feedback = analysis.get("ai_feedback") or {}
    if isinstance(feedback, dict) and feedback.get("allow") is False:
        return AgentDecision("ai", "blocked", "IA rechazo la operacion.", {"feedback": feedback})
    if analysis.get("ai_called"):
        return AgentDecision("ai", "approved", "IA no bloqueo la operacion.", {"feedback": feedback})
    return AgentDecision("ai", "context", "IA no fue llamada porque la senal no lo requirio.", {})

